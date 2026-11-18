# OpenSprinkler-Firmware

<!-- project-workflow:start -->
## Project work tracking and Empirica

Use [the project workflow](docs/agent-workflow.md) for implementation, maintenance, bug intake and idea intake. GitHub Issues in `kars85/OpenSprinkler-Firmware` are the work tracker; keep acceptance, handoff and verification evidence there. Preserve local specs/runbooks as reference documents. This supersedes older local-only task-tracker instructions.

Apply local-only/offline/confidentiality constraints before GitHub or shared Empirica access; use local files and drafts when those services are outside scope. Read access alone does not permit bootstrap or session creation; use local/cached evidence when writes are outside scope. When Empirica initialization and session/evidence writes are authorized, run `python3 scripts/agent-workflow.py bootstrap` and `verify`; `session` opens this conversation's explicit Empirica session. The profile in `.agent-workflow.json` owns the project UUID, repository and checks. Use project-specific `opensprinkler-firmware-abc` / `opensprinkler-firmware-intake` skills or Claude `/abc` / `/intake`; keep findings scoped to this project. Existing safety and deployment constraints continue to apply.
<!-- project-workflow:end -->
