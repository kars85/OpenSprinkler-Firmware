# OpenSprinkler-Firmware — Codebase Definition (structure, weaknesses, phased improvement)

> **Provenance:** A definition/analysis pass (not implementation) produced via multi-AI review — Codex (read the codebase directly, with file:line citations), Gemini (architecture/maintainability), and Claude (synthesis + measured structure). Generated 2026-06-06 from a cross-project session in the sibling OpenSprinkler-Weather service. Uncommitted draft for maintainer review.

## Problem statement (current architecture)

~19.5K LOC of C/C++ in a **flat root** (no `src/`; only `docs/ examples/ external/ html/ skills/`). The runtime centers on a **global god-object** `OpenSprinkler os` (`OpenSprinkler.h`, ~101 methods) plus oversized shared scratch buffers (`tmp_buffer`, `ether_buffer`). Three files carry most of the system:

- **`OpenSprinkler.cpp` (3280)** — boot, options, storage, display, GPIO expansion, valve drive, HTTP client, factory reset.
- **`main.cpp` (2089)** — a ~600-line `do_loop()` (`:580`) orchestrating flow/current polling, HTTP/OTF servicing, MQTT, 1-second scheduling, sensors/rain-delay, program matching, queue execution, master-zone + valve application, weather, notifications, NTP, network checks, reboot. `do_setup()` is **duplicated** under conditional compilation (`:419` / `:498`).
- **`opensprinkler_server.cpp` (2636)** — a table-driven HTTP router (`_url_keys` / `urls[]`, `:2192`) whose handlers mutate `os`/`pd` directly through the shared buffers (routing + auth + parse + validate + mutate in one file).

Build targets (AVR/Arduino, ESP8266, OSPi/Linux, DEMO, `USE_OTF`, display/HTTPS/email variants) are selected by **preprocessor branches interleaved throughout** (`defines.h`, `OpenSprinkler.cpp:529`, `main.cpp:419`, `gpio.cpp`). **Zero automated tests.** Three parallel build systems (`platformio.ini`, `Makefile`, `mainArduino.ino`) + `Dockerfile`.

**Weather-service boundary:** `weather.cpp:160` (`GetWeather()`) calls the remote weather server (`weather?.py`); its flat, `&`-delimited callback at `weather.cpp:54` (`getweather_callback`) **directly mutates** water level/scale, sunrise, sunset, external IP, timezone, rain delay, raw data, historical scales, and NVRAM via `os.weather_update_flag` bits. The schema is **implicit, unversioned, and only partially validated**, and is hard to test in isolation — it is the legacy contract the sibling OpenSprinkler-Weather service emits (which now also offers a cleaner versioned `/v1` JSON API).

## Prioritized weaknesses

1. **Maintainability / modularity (highest).** The three giant files each hide multiple subsystems; the `os` god-object + global mutable state create pervasive coupling, making changes risky. The duplicated `do_setup()` is a concrete drift hazard.
2. **Testability (highest leverage).** No tests and almost no pure seams. Core logic — `ProgramStruct::check_match()` (`program.cpp:315`), `schedule_all_stations()` (`main.cpp:1475`), HTTP/MQTT command + `wto` parsing — depends on globals, time, storage, and shared buffers, so none of it is host-testable today.
3. **Safety / reliability.** Watchdog coverage is mainly AVR setup/loop paths (`main.cpp:444`/`:767`); ESP/Linux is more cooperative. The oversized global scratch buffers invite cross-call coupling. Valve correctness depends on `station_bits` + the runtime queue + master bits + special-station side-effects + repeated `apply_all_station_bits()` (`OpenSprinkler.cpp:1362`), and failures are mostly **silent**. Overcurrent handling is solid but embedded in loop timing (`main.cpp:552`).
4. **Firmware ↔ weather boundary.** Brittle: implicit/unversioned schema, partial validation, direct NVRAM mutation from the parse callback, and no interface seam — so weather providers can't be flexed and `/v1` can't be adopted without touching core logic.

## Phase 1 — incremental, low-risk (does not disrupt shipping firmware)

- **Extract from `main.cpp`:** `scheduler.cpp` (`check_weather`, `schedule_all_stations`, station on/off/reset, dynamic events) and `safety.cpp` (current/flow/watchdog/reboot); keep `do_loop()` as thin orchestration.
- **Extract from `OpenSprinkler.cpp`:** `station_store`, `options_store`, `station_driver`, `http_client`, and the display code — preserving the public API initially.
- **Extract from `opensprinkler_server.cpp`:** the route table, auth/query parsing, and the program / station / log endpoint groups.
- **First host-side unit tests** around the now-pure logic: `starttime_decode` / `check_match`, `parse_listdata`, `parse_wto`, `parseMdScalesArray`, and station-queue scheduling against a fake `os` state.
- **Deduplicate `do_setup()`** into shared boot steps + per-target hooks.
- **Isolate the weather contract:** a `WeatherContract` parser returning a validated `WeatherResult`; a single adapter applies it to `os`. This is the seam that later enables `/v1` adoption.

## Phase 2 — re-architecture roadmap

- Layer into: domain scheduler · controller state · hardware abstraction (HAL) · persistence · protocol adapters · platform layer.
- Replace global `os` access with **injected interfaces** (time, storage, valve driver, network, notifier) — which unlocks host-side testing.
- Consolidate build/config into explicit **target profiles** + a **CI matrix**.
- Add **CI**: host unit tests, static analysis, firmware size checks, selected platform builds.
- Decompose the `OpenSprinkler` god-object into service classes; standardize error handling / failsafes.
- **Adopt the `/v1` weather API** through the Phase-1 contract seam (versioned, validated, testable).

## Out of scope
Implementation, per-feature specs, non-weather protocol redesign, and hardware changes. This is a definition/analysis pass.

## Provider perspectives (summary)
- **Codex (technical, code-grounded):** identified the three monoliths' mixed concerns, the table-driven-but-monolithic HTTP handler, the duplicated `do_setup`, the silent valve-failure surface, and concrete extraction targets with file:line anchors.
- **Gemini (architecture/maintainability):** emphasized the god-object/global-state coupling, the total absence of tests as the central risk, build-system sprawl, and the brittle weather coupling; recommended HAL + DI + unified build + CI.
- **Claude (synthesis):** measured the structure (LOC, layout, no tests), reconciled both perspectives, and sequenced Phase 1 (extraction + first tests + the weather seam) ahead of Phase 2 (layering/DI/CI/`/v1`).
