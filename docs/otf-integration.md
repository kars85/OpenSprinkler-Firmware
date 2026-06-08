# OTF (OpenThings Framework) — firmware dependency contract

> **Consumer-side pointer.** The firmware's HTTP server and OpenThings Cloud remote-access layer are provided by the **OpenThings-Framework-Firmware-Library** (OTF), a compile-time dependency. The **canonical, source-grounded reference is `ARCHITECTURE.md` in the OpenThings-Framework-Firmware-Library repo** — read it before changing anything below. This file is the firmware-side record of the coupling so a change here (or an OTF version bump) doesn't silently break the other side. See also the [ecosystem map](ecosystem.md).

## What OTF provides to this firmware
On all **non-AVR** targets (ESP8266 / ESP32 / OSPi-Linux), OTF is the controller's entire web layer: the local HTTP server, the request router, and the optional OpenThings Cloud (OTC) WebSocket reverse-tunnel for remote access. AVR builds exclude it.

## Coupling points (what to check before changing)

| Coupling | Firmware site | OTF / contract |
|---|---|---|
| Dependency + version pin | `platformio.ini:24` (`OpenThingsIO/OpenThings-Framework-Firmware-Library @ ^0.2.0`) | bumping the major version can break the API below |
| Build gating | `USE_OTF` (`defines.h:177-178`) — defined for all non-AVR | OTF is excluded on AVR |
| Header / global handle | `OpenSprinkler.h:48,66,122` (`extern OTF::OpenThingsFramework *otf;`) | `OpenThingsFramework.h` |
| Instantiation (local vs cloud) | `OpenSprinkler.cpp:543/546` (ESP), `:751/754` (Linux) | constructors in `OpenThingsFramework.h:84,104,107` |
| Handler API | `OTF_PARAMS_DEF` = `const OTF::Request &req, OTF::Response &res` (`opensprinkler_server.cpp:35`) | `Request.h` / `Response.h` |
| Route registration | `otf->on(path, handler[, method])` + `urls[]` table (`opensprinkler_server.cpp:2334+`, `initialize_otf`) | `OpenThingsFramework::on` (`OpenThingsFramework.h:117`) |
| Loop servicing | `otf->loop()` (`main.cpp:689,697,711,762`) | must be called frequently (single-threaded poll) |
| Cloud status surface | `/jc` `otcs` = `otf->getCloudStatus()` (`opensprinkler_server.cpp:1261`); switch in `main.cpp:311-321` | `CLOUD_STATUS` enum (`OpenThingsFramework.h:46-55`) |
| Shared buffer | `ether_buffer` / `ETHER_BUFFER_SIZE` passed as OTF's header buffer | `HEADERS_BUFFER_SIZE` default 1024 (`OpenThingsFramework.h`) |
| OTC cloud config | `otc.en/token/server/port`, defaults `ws.cloud.openthings.io` (`defines.h:161-163`) | `/socket/v1?deviceKey=` tunnel |

## What can break, and how
- **Changing an OTF handler signature, `Request`/`Response` API, or `on()`** in the library breaks **every** web endpoint here (they all use `OTF_PARAMS_DEF`). Coordinate via the library's `ARCHITECTURE.md`.
- **Bumping OTF past `^0.2.0`** must be validated against the handler/`Request`/`Response` API; pin deliberately.
- **Changing `ETHER_BUFFER_SIZE`** alters the header/parse capacity OTF works with (it shares `ether_buffer`).
- **Note (security):** OTF's `wss`/TLS path is currently **not wired** (`connectSecure` is commented out in the library); the firmware passes `useSsl=false`, so the cloud link is plaintext `ws://`. Tracked in the library's `ARCHITECTURE.md` §8.

## Rule
Treat the OTF API as a contract: changes to the handler/`Request`/`Response` surface or the version pin require checking **both** this file and the library's `ARCHITECTURE.md`, and updating them together.

---
*Author note: OTF is maintained by the same author as OpenSprinkler (Ray Wang / OpenThingsIO), so the two evolve together — but the coupling is still explicit here to prevent silent breakage.*
