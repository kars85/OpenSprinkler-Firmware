# Weather Contract

Firmware repo role: **CONSUMER**  
Weather service role: **PRODUCER**

This document is the firmware-side counterpart to the producer-owned contract in `OpenSprinkler-Weather/docs/firmware-integration-requirements.md`. The producer wire format is canonical there and should be guarded there by `test/firmware-contract.spec.ts`. This document records the consumer constraints and parser behavior that the producer must preserve for existing firmware builds.

## Scope

The firmware weather callback is a flat, top-level key pull over an `&`-delimited response, not a general JSON document parser. `getweather_callback` peels the HTTP header, scans to the first `&`, then repeatedly pulls known keys with `findKeyVal` (`weather.cpp:54-61`, `weather.cpp:155-157`, `opensprinkler_server.cpp:148-206`).

## Hard Constraints On The Producer

1. `rawData` value length must be `<= 319` bytes (equivalently `< TMP_BUFFER_SIZE` = `< 320`).
   Reason: `wt_rawData` is only `TMP_BUFFER_SIZE` bytes (`weather.cpp:39`, `defines.h:31`). `findKeyVal(..., TMP_BUFFER_SIZE, ...)` copies up to `maxlen-1 = 319` value bytes and keeps the value only if the next character is a delimiter; a value of exactly `319` bytes is accepted, but a value of `320`+ bytes is silently discarded by resetting `found=0` (`weather.cpp:137-139`, `opensprinkler_server.cpp:188-205`).
2. The full HTTP response must fit the platform `ETHER_BUFFER_SIZE`.
   AVR and ESP8266 builds cap the receive buffer at `2048` bytes; OSPi/Linux builds use `16384` bytes (`defines.h:359`, `defines.h:385`, `defines.h:474`, `defines.h:497`). `send_http_request` reads no more than `ETHER_BUFFER_SIZE` bytes before invoking the callback (`OpenSprinkler.cpp:2083-2117`). That cap applies before header peeling, so headers count too (`weather.cpp:155-157`).
3. AVR producer endpoints must be plain HTTP.
   AVR builds do not enable HTTPS support (`defines.h:175-180`). The AVR weather path strips `http://` or `https://` text but still calls the non-TLS request path (`weather.cpp:189-194`, `weather.cpp:227-228`). In practice, AVR-compatible producer endpoints must be reachable over plain HTTP.

## Parser Behavior

The consumer only pulls these top-level keys today: `errCode`, `scale`, `restricted`, `sunrise`, `sunset`, `eip`, `tz`, `rd`, `rawData`, and `scales` (`weather.cpp:65-149`).

- `errCode` is checked first. `scale` and `scales` are only applied when `wt_errCode == 0` (`weather.cpp:65-72`, `weather.cpp:143-149`).
- Unknown top-level keys are tolerated because the parser ignores anything it never asks for, but they still consume scarce response bytes (`weather.cpp:65-149`, `opensprinkler_server.cpp:148-206`).
- `rawData` is treated as an opaque blob: firmware copies it into `wt_rawData` and later exposes it through `/jc` as `wtdata`; it does not parse nested structure out of that field (`weather.cpp:137-139`, `opensprinkler_server.cpp:1273-1283`).
- Consumer-side guidance inferred from that behavior: new structured producer data should ride inside the `rawData` JSON blob, not as new top-level fields. That preserves the fixed top-level parser while still allowing producer evolution.

## Watering Level Semantics

`scale=0` already means "do not water" with no firmware change required. The weather callback accepts `scale` in the range `0..250` and stores it as `IOPT_WATER_PERCENTAGE` (`weather.cpp:72-79`). During scheduling, station run times are multiplied by `wl / 100`, so `wl == 0` reduces all durations to zero and the program is skipped (`main.cpp:886-943`).

## Restricted Gap

Firmware has a complete top-level `restricted` path today:

- The parser reads `restricted` into `wt_restricted` (`weather.cpp:82-86`).
- Scheduling forces `wl = 0` when `wt_restricted > 0` (`main.cpp:887-900`).
- `/jc` exposes the state as `wtrestr` (`opensprinkler_server.cpp:1273-1283`).
- Skipped-program notifications include the restriction bit and can label the skip as weather-restriction-driven (`main.cpp:939-943`, `notifier.cpp:375-407`).

Current cross-repo gap: if the producer does not emit top-level `restricted`, restriction reaches the controller only through `scale=0`. Watering still skips correctly, but firmware cannot label the skip as a restriction or surface `wtrestr`/restriction-specific notifications.

