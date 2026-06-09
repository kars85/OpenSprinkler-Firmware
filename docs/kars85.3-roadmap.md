# kars85.3 + fork program roadmap

Derived from a planning pass (2026-06-09) over four fronts. **Destinations differ** — keep them separate.

| Front | Destination | Status |
|-------|-------------|--------|
| `parse_url_transport()` extraction | this repo | ✅ done (`e24d0c6`) — behavior-preserving |
| Embedded-page UX (Phase 0) | this repo | ✅ `/su` help + labels + cross-links (this branch) |
| `parse_url_transport()` caller-rewiring | this repo | ⏸ **deferred** — see below |
| Upstream app issues (6 drafts) | OpenSprinkler-App (upstream) | staged in the app-fork project |
| Self-hosted app fork | **new separate project** | spike-first; staged separately |

## Firmware (this repo)

**Shipping as `kars85.3`:**
- Shared `OpenSprinkler::parse_url_transport(host, &port, &use_ssl)` (non-AVR), reused by `weather.cpp` with zero behavior change.
- `/su` embedded-page UX: `<label for>`, `aria-describedby` inline help (weather-URL scheme guidance — the `http://` gotcha; UI-Source explanation), and cross-links to `/update` and home.
- Bump `OSF_FORK_BUILD` → 3 at release time.

**Deliberately NOT done (contract risk — per `CLAUDE.md` coordination rule):**
- Rewiring OTC tunnel / OTC remote-station / IFTTT to the shared helper. These touch externally-observed transport (OTC cloud `ws://`, IFTTT webhook). The helper would *change* their transport selection. Leave as-is; the helper is available if a future, contract-reviewed change wants it. HTTP(S)/Remote-IP stations are also left as-is (explicit type selector is the contract; LAN has no scheme).
- Embedded-UX Phase 1 (a standalone `html/su.html` rewrite) — larger surface + gzip-gate sensitive; its own PR.

## Upstream — OpenSprinkler-App issues (no firmware coupling)
Six drafts (System Diagnostics interpretation, Last-Request timestamp/DST bug, feature discoverability, Multi-Day Levels empty-state, "Weather Restri." label, PWS attribution). The controller's `/jc` data is per-spec; these are app-side presentation. Drafts live in the app-fork project's `docs/`.

## Self-hosted app fork (separate project)
A fork of `OpenSprinkler/OpenSprinkler-App`, repointed via the firmware's existing `SOPT_JAVASCRIPTURL` (`/cu?jsp=...`) — **no firmware change required**. Sequenced spike-first: (1) fork + local dev, (2) **validate the `jsp` repoint loop on test hardware before writing any helper code**, (3) build the novice context-helper layer, (4) hosting + CI + rollback runbook. Largest/least-certain scope; intentionally last and off the firmware critical path.
