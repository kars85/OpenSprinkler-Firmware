# Project awareness — OpenSprinkler-Firmware

This controller firmware is **coupled to two sibling projects**. Before changing any coupled behavior, read the relevant contract on **both** sides — a change here can silently break the other project.

**Read [`docs/ecosystem.md`](docs/ecosystem.md) first** — it is the hub map of all three repos, every coupling point, and the coordination rule.

## Couplings (and the doc to consult before changing them)

- **Weather service** (`OpenSprinkler-Weather`, producer of the watering response) — consumed by `weather.cpp:getweather_callback`. Contract: [`docs/weather-contract.md`](docs/weather-contract.md) ↔ the weather repo's `docs/firmware-integration-requirements.md` (canonical wire format) + its CI guard `test/firmware-contract.spec.ts`. Cross-repo work is tracked as issues here (#2/#3/#4).
- **OpenThings Framework** (`OpenThings-Framework-Firmware-Library`, OTF — the HTTP server + OTC cloud layer, a compile-time dependency on non-AVR). Contract: [`docs/otf-integration.md`](docs/otf-integration.md) ↔ the OTF repo's `ARCHITECTURE.md`. Pinned `^0.2.0` in `platformio.ini`; the whole web API is built on `OTF::Request`/`OTF::Response`.

## The rule
Before changing the weather wire contract, the OTF handler/`Request`/`Response` API, the OTF version pin, or externally-observed shapes (`fwv`, MQTT payloads, OTC handshake): open the linked contract on the other side and update both together (plus the CI guard / version pin where one exists).

## Verification discipline
Don't trust recalled state — verify against source with `file:line`, and confirm firmware changes build via the PlatformIO CI (see the memory note on triggering it on this fork).
