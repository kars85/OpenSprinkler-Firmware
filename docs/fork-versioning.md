# Fork versioning scheme

This fork rebases onto upstream OpenSprinkler and layers its own changes on top.
To keep fork builds distinguishable from official firmware **without** breaking
upstream compatibility, the fork identity lives in dedicated, additive markers —
never by repurposing the upstream version numbers.

## Version string format

```
2.2.1(4)+kars85.1
└──┬──┘ └─┬──┘ └┬┘
   │      │     └─ fork build counter  (OSF_FORK_BUILD)
   │      └─────── fork channel id      (OSF_FORK_ID)
   └────────────── exact upstream base this fork is rebased onto (OS_FW_VERSION / OS_FW_MINOR)
```

At runtime the firmware prints `OpenSprinkler 221(4)+kars85.1` (the raw integer form of
the upstream base) — see `fork_version_string` in `main.cpp`.

## The macros (`defines.h`)

| Macro | Owner | Meaning |
|-------|-------|---------|
| `OS_FW_VERSION` | upstream | Major version integer (221 = 2.2.1). **Drives the device-reset check** and the `/jo` API (`fwv`). Never edit except to match upstream. |
| `OS_FW_MINOR` | upstream | Minor/build revision (the number in parentheses). Tracks upstream; surfaced as `fwm` and copied into the loaded option array, but **is not compared by the device-reset check**. |
| `OSF_FORK_ID` | fork | Constant fork channel identifier (`"kars85"` — the GitHub handle / repo owner). |
| `OSF_FORK_BUILD` | fork | Monotonic fork build counter, **relative to the current upstream base**. |

## Cadence rules

| Event | Action |
|-------|--------|
| Ship a new fork binary on the **same** upstream base | `OSF_FORK_BUILD++` |
| Rebase onto a **newer** upstream (e.g. upstream → 2.2.1(5)) | set `OS_FW_MINOR` (and `OS_FW_VERSION` if it moved) to match upstream, then **reset `OSF_FORK_BUILD` to 1** |
| Make a change that alters NVM/options data layout | coordinate a new persisted-storage epoch and bump `OS_FW_VERSION` (or add an explicit migration/reset path). Changing `OS_FW_MINOR` alone does **not** force a settings wipe. |

## Build history

| Build | Change |
|-------|--------|
| `kars85.1` | Initial fork build on upstream base 2.2.1(4): Tier 1 (markers, banner, gc-sections-safe retention, version-stamped CI artifact) + Tier 2 (read-only `/jo` `fwf`). |
| `kars85.2` | Weather URL transport fix (`weather.cpp`): a scheme-less URL with an explicit non-443 port now defaults to plain HTTP, so a bare local weather URL like `10.10.100.3:3000` no longer silently defaults to HTTPS and fails the TLS handshake. Explicit `https://` and port 443 still select TLS. Supersedes `kars85.1` (includes all of its content). |
| `kars85.3` | Internal: extract the URL transport parser into shared `OpenSprinkler::parse_url_transport()` (behavior-preserving; `weather.cpp` reuses it). Embedded-page UX: `/su` gains `<label>`s, `aria-describedby` inline help (weather-URL scheme guidance, UI-Source explanation), and cross-links to `/update`/home. OTC/IFTTT/station callers deliberately left as-is (external-contract risk). No observable runtime behavior change vs `kars85.2`. |

## Why the fork counter does not affect the reset logic

`options_setup()` (`OpenSprinkler.cpp`) factory-resets only when the stored
`OS_FW_VERSION` integer differs from the running firmware, or the `DONE` marker file
is missing. `OSF_FORK_BUILD` is intentionally excluded: a fork rev must **not** wipe a
user's settings. `OS_FW_MINOR` is also absent from this comparison; after loading the
stored options, firmware overwrites the in-memory `IOPT_FW_MINOR` value with the
compiled `OS_FW_MINOR`. Only a coordinated persisted-data compatibility change should
use a new `OS_FW_VERSION` storage epoch or an explicit migration/reset path.

> **Footgun to be aware of:** because the fork keeps `OS_FW_VERSION`/`OS_FW_MINOR`
> identical to the upstream base, a device cannot distinguish a fork build from
> official firmware by `fwv`/`fwm` alone. Flashing between fork and official builds of
> the same base will therefore *not* auto-reset settings even though the binaries
> differ. Use the fork markers (boot banner / artifact name) to tell them apart.

## Git tags

Refname-safe form (no parentheses): `fw-<base>-<id><build>`, e.g. `fw-2.2.1.4-kars85.1`.

## Tiers

- **Tier 1 (implemented):** macros + boot banner (`fork_version_string`, printed in
  `do_setup()`). The string is retained in every build — including release builds where
  `ENABLE_DEBUG` is off and the banner print compiles away — via a **live reference**:
  `do_setup()` does a `volatile` store into `fork_version_keepalive`. `__attribute__((used))`
  alone is insufficient because it doesn't set `SHF_GNU_RETAIN`, so `-fdata-sections` +
  `--gc-sections` (the ESP8266/AVR default link) could otherwise reclaim the unreferenced
  string. Zero external-contract impact.
- **Tier 2 (implemented):** the fork tag (`OSF_FORK_TAG`, e.g. `kars85.1`) is exposed as
  a read-only `fwf` field in the `/jo` options JSON (and `/ja`) so apps/integrations can
  detect the fork at runtime. It is emitted in the computed, non-stored field group
  (`opensprinkler_server.cpp` `server_json_options_main`), so it never touches NVM and
  cannot trigger a reset. Additive and fork-local; documented in
  [`external-contracts.md`](external-contracts.md) §1a and the API reference.
