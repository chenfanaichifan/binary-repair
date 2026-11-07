# P1 V5 second guest replay request (M3/VMer)

P1 `M3-P1-real-guest-window-2026-11-07.zip` measured V5 as `not_run`: the archive
has no build-twice replay evidence. To use P1 as a V5-complete bundle, M3/VMer
must run a second independent guest replay from the same package and return the
V5 evidence; M1 will not synthesize it and cannot execute ELF on the host.

## Requested evidence

- same `package/` identity:
  original `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9`
  candidate `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0`
  contract `8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b`
- second guest run with the fixed wrapper, same purpose/route/mode;
- V5 evidence for the build-twice / reproducibility check, with observed
  digests and commands;
- the resulting bundle SHA256SUMS and a fresh fingerprint;
- no `verified_by`, no outcome, no Gate promotion: M1 ingests only after
  evidence is present.

## Status

P1 V5 remains `not_run`. The current controller run is `inconclusive /
required_check_not_run / identity`; no success is claimed.
