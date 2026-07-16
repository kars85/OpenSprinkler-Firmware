# OpenSprinkler ecosystem — cross-project coupling map

> **Why this exists:** four sibling repos are coupled. A change in one can break another if the contract isn't coordinated. This is the hub map: what's coupled, where each contract is documented, and the rule for changing coupled behavior safely. **If you change anything listed under "Coupled on" below, check the linked contract on the other side first.**

This repo (**OpenSprinkler-Firmware**, the controller) sits at the center of three couplings.

## The four projects

| Project | Role | Language | Repo |
|---|---|---|---|
| **OpenSprinkler-Weather** | Weather/watering-adjustment service — **producer** of the watering response | Node/TypeScript | `OpenSprinkler-Weather` |
| **OpenSprinkler-Firmware** *(this repo)* | Irrigation controller — **consumer** of the weather contract; **host** of the OTF library; **producer** of the web API | C/C++ | `OpenSprinkler-Firmware` |
| **OpenThings-Framework-Firmware-Library** (OTF) | HTTP server + OpenThings Cloud remote-access layer — compile-time **dependency** of the firmware | C++ | `OpenThings-Framework-Firmware-Library` |
| **OpenSprinkler-App** | Web/Cordova UI — **consumer** of the firmware web API | JavaScript | `OpenSprinkler-App` |

## Coupling axes

