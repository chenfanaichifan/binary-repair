# dist — current handoff artifacts (2026-10-22)

Old v2–v5 kits were removed from `main` to avoid stale-contract downloads. They
remain recoverable from git history / `archive/2026-10-22/*` tags.

| File | SHA-256 | Purpose |
|---|---|---|
| `m5-routeb-kit-2026-10-22-v6.zip` | `499f510c9fda660826ea6b7f5b1969839334ba7cd63cc0c975a1e4ca951e4b1d` | Gate 4 kit for `toolchain-v4-ready`; canonical contract `24bfe568…4e37` |
| `m5-routea-c4a159-2026-10-22.zip` | `957d73d4284a4e5ced27de451bacdfe8956751232bd4a1fa5aa6454dccdc108e` | Route A c4a159 candidate handoff |
| `m5-delivery-2026-10-22.zip` | `2b0f8364bb940f67261ba59b01209f2ad490c5fb16bd57beb9307a77736830ca` | M5 consolidated handoff |
| `M3-120-cwe416-v3-handoff-2026-11-05.zip` | `e90c82de89c6c0d6700d8056b54b55cd84a1549946066ce84b8581a7bbb19ec7` | M3: record 120 + 9 evidence files + the CWE416 no-input fixture, own `INDEX.md` and `SHA256SUMS` |
| `M3-121-cwe416-closeout-2026-11-05.zip` | `486c7b0575546bdc157ca22e795f58d5f978e489d40b435d368735ab4d04e2e8` | M3: record 121 + 11 evidence files + the fixture as closed out (the current tree) |

Notes:

- Two digest conventions live here. The 2026-10-22 and `p3b-fixed-c` manifests
  name the file as `dist/<name>.zip` and verify from the repository root; the
  2026-11-05 ones name it bare and verify with `cd dist` first. Check the first
  line of a manifest before choosing:
  `head -1 <manifest>` then `sha256sum -c <manifest>` from the matching directory.
- `*.sha256` is pinned to `-text` in `.gitattributes`. Without it
  `core.autocrlf=true` rewrites the trailing LF to CRLF and `sha256sum -c` goes
  looking for a file whose name ends in a carriage return.
- v6 kit runner hash is recorded in `m5-routeb-kit-v6-ERRATA.md`; the README
  inside the zip prints an older runner hash.
- v5 and older are withdrawn because they embed the stale contract
  `1a0ad101…`; do not use them for formal Gate 4.
- Runtime attempt/evidence outputs belong under `var/jobs/...`, not `dist/`.
