# OTF (OpenThings Framework) — firmware dependency contract

> **Consumer-side pointer.** The firmware's HTTP server and OpenThings Cloud remote-access layer are provided by the **OpenThings-Framework-Firmware-Library** (OTF), a compile-time dependency. The **canonical, source-grounded reference is `ARCHITECTURE.md` in the OpenThings-Framework-Firmware-Library repo** — read it before changing anything below. This file is the firmware-side record of the coupling so a change here (or an OTF dependency-resolution change) doesn't silently break the other side. See also the [ecosystem map](ecosystem.md).

## What OTF provides to this firmware
On the firmware's supported OTF targets — **ESP8266, OSPi/Linux, and the native DEMO test build** — OTF is the controller's entire web layer: the local HTTP server, request router, and optional OpenThings Cloud (OTC) WebSocket reverse tunnel. AVR builds exclude it. The OTF library itself supports ESP32, but this firmware has no ESP32 PlatformIO environment or hardware branch; ESP32 is not a supported firmware target today.

## Coupling points (what to check before changing)

| Coupling | Firmware site | OTF / contract |
|---|---|---|
| Dependency + version constraint | `platformio.ini:24` (`OpenThingsIO/OpenThings-Framework-Firmware-Library @ ^0.2.0`) | changing the resolved revision or compatibility range can break the API below |
| Build gating | `USE_OTF` (`defines.h:190-196`) — enabled outside `OS_AVR` | OTF is excluded on AVR |
| Header / global handle | `OpenSprinkler.h:48,66,122` (`extern OTF::OpenThingsFramework *otf;`) | `OpenThingsFramework.h` |
| Instantiation (local vs cloud) | `OpenSprinkler.cpp:533-548` (ESP8266), `:740-759` (Linux/DEMO) | constructors in `OpenThingsFramework.h` |
| Handler API | `OTF_PARAMS_DEF` = `const OTF::Request &req, OTF::Response &res` (`opensprinkler_server.cpp:35`) | `Request.h` / `Response.h` |
| Route registration | `otf->on(path, handler[, method])` + `urls[]` table (`opensprinkler_server.cpp:2334+`, `initialize_otf`) | `OpenThingsFramework::on` (`OpenThingsFramework.h:117`) |
| Loop servicing | `otf->loop()` (`main.cpp:709,717,731,782`) | must be called frequently (single-threaded poll) |
| Cloud status surface | `/jc` `otcs` = `otf->getCloudStatus()` (`opensprinkler_server.cpp:1269`); display switch in `main.cpp:324-341` | `CLOUD_STATUS` enum (`OpenThingsFramework.h:46-55`) |
| Shared buffer | `ether_buffer` / `ETHER_BUFFER_SIZE` passed as OTF's header buffer | `HEADERS_BUFFER_SIZE` default 1024 (`OpenThingsFramework.h`) |
| OTC cloud config | `otc.en/token/server/port`, defaults `ws.cloud.openthings.io` (`defines.h:161-163`) | `/socket/v1?deviceKey=` tunnel |

## What can break, and how
- **Changing an OTF handler signature, `Request`/`Response` API, or `on()`** in the library breaks **every** web endpoint here (they all use `OTF_PARAMS_DEF`). Coordinate via the library's `ARCHITECTURE.md`.
- **Changing the OTF constraint or resolved revision** must be validated against the handler/`Request`/`Response` API and recorded deliberately.
- **Changing `ETHER_BUFFER_SIZE`** alters the header/parse capacity OTF works with (it shares `ether_buffer`).
- **Note (security):** OTF's `wss`/TLS path is currently **not wired** (`connectSecure` is commented out in the library); the firmware passes `useSsl=false`, so the cloud link is plaintext `ws://`. Tracked in the library's `ARCHITECTURE.md` §8.

## Rule
Treat the OTF API as a contract: changes to the handler/`Request`/`Response` surface, version constraint, or resolved revision require checking **both** this file and the library's `ARCHITECTURE.md`, and updating them together.

---
*Author note: OTF is maintained by the same author as OpenSprinkler (Ray Wang / OpenThingsIO), so the two evolve together — but the coupling is still explicit here to prevent silent breakage.*
