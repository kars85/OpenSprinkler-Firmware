---
name: opensprinkler-firmware-abc
description: "Plan, implement and validate GitHub issue work in OpenSprinkler-Firmware using its A/B/C handoff and Empirica project."
---

# OpenSprinkler-Firmware /abc

Execute the A/B/C workflow for OpenSprinkler-Firmware. Read `docs/agent-workflow.md` and `.agent-workflow.json` from the assigned checkout before acting. Before any GitHub or Empirica access, apply the current task's publication and confidentiality constraints. Offline or explicitly local-only work stays on this machine: do not bootstrap, initialize, create Empirica sessions, retrieve shared context, or publish/embed findings unless the current request explicitly permits those services. Use local files and cached evidence, keep a local draft, and continue authorized local work. `python3 scripts/agent-workflow.py status` is local; `verify` is also local when identity files already exist. A no-publish constraint alone forbids writes, not reads already authorized by the task. When shared-service access is authorized, run the workflow helper's bootstrap/verify/session commands. For restricted work, follow `Restricted local execution` in the workflow document through local validation and stop; use the current agent/local tools, local draft metadata and explicit unrun remote gates. Do not dispatch cloud-backed agents for this branch. For the authorized connected workflow, use only `kars85/OpenSprinkler-Firmware` and its configured Empirica UUID.

Resolve the requested issue from authorized GitHub access or a local cached/draft handoff. If none is supplied, inspect ready open issues and select only work covered by the user's request. Work one independently verifiable checklist item through PM-HANDOFF, DEV-EXECUTION and PM-VALIDATION. Claude plans/reviews and Codex implements when both runtimes are available. Read local CLI help to invoke them; never silently substitute an unavailable runtime or reviewer.

Use the profile's actual checks plus affected-area guidance. For --loop, continue ready items in the selected issue; for --loopall, continue authorized ready issues. Stop when the selected scope is accepted, no authorized ready work remains, or a concrete external decision blocks progress. Report unresolved dependencies without marking them done.

Keep issue acceptance, live system changes and merge/release authorization distinct. Record the exact state reached and link the issue/PR. Use the target-specific build matrix in .github/workflows/build-ci.yml. package.json test is a failing placeholder. A build does not validate physical valves; flashing and live watering require task-specific authorization.
