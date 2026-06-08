# OpenSprinkler ecosystem — cross-project coupling map

> **Why this exists:** three sibling repos are coupled. A change in one can break another if the contract isn't coordinated. This is the hub map: what's coupled, where each contract is documented, and the rule for changing coupled behavior safely. **If you change anything listed under "Coupled on" below, check the linked contract on the other side first.**

This repo (**OpenSprinkler-Firmware**, the controller) sits at the center of two couplings.

## The three projects

| Project | Role | Language | Repo |
|---|---|---|---|
| **OpenSprinkler-Weather** | Weather/watering-adjustment service — **producer** of the watering response | Node/TypeScript | `OpenSprinkler-Weather` |
| **OpenSprinkler-Firmware** *(this repo)* | Irrigation controller — **consumer** of the weather contract; **host** of the OTF library | C/C++ | `OpenSprinkler-Firmware` |
| **OpenThings-Framework-Firmware-Library** (OTF) | HTTP server + OpenThings Cloud remote-access layer — compile-time **dependency** of the firmware | C++ | `OpenThings-Framework-Firmware-Library` |

## Coupling axes

### A. Weather ↔ Firmware — the watering-response wire contract  ✅ bidirectionally documented
- **Coupled on:** the flat `&key=value` watering response (`scale`, `restricted`, `rd`, `rawData`, `sunrise/sunset`, `tz`, `eip`, `scales`) parsed in `weather.cpp:getweather_callback`.
- **Producer-side (canonical wire format):** `OpenSprinkler-Weather/docs/firmware-integration-requirements.md`, with a CI guard `OpenSprinkler-Weather/test/firmware-contract.spec.ts` and a coordination backlog `OpenSprinkler-Weather/docs/firmware-integration-backlog.md`.
- **Consumer-side (firmware constraints):** [`docs/weather-contract.md`](weather-contract.md) — hard limits (`rawData ≤ 319 B`, `ETHER_BUFFER_SIZE`, AVR no-TLS), parser behavior, the `restricted` and `scales` records.
- **Cross-repo work is tracked as issues on this repo:** [#2](https://github.com/kars85/OpenSprinkler-Firmware/issues/2), [#3](https://github.com/kars85/OpenSprinkler-Firmware/issues/3), [#4](https://github.com/kars85/OpenSprinkler-Firmware/issues/4) (mirrored in the weather backlog).
- **Rule:** wire-format changes land in the **weather** repo first (it's canonical) and update both docs together; the CI guard protects existing controllers.

### B. Firmware ↔ OTF — the HTTP/cloud library dependency  ✅ documented (see [`docs/otf-integration.md`](otf-integration.md))
- **Coupled on:** `platformio.ini` pin (`^0.2.0`), `USE_OTF` gating (`defines.h:177-178`), the `OTF_PARAMS_DEF` handler API (`OTF::Request`/`OTF::Response`), `otf->on(...)` route registration, the shared `ether_buffer`, and OTC cloud config/status (`/jc` `otcs`).
- **Library-side (canonical API + integration):** `OpenThings-Framework-Firmware-Library/ARCHITECTURE.md`.
- **Firmware-side (consumer pointer + constraints):** [`docs/otf-integration.md`](otf-integration.md).
- **Rule:** an OTF API change (handler signature, `Request`/`Response`, constructor) or a major version bump can break every web handler here — review `ARCHITECTURE.md` and the version pin before changing either side.

### C. Weather ↔ OTF — **no direct coupling** (intentional)
The weather service does not use OTF, and OTF does not know about the weather service. They interact only *through* the firmware. Keep it that way.

## External-facing contracts (informal — not yet codified)
These couple the firmware to apps/integrations rather than to a sibling repo, but the same "don't break consumers" rule applies:
- **`fwv` (firmware version) negotiation** — the weather service and app key behavior off `fwv`; older firmware can't parse newer payloads.
- **MQTT payload/topic shapes** (e.g. `{"state":"skipped","wtrestr":1}`) — Home Assistant and other integrators couple to these; changing `notifier.cpp` output can break them.
- **OTC remote-station handshake** (`STN_TYPE_REMOTE_OTC`, OTC token in `/jc`).

## The one rule
**Before changing any behavior under "Coupled on," open the linked contract doc on the other side and update both together (and the CI guard / version pin where one exists).** That is what keeps a fix in one project from silently breaking another.

---
*Maintained as part of the cross-project coupling hygiene effort. See also [`weather-contract.md`](weather-contract.md), [`otf-integration.md`](otf-integration.md), and `firmware-definition.md`.*
