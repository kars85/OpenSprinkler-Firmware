# Fork versioning scheme

This fork rebases onto upstream OpenSprinkler and layers its own changes on top.
Fork provenance lives in dedicated, additive markers; the numeric firmware fields
remain compatibility signals. In particular, `fwv` is the stored compatibility
epoch and must never be bumped merely to identify a fork build.

## Version string format

```
2.2.1(4)+kars85.3
└──┬──┘ └─┬──┘ └┬┘
   │      │     └─ fork release counter       (OSF_FORK_BUILD)
   │      └─────── fork provenance/channel    (OSF_FORK_ID)
   └────────────── compatibility epoch + reset-free capability (OS_FW_VERSION / OS_FW_MINOR)
```

At runtime the current firmware prints `OpenSprinkler 221(4)+kars85.3` — see
`fork_version_string` in `main.cpp`.

## The macros (`defines.h`)

| Macro | Owner | Meaning |
|-------|-------|---------|
| `OS_FW_VERSION` | upstream / storage contract | Compatibility/storage epoch integer (`221` = 2.2.1), surfaced as `fwv`. It is the **only version field checked by the settings-reset path**. Never change it for a fork feature or build identifier. |
| `OS_FW_MINOR` | upstream + fork compatibility | Reset-free minor/capability revision (the number in parentheses), surfaced as `fwm`. `iopts_load()` refreshes it after loading settings; it does not participate in reset detection. |
| `OSF_FORK_ID` | fork | Constant fork channel identifier (`"kars85"` — the GitHub handle / repo owner). |
| `OSF_FORK_BUILD` | fork | Monotonic fork release counter, **relative to the current compatibility base**. It is provenance, not a capability signal. |

## Cadence rules

| Event | Action |
|-------|--------|
| Ship a behavior-only fork binary with no new consumer-visible capability | `OSF_FORK_BUILD++` only. |
| Add a backward-compatible API field or behavior that consumers must detect | Raise `OS_FW_MINOR` to the next documented capability level and bump `OSF_FORK_BUILD`; do **not** change `OS_FW_VERSION`. Consumers must also require `fwf` identity and field presence. The current floor is `2214`; the first future fork capability floor is `2215`. |
| Rebase onto a newer upstream | Adopt the upstream `OS_FW_VERSION`; set `OS_FW_MINOR` no lower than the upstream revision or any already-shipped fork capability floor, document the result, and reset `OSF_FORK_BUILD` to `1`. |
| Make an incompatible NVM/options layout change | Treat it as a new storage epoch: design a migration or an explicit reset plan before deliberately changing `OS_FW_VERSION`. `OS_FW_MINOR` never forces a wipe. |

## Build history

| Build | Change |
|-------|--------|
| `kars85.1` | Initial fork build on upstream base 2.2.1(4): Tier 1 (markers, banner, gc-sections-safe retention, version-stamped CI artifact) + Tier 2 (read-only `/jo` `fwf`). |
| `kars85.2` | Weather URL transport fix (`weather.cpp`): a scheme-less URL with an explicit non-443 port now defaults to plain HTTP, so a bare local weather URL like `10.10.100.3:3000` no longer silently defaults to HTTPS and fails the TLS handshake. Explicit `https://` and port 443 still select TLS. Supersedes `kars85.1` (includes all of its content). |
| `kars85.3` | Internal: extract the URL transport parser into shared `OpenSprinkler::parse_url_transport()` (behavior-preserving; `weather.cpp` reuses it). Embedded-page UX: `/su` gains `<label>`s, `aria-describedby` inline help (weather-URL scheme guidance, UI-Source explanation), and cross-links to `/update`/home. OTC/IFTTT/station callers deliberately left as-is (external-contract risk). No observable runtime behavior change vs `kars85.2`. |

## Why the fork counter does not affect the reset logic

`options_setup()` (`OpenSprinkler.cpp`) factory-resets only when the stored
`IOPT_FW_VERSION` differs from the running `OS_FW_VERSION`, or the `DONE` marker file
is missing. Neither `OS_FW_MINOR` nor `OSF_FORK_BUILD` participates. After a normal
load, `iopts_load()` overwrites the in-memory `fwm` value with the running
`OS_FW_MINOR`, which makes `fwm` safe for additive capability gates without wiping
settings.

> **Footgun to be aware of:** `fwv` and `fwm` describe compatibility, not provenance.
> They cannot prove that a binary is this fork, even when a fork capability happens to
> use a distinct `fwm`. Use `fwf` (and the boot banner/artifact name) for fork identity.
> Flashing between compatible fork and official builds does not auto-reset settings.

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
  [`external-contracts.md`](external-contracts.md) §1b and the API reference.
