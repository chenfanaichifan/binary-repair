# dist — current handoff artifacts (2026-10-22)

Old v2–v5 kits were removed from `main` to avoid stale-contract downloads. They
remain recoverable from git history / `archive/2026-10-22/*` tags.

| File | SHA-256 | Purpose |
|---|---|---|
| `m5-routeb-kit-2026-10-22-v6.zip` | `499f510c9fda660826ea6b7f5b1969839334ba7cd63cc0c975a1e4ca951e4b1d` | Gate 4 kit for `toolchain-v4-ready`; canonical contract `24bfe568…4e37` |
| `m5-routea-c4a159-2026-10-22.zip` | `957d73d4284a4e5ced27de451bacdfe8956751232bd4a1fa5aa6454dccdc108e` | Route A c4a159 candidate handoff |
| `m5-delivery-2026-10-22.zip` | `2b0f8364bb940f67261ba59b01209f2ad490c5fb16bd57beb9307a77736830ca` | M5 consolidated handoff |
| `M3-t30-rebuild-evidence-2026-11-05.zip` | `968fb8d9a80f991567c0cdd1e082a844556ef6405ee366786e2b3b7a010fcbd5` | M3: record 118 evidence (T30 second-window rebuild), 11 files + inner `SHA256SUMS` |
| `M3-118-handoff-2026-11-05.zip` | `6e17f40b535e2063256b6fa47419295ed4f1628fe10485457fb9c29bf3ce8489` | M3: record 118 + its 11 evidence files + `INDEX.md`, one file, own `SHA256SUMS` |

Notes:

- v6 kit runner hash is recorded in `m5-routeb-kit-v6-ERRATA.md`; the README
  inside the zip prints an older runner hash.
- v5 and older are withdrawn because they embed the stale contract
  `1a0ad101…`; do not use them for formal Gate 4.
- Runtime attempt/evidence outputs belong under `var/jobs/...`, not `dist/`.