## Dormant `scales` Capability

Firmware still supports a 14-day multiday `scales` payload:

- Capacity is `MAX_N_MD_SCALES = 14` (`weather.h:35`).
- The callback parses top-level `scales` when `errCode == 0` (`weather.cpp:141-147`).
- Parsed entries are stored in `md_scales` and counted in `md_N` (`weather.cpp:288-311`).
- Interval programs can consume those historical values during scheduling (`main.cpp:891-899`).
- `/jc` exposes the active array as `wls` (`opensprinkler_server.cpp:1289-1296`).

The OpenSprinkler-Weather service emits no top-level `scales` key today (verified: no producer code path builds it; only prose comments, MQTT config, and tests mention "scales"). With nothing emitted, `md_N` stays `0` (`main.cpp:1226-1229`) and the consumer branch is unreachable (`main.cpp:892` requires `mda == 100 && prog.type == PROGRAM_TYPE_INTERVAL && md_N > 0`).

### Decision: KEEP (reserved) — do not retire

The legacy watering response is a frozen, additive-only public API; removing a field is a subtractive, breaking change that would require a coordinated ordered cross-repo deletion (producer contract first, then the firmware consumer path) and would break any self-hosted or forked weather service that still emits `scales`. The dormant firmware path is guarded by `md_N > 0`, so it carries no runtime cost or risk while the field is absent. The net benefit of retiring (deleting a few lines of inert code) does not justify the coordination cost or the compatibility break.

Consequences of KEEP:
- The producer contract reserves the top-level `scales` field and documents the 14-entry cap (`MAX_N_MD_SCALES = 14`); the service may begin emitting it additively in the future without a firmware change.
- The firmware retains the parse/store/schedule/`wls` path unchanged.

Revisit retirement only if both sides agree to a coordinated, ordered change AND it is confirmed that no deployed or third-party producer emits `scales`.

## Field Compatibility Matrix

| Field | Status | Firmware behavior |
| --- | --- | --- |
| `errCode` | required | Gates success handling and whether `scale`/`scales` are applied; `0` updates `checkwt_success_lasttime` (`weather.cpp:65-72`, `weather.cpp:143-149`). |
| `scale` | required | Accepts `0..250`; updates `IOPT_WATER_PERCENTAGE`; `0` skips watering without firmware changes (`weather.cpp:72-79`, `main.cpp:886-943`). |
| `restricted` | optional-parsed | Drives `wt_restricted`, `wtrestr`, restriction-aware skips, and restriction-specific notifications when present (`weather.cpp:82-86`, `main.cpp:887-900`, `opensprinkler_server.cpp:1273-1283`, `notifier.cpp:375-407`). |
| `sunrise` | optional-parsed | Updates `nvdata.sunrise_time` when `0..1440` and changed (`weather.cpp:88-95`). |
| `sunset` | optional-parsed | Updates `nvdata.sunset_time` when `0..1440` and changed (`weather.cpp:97-104`). |
| `eip` | optional-parsed | Updates stored external IP when changed (`weather.cpp:106-113`). |
| `tz` | optional-parsed | Updates timezone when `0..108`, saves options, and flags a weather update (`weather.cpp:115-124`). |
| `rd` | optional-parsed | Starts or stops rain delay based on the parsed hour count (`weather.cpp:127-135`). |
| `rawData` | optional-parsed | Stored opaquely in `wt_rawData` and surfaced through `/jc` as `wtdata`; size constrained by `TMP_BUFFER_SIZE` (`weather.cpp:137-139`, `opensprinkler_server.cpp:1273-1283`). |
| `scales` | dormant | Optional 14-entry multiday scale array for interval programs; still parsed and exposed, but only if the producer sends it (`weather.h:35`, `weather.cpp:141-147`, `weather.cpp:288-311`, `main.cpp:891-899`). |
| `rawData.*` | producer-owned | Nested structure is opaque to firmware. The producer may evolve this blob as long as the top-level `rawData` size contract is preserved (`weather.cpp:137-139`, `opensprinkler_server.cpp:1273-1283`). |

## Maintenance Contract

- The weather repo owns the canonical wire format.
- The firmware repo owns consumer constraints, parser behavior, and scheduling consequences.
- Both documents must be updated together whenever the producer contract changes.
- Contract changes land in the weather repo first, because the producer definition is canonical there.
- Any producer change that would alter top-level fields, field sizes, transport requirements, or `restricted` / `scales` behavior must be evaluated against the firmware parser paths cited above before release.
