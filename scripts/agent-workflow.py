#!/usr/bin/env python3
"""Project routing and Empirica entrypoint. Run from any directory in this checkout."""

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit


def context():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / ".agent-workflow.json").read_text())
    uuid.UUID(config["project_id"])
    actual = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"], text=True
    ).strip()
    if Path(actual).resolve() != root:
        raise RuntimeError("Workflow file is outside its owning Git checkout")
    origin = subprocess.check_output(
        ["git", "-C", str(root), "remote", "get-url", "origin"], text=True
    ).strip()
    if origin.startswith("git@github.com:"):
        origin = "ssh://git@github.com/" + origin.removeprefix("git@github.com:")
    remote = urlsplit(origin)
    repository = remote.path.removeprefix("/").rstrip("/").removesuffix(".git")
    if (
        remote.scheme not in ("https", "ssh")
        or remote.hostname != "github.com"
        or remote.port not in (None, 22 if remote.scheme == "ssh" else 443)
        or remote.query
        or remote.fragment
        or repository.lower() != config["repository"].lower()
    ):
        raise RuntimeError("GitHub destination does not match this checkout origin")
    return root, config


def verify_entrypoints(root, config):
    for name in config["skills"]:
        canonical = (root / "skills" / name / "SKILL.md").resolve()
        if not canonical.is_file() or not canonical.is_relative_to(root.resolve()):
            raise RuntimeError("Missing or external canonical skill: " + name)
        for base in [".agents/skills", ".claude/skills"]:
            entry = root / base / name / "SKILL.md"
            if not entry.is_file() or entry.resolve() != canonical:
                raise RuntimeError("Invalid skill entrypoint: " + base + "/" + name)
    for path in [
        ".claude/commands/abc.md",
        ".claude/commands/intake.md",
        "docs/agent-workflow.md",
    ]:
        if not (root / path).is_file():
            raise RuntimeError("Missing workflow file: " + path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["verify", "status", "bootstrap", "session", "finding", "search"],
    )
    parser.add_argument("--text")
    parser.add_argument("--session-id")
    parser.add_argument("--epistemic-source", choices=["intuition", "search", "mixed"])
    args = parser.parse_args()
    root, config = context()
    if args.action == "status":
        print(json.dumps(config, indent=2))
        return
    project = root / ".empirica/project.yaml"
    if not project.exists():
        if args.action != "bootstrap":
            raise RuntimeError(
                "Run bootstrap to initialize this checkout under its existing project identity"
            )
        subprocess.run(
            [
                "empirica",
                "project-init",
                "--project-id",
                config["project_id"],
                "--project-name",
                config["name"],
                "--non-interactive",
                "--output",
                "json",
            ],
            cwd=root,
            check=True,
        )
    # project-init emits a top-level UUID scalar; reject duplicate or alternate values.
    entries = re.findall(
        r"^(?:project_id|\"project_id\"|'project_id')[ \t]*:[^\r\n]*",
        project.read_text(),
        re.MULTILINE,
    )
    identity = (
        entries[0].split(":", 1)[1].split("#", 1)[0].strip()
        if len(entries) == 1
        else ""
    )
    if identity.startswith(("'", '"')):
        identity = (
            identity[1:-1] if len(identity) >= 2 and identity[-1] == identity[0] else ""
        )
    if identity != config["project_id"]:
        raise RuntimeError(
            "Empirica identity mismatch; do not write into another project"
        )
    if args.action == "verify":
        verify_entrypoints(root, config)
        print(
            json.dumps(
                {
                    "ok": True,
                    "repository": config["repository"],
                    "project_id": config["project_id"],
                }
            )
        )
        return
    if args.action in ["finding", "search"] and not args.text:
        parser.error("--text is required for " + args.action)
    if args.action == "finding" and not args.session_id:
        parser.error("--session-id from this conversation is required for finding")
    if args.action == "finding" and not args.epistemic_source:
        parser.error(
            "--epistemic-source is required to record the finding's actual provenance"
        )
    commands = {
        "bootstrap": [
            "project-bootstrap",
            "--include-live-state",
            "--depth",
            "minimal",
        ],
        "session": ["session-create", "--ai-id", "workflow"],
        "finding": [
            "finding-log",
            "--session-id",
            args.session_id or "",
            "--finding=" + (args.text or ""),
            "--scope",
            "project",
            "--visibility",
            "local",
            "--epistemic-source",
            args.epistemic_source or "",
        ],
        "search": [
            "project-search",
            "--task=" + (args.text or ""),
            "--type",
            "focused",
            "--limit",
            "5",
        ],
    }
    env = dict(os.environ, EMPIRICA_PROJECT_ID=config["project_id"])
    result = subprocess.run(
        [
            "empirica",
            *commands[args.action],
            "--project-id",
            config["project_id"],
            "--output",
            "json",
        ],
        cwd=root,
        env=env,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("Workflow error: " + str(error), file=sys.stderr)
        sys.exit(1)
