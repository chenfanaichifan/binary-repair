# 49 — M2 independent witness (Gate 4 packages, 2026-10-29)

**From:** M2 (GUI) · **Cross-person witness**, not M5's row and not a gate pass.

M2 unpacked its own copies of the packages from `for-M5-2026-10-29-v5.zip`
(SHA-256 `dbe766edb00b20bc52f9084db00edb7a0a22508400c13c68f4fbb9166c05a895`)
and reran the INTERFACE-v1 checker and SHA-256 checks. No producer row was
copied.

Checker identity:

- main `scripts/check_handoff.py` raw blob SHA-256
  `caeffc2e7342796c3323e629c0e5ff29ba131032ac635b78697b876c8d85afab`
- M3's kit checker was `5bbf9a38…6649`; both agree on PASS for the handoff
  packages below.

```bash
python <main>/scripts/check_handoff.py <pkg> --expect-from M3 --expect-to M5
sha256sum -c SHA256SUMS
sha256sum <pkg>.zip
```

## Observations

| Package | Zip SHA-256 | Checker | Internal sums | Witness observation |
|---|---|---|---|---|
| P3A v4 | `347e7d22cc741e2da539e756761afa28d09c739751a33ca5b9a6b22d2b6efa15` | **PASS** 25/25, sums `d9c33b42…0bcb` | 25/25 OK | candidate `c4a159…aa82`; V0/V1/V3 pass, V2/V4/V5 not_run; worker remains inconclusive |
| P3B v3 | `72d789c665fa2e7796b092b3c351a488472a68269549a5e709168dcf1020034b` | **PASS** 18/18, sums `8bec86e06e0266ef939822ef351a98438da82e8b79b114a7dd277e192b070ae7` | 18/18 OK after LF normalization of the sum file | candidate `63fcafa6…6d01`; source `a2e4ff8f…c90e`; jobwrap exit 0, uid 1003/caps 0/NNP 1/netns empty; audit pass; V3 6/6; still witness only, no gate pass |
| P4 package | `427dd71d3b94ca7b12dfce3a4031611f9bb6a0d7ce986d6d96fe9b6a762b2dd4` | **PASS** 15/15, sums `5c7ab9aa…fc3c` | 15/15 OK | native `manifest-compare.json` 6/6; derived cases marked `runner_native=false`; original/candidate ELF, before/after, snapshot/chain, raw revert and refreshed harness manifest missing; Gate 4 record remains DRAFT/NOT RUN |
| Gate5 A blocked | `74952fc4e4349992cae47835bbb2fd1851201cd5dde076f4accc334c5682b0a4` | not a handoff package | 1/1 OK | no jobwrap fixed-script mode; no PASS/FAIL; Gate 5 unsigned |

The `for-M5-v5` root `SHA256SUMS` verifies 4/4 OK.

## Boundary

M2 signs no gate pass, does not edit the M5 record's gate result, and does not
change Gate 3/4/5 status. Gate 4 remains **DRAFT / NOT RUN**. This row may be
inserted into the M5-owned Gate 4 record as the M2 witness row; M2 does not sign
the M5 Gate 4 row, M4 verifier row, or Lead approval.
