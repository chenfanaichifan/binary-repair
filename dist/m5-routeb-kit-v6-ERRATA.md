# v6 kit runner hash erratum

- v6 zip: `dist/m5-routeb-kit-2026-10-22-v6.zip`
- v6 zip SHA-256 unchanged: `499f510c9fda660826ea6b7f5b1969839334ba7cd63cc0c975a1e4ca951e4b1d`
- **canonical runner:** `routeb/gate4_runner.sh` inside v6 and on main
  - SHA-256 `515c4d609495dea723c6fe6ff9e55b34fca078a3bf450770ebb3c744f07bd357`
  - size 6,507 B
- The v6 zip's README.md mistakenly prints the older `e49a8879…` value. That value
  is stale. Do **not** use it for the formal record.
- The zip is intentionally not rebuilt, to preserve the downloaded/verified
  `499f510c…` hash. Formal Gate 4 records the actual runner hash `515c4d60…`.
