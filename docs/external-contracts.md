# External-facing contracts — firmware identity, MQTT, OTC

> These are shapes the firmware exposes to **external consumers** (the weather service, the mobile/web app, MQTT integrations like Home Assistant, and the OpenThings Cloud) rather than to a single sibling repo. They were previously informal; this records them so a change here doesn't silently break a consumer. See the [ecosystem map](ecosystem.md) for the repo-to-repo couplings.

---

## 1. `fwv` — firmware-version negotiation

**What it is:** the firmware advertises its version so producers/clients can branch on capability.

- **Outbound to the weather service:** every weather poll includes `&fwv=<IOPT_FW_VERSION>` (`weather.cpp:167-171`). The value is `OS_FW_VERSION` (`221` = 2.2.1, `defines.h:34`).
- **Exposed in the controller API:** reported in `/jo` and `/ja.options`, and emitted as the only top-level field when a password check fails for `/jo` or `/ja`, so clients can detect the version pre-auth (`opensprinkler_server.cpp:388-420,1140-1150,2088-2112`). It is not a `/jc` field.

**Contract / who depends on it:** the OpenSprinkler-Weather service and the app may key behavior on `fwv` (older firmware can't parse newer response shapes — this is the safety valve behind the weather wire contract). 

**What breaks if changed:** removing/renaming `fwv` from the weather request or `/jo` blinds version-gating on both the service and app sides. **Rule:** keep sending `fwv` on weather calls and exposing it in `/jo`; if the response format changes in a way old firmware can't parse, the producer must gate on `fwv` (coordinate via `docs/weather-contract.md` ↔ weather `firmware-integration-requirements.md`).

---

## 1a. `fwm` — reset-free capability revision

**What it is:** the read-only minor/capability component paired with `fwv` in `/jo` and `/ja.options`. Unlike `fwv`, it is not checked by `options_setup()` and does not force a settings reset. Fork consumers use a documented `fwm` floor together with `fwf` identity and field presence; they never treat `fwm` alone as provenance.

---

## 1b. `fwf` — fork build identity *(this fork only)*

**What it is:** a read-only string that identifies which **fork build** is running. `fwv` and `fwm` describe compatibility and cannot prove provenance. Value is `OSF_FORK_TAG` = `"<OSF_FORK_ID>.<OSF_FORK_BUILD>"`, e.g. `"kars85.3"` (`defines.h`).

- **Exposed in the controller API:** reported as `fwf` in `/jo` (and `/ja`, which embeds the same options block) — emitted in the computed, non-stored field group alongside `dexp`/`mexp`/`hwt` (`opensprinkler_server.cpp` `server_json_options_main`). It is **not** an `iopts`/NVM value: `/co` has no `fwf` write path and skips the read-only version iopts, so `fwf` cannot trigger a device reset.
- **Not sent to the weather service.** `fwv` remains the only version field on weather polls; `fwf` is firmware/app-facing only.

**Contract / who depends on it:** consumers that want to tell a fork build apart from official firmware (e.g. an app surfacing the running build, or update tooling). Absent on official OpenSprinkler firmware — consumers must treat a missing `fwf` as "not this fork."

**What breaks if changed:** renaming/removing `fwf`, or changing the `"<id>.<build>"` shape, breaks any consumer keying on it. **Rule:** additive only; the tag format and the bump cadence are defined in [`fork-versioning.md`](fork-versioning.md). This is a fork-local field — it does **not** exist upstream, so do not assume official firmware will ever emit it.

---

## 2. MQTT — topic scheme & payload shapes

**Source:** `mqtt.cpp` (transport/topics) and `notifier.cpp` (`NOTIFY_*` event payloads).

**Topic scheme:**
- Configurable publish prefix `_pub_topic`, max `MQTT_MAX_TOPIC_LEN = 24` (`mqtt.cpp:80,97`); published topics are `<prefix>/<event>` (`_publish` builds `total_topic`, `mqtt.cpp:549/703`).
- **Availability:** `<prefix>/availability` (`MQTT_AVAILABILITY_TOPIC`, `mqtt.cpp:84`), **retained**, with online payload on connect (`mqtt.cpp:537/629`) and an **LWT** offline payload set via `mosquitto_will_set` (`mqtt.cpp:669`).

**Event payloads (JSON), from `notifier.cpp`:**

| Topic | Payload shape | Ref |
|---|---|---|
| `station/<sid>` (on) | `{"state":1[,"duration":<s>]}` | `notifier.cpp:211-216` |
| `station/<sid>` (off) | `{"state":0[,"duration":<s>][,"flow":<gpm>]}` | `notifier.cpp:233-246` |
| `program/<pid>` (run) | `{"state":1,"wl":<pct>}` | `notifier.cpp:382-385` |
| `program/<pid>` (skipped) | `{"state":"skipped","wtrestr":<0\|1>}` | `notifier.cpp:378-380` |
| sensor / rain-delay / weather / reboot | analogous `NOTIFY_*` payloads | `notifier.cpp` |

**Contract / who depends on it:** Home Assistant and other MQTT integrators subscribe to these topics and parse these exact JSON shapes.

**What breaks if changed:** renaming a topic, changing the prefix scheme, or altering a payload key (e.g. the `wtrestr` skipped-program field — note its labeling fix in issue #7) breaks downstream automations silently. **Rule:** treat topic names + payload keys as a public API; additive changes only; document changes here.

---

## 3. OTC — OpenThings Cloud remote access

**Config (`OTCConfig`, `OpenSprinkler.h:230-233`):** `en`, `token` (32 chars, `DEFAULT_OTC_TOKEN_LENGTH`), `server`, `port`. Two server profiles (`defines.h:161-164`):
- DEV: `ws.cloud.openthings.io:80` (plain `ws://`)
- APP: `cloud.openthings.io:443` (`https`)

**Two distinct OTC couplings:**

1. **Inbound tunnel (firmware ↔ OTF ↔ cloud):** OTF opens `/socket/v1?deviceKey=<token>` and the cloud relays HTTP requests to the controller via the `FWD:`/`RES:` framing (see OTF `ARCHITECTURE.md` §5 and [`otf-integration.md`](otf-integration.md)). Connection state is surfaced as `otcs` in `/jc` (`opensprinkler_server.cpp:1261`).
   - ⚠️ The tunnel is currently plaintext `ws://` (`useSsl=false`; OTF's `connectSecure` is unimplemented/disabled). The 32-char token transits in cleartext. Tracked as an OTF-repo issue.
2. **Outbound remote-station control (firmware → cloud forward API):** a `STN_TYPE_REMOTE_OTC` station (`defines.h:66`, `0x06`) actuates another controller through the cloud: the master sends `GET /forward/v1/<token>/cm?pw=&sid=&en=&t=` (`OpenSprinkler.cpp:2211`, case at `:1902`). The browser equivalent is `cloud.openthings.io/forward/v1/<token>`.

**Contract / who depends on it:** the OpenThings Cloud service (relay + forward API), the app's remote-access flow, and any controller configured with a remote-OTC station.

**What breaks if changed:** changing the `deviceKey` query param, the `/socket/v1` or `/forward/v1/<token>/cm` paths, or the `otc` config shape breaks remote access and remote-station chaining. **Rule:** these paths/params are a cloud-service contract — coordinate any change with the OpenThings Cloud service, not just the firmware.

---

*Companion to [`ecosystem.md`](ecosystem.md), [`weather-contract.md`](weather-contract.md), and [`otf-integration.md`](otf-integration.md). All claims verified against source with `file:line`.*
