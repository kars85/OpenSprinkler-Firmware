---
name: opensprinkler-firmware-intake
description: "Investigate bugs or ideas and file actionable, duplicate-checked GitHub issues for OpenSprinkler-Firmware, with project-scoped Empirica evidence."
---

# OpenSprinkler-Firmware /intake

Investigate and file work for OpenSprinkler-Firmware. Read `docs/agent-workflow.md` and `.agent-workflow.json`, then bootstrap this checkout and then verify its Empirica identity. Accept `bug "title"`, `idea "title"`, or an ordinary request to document work.

Search issues in `kars85/OpenSprinkler-Firmware` first. A bug needs observed/expected behavior, reproducible evidence or an explicitly named missing reproduction, and a bounded acceptance test. An idea needs the requested outcome, evidence, constraints, alternatives that affect the decision, and explicit scope. Ask only for missing facts that change the work.

Create or update the controlling issue under the user's work-documentation authorization. Use a structured GitHub tool or a uniquely named temporary body file with `gh issue create --repo kars85/OpenSprinkler-Firmware --body-file PATH`; never interpolate prose into shell source. Include `<!-- intake-schema: v1 -->`, independently verifiable `- [ ] [P1] ...` items (adjust priority to evidence), dependencies, verification, and remaining uncertainty. Only apply labels that exist; labels are optional.

For multi-project work, file linked issues in the owning repositories. Epic parents coordinate children; child issues own executable tasks. Validate the returned URL/repository, record the durable finding with this project's Empirica UUID, and return the issue link. Empirica bookkeeping failure must not duplicate a successful GitHub write. Use the target-specific build matrix in .github/workflows/build-ci.yml. package.json test is a failing placeholder. A build does not validate physical valves; flashing and live watering require task-specific authorization.
