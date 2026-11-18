"""Offline routing checks; no GitHub, Empirica or production writes."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).with_name("agent-workflow.py")


# Application suites may discover this file; dedicated workflow CI installs PyYAML first.
@unittest.skipUnless(
    importlib.util.find_spec("yaml"),
    "Install scripts/requirements-agent-workflow.txt for workflow checks",
)
class RoutingTests(unittest.TestCase):
    def setUp(self):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        clean_git_environment = patch.dict(os.environ, environment, clear=True)
        clean_git_environment.start()
        self.addCleanup(clean_git_environment.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "scripts").mkdir()
        target = self.root / "scripts/agent-workflow.py"
        shutil.copyfile(SOURCE, target)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "remote",
                "add",
                "origin",
                "https://github.com/example/test.git",
            ],
            check=True,
        )
        self.id = "11111111-2222-4333-8444-555555555555"
        self.config = {
            "name": "test",
            "repository": "example/test",
            "project_id": self.id,
            "skills": [],
        }
        (self.root / ".agent-workflow.json").write_text(json.dumps(self.config))
        (self.root / ".empirica").mkdir()
        (self.root / ".empirica/project.yaml").write_text(
            "project_id: " + self.id + "\n"
        )
        spec = importlib.util.spec_from_file_location("workflow_test", target)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        actual_check_output = subprocess.check_output

        def fixture_check_output(command, **kwargs):
            if command[0] == "git":
                # Production clears GIT_*; keep fixture reads independent of host URL rewrites.
                kwargs["env"] = dict(
                    kwargs.get("env", os.environ),
                    GIT_CONFIG_GLOBAL=os.devnull,
                    GIT_CONFIG_SYSTEM=os.devnull,
                )
            return actual_check_output(command, **kwargs)

        git_reads = patch.object(
            self.module.subprocess, "check_output", side_effect=fixture_check_output
        )
        git_reads.start()
        self.addCleanup(git_reads.stop)

    def local_context(self):
        return patch.object(
            self.module, "context", return_value=(self.root, self.config)
        )

    def test_correct_repository(self):
        root, profile = self.module.context()
        self.assertEqual(root, self.root)
        self.assertEqual(profile["project_id"], self.id)

    def test_inherited_git_dir_cannot_redirect_fixture_setup(self):
        original_config = (self.root / ".git/config").read_bytes()
        with patch.dict(
            os.environ,
            {"GIT_DIR": str(self.root / ".git"), "GIT_WORK_TREE": str(self.root)},
        ):
            result = unittest.TestResult()
            RoutingTests("test_correct_repository").run(result)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertEqual((self.root / ".git/config").read_bytes(), original_config)

    def test_wrong_repository_is_rejected(self):
        self.config["repository"] = "example/other"
        (self.root / ".agent-workflow.json").write_text(json.dumps(self.config))
        with self.assertRaisesRegex(RuntimeError, "destination"):
            self.module.context()

    def test_foreign_git_metadata_cannot_spoof_context(self):
        foreign = self.root / "foreign"
        subprocess.run(["git", "init", "-q", str(foreign)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(foreign),
                "remote",
                "add",
                "origin",
                "https://github.com/example/test.git",
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "remote",
                "set-url",
                "origin",
                "https://github.com/example/other.git",
            ],
            check=True,
        )
        with patch.dict(
            os.environ,
            {"GIT_DIR": str(foreign / ".git"), "GIT_WORK_TREE": str(self.root)},
        ):
            with self.assertRaisesRegex(RuntimeError, "destination"):
                self.module.context()

    def test_standard_github_remote_forms(self):
        for origin in (
            "git@github.com:example/test.git",
            "ssh://git@github.com/example/test.git",
            "ssh://git@github.com:22/example/test.git/",
            "https://username:fake-token@github.com/example/test.git/",
        ):
            with self.subTest(origin=origin):
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(self.root),
                        "remote",
                        "set-url",
                        "origin",
                        origin,
                    ],
                    check=True,
                )
                self.assertEqual(self.module.context()[1]["repository"], "example/test")

    def test_spoofed_github_remote_is_rejected(self):
        for origin in (
            "ssh://git@github.com.example.org/example/test.git",
            "https://github.com@evil.example/example/test.git",
            "https://github.com/example/test.git?redirect=other",
            "ssh://git@github.com/example/other.git",
        ):
            with self.subTest(origin=origin):
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(self.root),
                        "remote",
                        "set-url",
                        "origin",
                        origin,
                    ],
                    check=True,
                )
                with self.assertRaisesRegex(RuntimeError, "destination"):
                    self.module.context()

    def test_malformed_origin_errors_omit_credentials(self):
        for authority in ("github.com\uff0f.invalid", "github.com:invalid-port"):
            with self.subTest(authority=authority):
                origin = (
                    "https://fake-user:fake-private-token@"
                    + authority
                    + "/example/test.git"
                )
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(self.root),
                        "remote",
                        "set-url",
                        "origin",
                        origin,
                    ],
                    check=True,
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        str(self.root / "scripts/agent-workflow.py"),
                        "status",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("fake-private-token", result.stderr)
                self.assertNotIn("fake-user", result.stderr)
                self.assertIn("GitHub destination", result.stderr)

    def test_workflow_allowlist_keeps_local_agent_files_private(self):
        checkout = SOURCE.parent.parent
        (self.root / ".gitignore").write_bytes((checkout / ".gitignore").read_bytes())
        profile = json.loads((checkout / ".agent-workflow.json").read_text())
        private = [
            ".claude/session-notes.md",
            ".claude/settings.local.json",
            ".claude/commands/local-only.md",
            ".claude/skills/local-only/SKILL.md",
            ".agents/session-notes.md",
            ".agents/skills/local-only/SKILL.md",
            ".empirica/sessions/sessions.db",
            ".empirica_reflex_logs/assessment.json",
            ".breadcrumbs.yaml",
        ]
        admitted = [".claude/commands/abc.md", ".claude/commands/intake.md"]
        for name in profile["skills"]:
            admitted.extend([".claude/skills/" + name, ".agents/skills/" + name])
        for path in private + admitted:
            with self.subTest(path=path):
                result = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(self.root),
                        "-c",
                        "core.excludesFile=/dev/null",
                        "check-ignore",
                        "--no-index",
                        "--quiet",
                        "--",
                        path,
                    ],
                    check=False,
                )
                self.assertEqual(result.returncode, 0 if path in private else 1)

    def test_wrong_identity_is_rejected_before_writing(self):
        (self.root / ".empirica/project.yaml").write_text("project_id: foreign\n")
        with (
            self.local_context(),
            patch.object(
                sys,
                "argv",
                ["workflow", "finding", "--text", "test", "--session-id", "session"],
            ),
            patch.object(self.module.subprocess, "run") as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                self.module.main()
        run.assert_not_called()

    def test_identity_suffixes_and_duplicate_keys_are_rejected(self):
        for value in (
            "project_id: " + self.id + ".foreign\n",
            "project_id: " + self.id + "#foreign\n",
            "project_id: " + self.id + "\nproject_id: foreign\n",
            "project_id: " + self.id + '\n"project_id": foreign\n',
            "project_id: " + self.id + '\n"\\x70roject_id": foreign\n',
            'project_id: "' + self.id + "'\n",
        ):
            with self.subTest(value=value):
                (self.root / ".empirica/project.yaml").write_text(value)
                with (
                    self.local_context(),
                    patch.object(sys, "argv", ["workflow", "session"]),
                    patch.object(self.module.subprocess, "run") as run,
                ):
                    with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                        self.module.main()
                run.assert_not_called()

    def test_exact_identity_scalars_and_separated_comments_are_accepted(self):
        for scalar in (self.id, "'" + self.id + "'", '"' + self.id + '"'):
            with (
                self.subTest(scalar=scalar),
                self.local_context(),
                patch.object(sys, "argv", ["workflow", "session"]),
                patch.object(
                    self.module.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0),
                ),
            ):
                (self.root / ".empirica/project.yaml").write_text(
                    "project_id: " + scalar + " # valid comment\n"
                )
                with self.assertRaises(SystemExit) as result:
                    self.module.main()
            self.assertEqual(result.exception.code, 0)

    def test_actual_checkout_entrypoints_resolve(self):
        checkout = SOURCE.parent.parent
        profile = json.loads((checkout / ".agent-workflow.json").read_text())
        self.module.verify_entrypoints(checkout, profile)

    def test_wrong_skill_link_is_rejected(self):
        for path in [
            "skills/test-abc/SKILL.md",
            ".claude/commands/abc.md",
            ".claude/commands/intake.md",
            "docs/agent-workflow.md",
        ]:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture")
        for base in [".agents/skills", ".claude/skills"]:
            target = self.root / base / "test-abc"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to("../../skills/test-abc")
        profile = dict(self.config, skills=["test-abc"])
        self.module.verify_entrypoints(self.root, profile)
        (self.root / ".agents/skills/test-abc").unlink()
        (self.root / ".agents/skills/test-abc").symlink_to("../../skills/missing")
        with self.assertRaisesRegex(RuntimeError, "entrypoint"):
            self.module.verify_entrypoints(self.root, profile)

    def test_dash_leading_text_is_passed_as_a_value(self):
        for action, flag in [("finding", "--finding="), ("search", "--task=")]:
            with (
                self.subTest(action=action),
                self.local_context(),
                patch.object(
                    sys,
                    "argv",
                    [
                        "workflow",
                        action,
                        "--text=--global",
                        "--session-id",
                        "my-session",
                        "--epistemic-source",
                        "mixed",
                    ],
                ),
                patch.object(
                    self.module.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0),
                ) as run,
            ):
                with self.assertRaises(SystemExit) as result:
                    self.module.main()
            self.assertEqual(result.exception.code, 0)
            self.assertIn(flag + "--global", run.call_args.args[0])
            self.assertNotIn("--global", run.call_args.args[0])

    def test_finding_requires_explicit_session(self):
        with (
            self.local_context(),
            patch.object(sys, "argv", ["workflow", "finding", "--text", "test"]),
            patch.object(self.module.subprocess, "run") as run,
        ):
            with self.assertRaises(SystemExit) as result:
                self.module.main()
        self.assertEqual(result.exception.code, 2)
        run.assert_not_called()

    def test_finding_routes_project_and_session(self):
        with (
            self.local_context(),
            patch.object(
                sys,
                "argv",
                [
                    "workflow",
                    "finding",
                    "--text",
                    "safe test",
                    "--session-id",
                    "my-session",
                    "--epistemic-source",
                    "mixed",
                ],
            ),
            patch.object(
                self.module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0),
            ) as run,
        ):
            with self.assertRaises(SystemExit) as result:
                self.module.main()
        self.assertEqual(result.exception.code, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--project-id") + 1], self.id)
        self.assertEqual(command[command.index("--session-id") + 1], "my-session")
        self.assertEqual(command[command.index("--epistemic-source") + 1], "mixed")
        self.assertNotIn("--global", command)
        self.assertFalse(
            any(key.startswith("GIT_") for key in run.call_args.kwargs["env"])
        )

    def test_finding_requires_explicit_provenance(self):
        with (
            self.local_context(),
            patch.object(
                sys,
                "argv",
                ["workflow", "finding", "--text", "test", "--session-id", "my-session"],
            ),
            patch.object(self.module.subprocess, "run") as run,
        ):
            with self.assertRaises(SystemExit) as result:
                self.module.main()
        self.assertEqual(result.exception.code, 2)
        run.assert_not_called()

    def test_fresh_checkout_bootstraps_same_identity(self):
        (self.root / ".empirica/project.yaml").unlink()
        calls = []

        def execute(command, **kwargs):
            calls.append(command)
            if command[1] == "project-init":
                (self.root / ".empirica/project.yaml").write_text(
                    "project_id: " + self.id + "\n"
                )
            return subprocess.CompletedProcess(command, 0)

        with (
            self.local_context(),
            patch.object(sys, "argv", ["workflow", "bootstrap"]),
            patch.object(self.module.subprocess, "run", side_effect=execute),
        ):
            with self.assertRaises(SystemExit) as result:
                self.module.main()
        self.assertEqual(result.exception.code, 0)
        self.assertEqual([c[1] for c in calls], ["project-init", "project-bootstrap"])
        self.assertTrue(all(c[c.index("--project-id") + 1] == self.id for c in calls))


if __name__ == "__main__":
    unittest.main()