### A. Weather ↔ Firmware — the watering-response wire contract  ✅ bidirectionally documented
- **Coupled on:** the flat `&key=value` watering response (`scale`, `restricted`, `rd`, `rawData`, `sunrise/sunset`, `tz`, `eip`, `scales`) parsed in `weather.cpp:getweather_callback`.
- **Producer-side (canonical wire format):** `OpenSprinkler-Weather/docs/firmware-integration-requirements.md`, with a CI guard `OpenSprinkler-Weather/test/firmware-contract.spec.ts` and a coordination backlog `OpenSprinkler-Weather/docs/firmware-integration-backlog.md`.
- **Consumer-side (firmware constraints):** [`docs/weather-contract.md`](weather-contract.md) — hard limits (`rawData ≤ 319 B`, `ETHER_BUFFER_SIZE`, AVR no-TLS), parser behavior, the `restricted` and `scales` records.
- **Cross-repo work is tracked as issues on this repo:** [#2](https://github.com/kars85/OpenSprinkler-Firmware/issues/2), [#3](https://github.com/kars85/OpenSprinkler-Firmware/issues/3), [#4](https://github.com/kars85/OpenSprinkler-Firmware/issues/4) (mirrored in the weather backlog).
- **Rule:** wire-format changes land in the **weather** repo first (it's canonical) and update both docs together; the CI guard protects existing controllers.

### B. Firmware ↔ OTF — the HTTP/cloud library dependency  ✅ documented (see [`docs/otf-integration.md`](otf-integration.md))
- **Coupled on:** `platformio.ini` version constraint (`^0.2.0`), `USE_OTF` gating (`defines.h:190-196`), the `OTF_PARAMS_DEF` handler API (`OTF::Request`/`OTF::Response`), `otf->on(...)` route registration, the shared `ether_buffer`, and OTC cloud config/status (`/jc` `otcs`).
- **Library-side (canonical API + integration):** `OpenThings-Framework-Firmware-Library/ARCHITECTURE.md`.
- **Firmware-side (consumer pointer + constraints):** [`docs/otf-integration.md`](otf-integration.md).
- **Rule:** an OTF API change (handler signature, `Request`/`Response`, constructor) or dependency-resolution change can break every web handler here — review `ARCHITECTURE.md` and the version constraint before changing either side.

### C. Weather ↔ OTF — **no direct coupling** (intentional)
The weather service does not use OTF, and OTF does not know about the weather service. They interact only *through* the firmware. Keep it that way.

### D. App ↔ Firmware — the web API contract  ✅ bidirectionally documented + CI guarded
- **Coupled on:** the current two-character 2.2.1(4) web API in scope. Its keys are registered in the firmware's `_url_keys[]` PROGMEM table (`opensprinkler_server.cpp:2209-2236`) and dispatched through the parallel `urls[]` handler table (`opensprinkler_server.cpp:2239-2266`). Renaming, reordering, or removing a key breaks consumers; **the two tables are positional and must stay index-aligned**. Coupling covers four surfaces:
  - **Endpoints + JSON field names.** Read endpoints span `/jo`, `/jc`, `/js`, `/jn`, `/jp`, `/ja`, `/je`, and `/jl`; mutations include `/cv`, `/co`, `/cs`, `/cm`, `/cp`, `/dp`, `/up`, `/cr`, `/mp`, `/dl`, `/sp`, `/cu`, and `/pq`. The app reads JSON keys directly, so field names are part of the contract, not an implementation detail. Non-table pages such as `/update` remain separate surfaces.
  - **Layered version/capability signals.** Frozen legacy gates combine `fwv` and `fwm` for four-digit checks (`fwv * 10 + fwm`). The modern fork uses `fwv` only as the storage/pre-auth floor, requires `fwf` beginning with `kars85.` for provenance, and requires both a reset-free `fwm` capability floor and field presence. **Never bump `fwv` merely to ship a fork feature.**
  - **Auth + the `fwv`-on-failure escape hatch.** The frozen legacy add-site probe sends `/jo?pw=md5(pw)` before it knows the version. Firmware returns **HTTP 200 `{"fwv":N}`** on failed `/jo` and `/ja` authentication, so legacy sees `fwv` present but `wl` absent and can fall back to cleartext for pre-2.1.3 controllers; **`wl` presence is the auth-success sentinel.** The modern UI is hash-only, but it still uses the `fwv`-only shape to distinguish Unsupported from Authentication. Removing or expanding this response silently breaks bootstrap behavior.
  - **UI injection and recovery.** An unauthenticated visit to `/su` renders the recovery/settings form. Its submission goes to authenticated `/cu`, which persists nonempty `jsp` and `wsp` values; omitted or empty values leave the stored setting unchanged. A deployed app update then reaches every controller pointing at that UI host without a firmware flash, while old app builds continue hitting new controllers.
- **Firmware-side (canonical API reference):** [`docs/docs/2.2.1/221_4_api.md`](docs/2.2.1/221_4_api.md) — full endpoint + parameter docs. The handler tables above are the source of truth.
- **App-side (consumer constraints):** `OpenSprinkler-App/docs/firmware-contract.md` — the producer constraints, the full `fwv` gate tier table, the auth bootstrap, the `result` code contract, and the endpoints/fields consumed.
- **CI guard:** `OpenSprinkler-App/.github/workflows/test.yml` builds the native Firmware DEMO and runs `test/firmware-demo-contract.spec.ts` against success shapes, mutations, and auth-enabled `/jo`/`/ja` HTTP-200 `fwv` failures. The typed guard covers the modern consumer surface; grep frozen legacy call sites before removing or renaming anything.
- **Rule:** the **firmware is canonical** here (inverse of axis A). Endpoint keys and JSON field names are append-only in practice — old app builds and old controllers coexist in the field in both directions. Additive fork behavior uses a documented `fwm` floor plus `fwf` identity and field presence; it never bumps `fwv` merely for capability detection.

### E. App ↔ Weather — frozen legacy direct dependency; do not extend it
The frozen legacy app calls the configured Weather service directly for `/weatherData` and `/baselineETo`, and calls provider APIs such as `api.weather.com/v2/pws/` for validation (`www/js/modules/weather.js:469-486`, `:559-593`, `:665-699`). It derives the service from `/jc.wsp`, with an unauthenticated `/su` scrape as an old-firmware fallback. Firmware exposes `jsp`, `wsp`, `wto`, `wtdata`, `wterr`, `wtrestr`, and `wls` in `/jc`; `uwt` and `wl` are `/jo` options. The modern UI must not add a direct Weather dependency; these direct calls retire with the frozen legacy surface.

### F. App ↔ OTF — **cloud service only, not the library**
The app never compiles or links OTF. It couples to the same **OpenThings Cloud** service OTF talks to, routing requests through `https://cloud.openthings.io/forward/v1/<token>` instead of a local IP (`www/js/modules/firmware.js:56`, `www/js/modules/sites.js:396`) with tokens matching `^OT[a-fA-F0-9]{30}$` (`www/js/modules/dashboard.js:169`). This is the outbound half of the OTC contract in [`external-contracts.md`](external-contracts.md) — the app is a third consumer of that URL shape, alongside the firmware's remote stations.

## External-facing contracts → [`external-contracts.md`](external-contracts.md)
These couple the firmware to apps/integrations/cloud rather than to a sibling repo, but the same "don't break consumers" rule applies. Now codified in [`external-contracts.md`](external-contracts.md):
- **`fwv`/`fwm`/`fwf` negotiation** — `fwv` is the storage/API epoch, `fwm` is a reset-free capability revision, and `fwf` is fork provenance. The app's side is axis D above; Weather polls continue sending `fwv` only.
- **MQTT payload/topic shapes** (e.g. `{"state":"skipped","wtrestr":1}`) — Home Assistant and other integrators couple to these; changing `notifier.cpp` output can break them.
- **OTC remote access** — inbound cloud tunnel (`/socket/v1?deviceKey=`) and outbound remote-station control (`STN_TYPE_REMOTE_OTC` → `/forward/v1/<token>/cm`).

## The one rule
**Before changing any behavior under "Coupled on," open the linked contract doc on the other side and update both together (and the CI guard / dependency constraint where one exists).** That is what keeps a fix in one project from silently breaking another.

---
*Maintained as part of the cross-project coupling hygiene effort. See also [`weather-contract.md`](weather-contract.md), [`otf-integration.md`](otf-integration.md), [`docs/2.2.1/221_4_api.md`](docs/2.2.1/221_4_api.md), and `firmware-definition.md`.*
