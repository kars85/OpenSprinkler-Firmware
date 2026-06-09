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
| `OS_FW_MINOR` | upstream | Minor/build revision (the number in parentheses). Tracks upstream; surfaced as `fwm`. |
| `OSF_FORK_ID` | fork | Constant fork channel identifier (`"kars85"` — the GitHub handle / repo owner). |
| `OSF_FORK_BUILD` | fork | Monotonic fork build counter, **relative to the current upstream base**. |

## Cadence rules

| Event | Action |
|-------|--------|
| Ship a new fork binary on the **same** upstream base | `OSF_FORK_BUILD++` |
| Rebase onto a **newer** upstream (e.g. upstream → 2.2.1(5)) | set `OS_FW_MINOR` (and `OS_FW_VERSION` if it moved) to match upstream, then **reset `OSF_FORK_BUILD` to 1** |
| Make a change that alters NVM/options data layout | bump `OS_FW_MINOR` **deliberately** (accepting divergence from upstream's number) — this is the *only* knob that should ever force a settings wipe |

## Why the fork counter does not affect the reset logic

`options_setup()` (`OpenSprinkler.cpp`) factory-resets only when the stored
`OS_FW_VERSION` integer differs from the running firmware, or the `DONE` marker file
is missing. `OSF_FORK_BUILD` is intentionally excluded: a fork rev must **not** wipe a
user's settings. Only a real data-structure change should, and that is gated on a
deliberate `OS_FW_MINOR` bump.

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
