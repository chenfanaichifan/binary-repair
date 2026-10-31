# 82 — Lead/M4 Gate5 re-hash result and successor split-chain decision

**From:** Lead / M4 (same operator; not human-independent)
**To:** M1, M3, M5, M4
**Date:** 2026-10-31 23:20 (Asia/Hong_Kong)
**Scope:** final re-hash on `origin/member-3-route-a` (`be11c5c`) and the
`90af91ef` → `0066973d` successor binary change.

## 1. Re-hash result

The sandbox blocks the MSYS `sha256sum.exe` with a signal-pipe error
(`Win32 error 5`), so an independent Python `hashlib.sha256` pass was used over
the exact manifests. This is the same SHA-256 algorithm; the binary tool must be
run in an unsandboxed shell for a literal `sha256sum -c` record.

| Manifest | Entries | Result | Manifest SHA-256 |
|---|---|---|---|
| Route A `SHA256SUMS` | 43 | **43/43 OK, 0 bad, 0 missing** | `0266933653e58546be09c9b633c0072a456dcc72f457ae627deb2b80424d1a71` |
| Route B `routeb-SHA256SUMS` | 43 | **43/43 OK, 0 bad, 0 missing** | `0eafc14bd1c35c8977b273c96ccf9a8b1361398d9ba349a32d91920f39837d19` |

Key hashes:

```
Route A probe       f39a0302…d146cb
Route A successor   90af91ef…ff20
Route A candidate   c4a159…aa82
Route A original    aa428157…8393
Route B probe       05d9a2cd…edb82
Route B successor   0066973d…9eee
Route B candidate   208574ab…6717
Route B tail file   e16ba161…25f3
```

Route B manifest is the same `0eafc14b…` root manifest as the accepted
`gate5b-evidence(1).zip`; Route B re-hash is accepted.

Route A branch manifest (`02669336…`) is the **sanitized feature-branch variant**
(M3 changed `gdb-probe.log` after the signed `51`). It is self-consistent but it
is **not** the signed Route A evidence. The authoritative Route A evidence remains
the signed main record: root `a193a749…d845`, `evidence/SHA256SUMS`
`05438764…ec8`, zip `371cdacd…be8c`. Do not merge the sanitized variant; do not
rewrite `51`'s R8.

## 2. Successor binary change decision

**Accepted: split-chain binding.**

- Route A evidence remains bound to `jobwrap-gate5` `90af91ef…ff20`, probe
  `f39a0302…d146cb`.
- Route B evidence is bound to `jobwrap-gate5` `0066973d…9eee`, probe
  `05d9a2cd…edb82`.
- The Route A probe blob is unchanged; the new binary adds the Route B mode.
- No Route A rerun is required for this submission. Recorded limitation: Route A
  was not re-executed under the new binary; each gate keeps its own bound binary.

If a future client requirement demands one binary binding all Gate 5 evidence, a
single Route A re-run under `0066973d` would be needed; it is not a blocker for
the current MVP acceptance and does not change Gate 5A PASS.

## 3. Final status

```
Gate 4: PASS
Gate 5 Route A: PASS (old successor 90af91ef)
Gate 5 Route B: PASS (new successor 0066973d)
V4: PASS (model-level, bound 64)
fixture: FROZEN (candidate scope)
full MVP acceptance: APPROVED with recorded limitations (record 81)
final tag: mvp-2026-10-31 authorized after merging records
```

## 4. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | M4 | 2026-10-31 | re-hash: Route B 43/43; Route A branch variant separated from signed main; split-chain accepted |
| Lead approval | Lead | 2026-10-31 | **split-chain accepted**; no Route A rerun required for this submission; same-person limitation |
