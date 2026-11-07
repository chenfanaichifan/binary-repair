# M1 real P1 controller run (2026-11-07)

Source: `M3-P1-real-guest-window-2026-11-07.zip`
sha256: `6d2ef8f3378582a88b8701402a707a0a2161c24fd192b0e8f61507cf27a329d0`

```
job      3cde2df6164d4b8fbf9c8b75b93b4a37
run      8d7a422830794a68bd50709716c62109
route A  046ea49a23ab4ff59e98d6247ca4c726
route B  119f3ffa22c54e6e84e0c313e1055012
```

Route B is the real P1 `a1.routeb` bundle copied to the attempt's canonical
`.routeb` path; it carries V0/V1/V3 passed and V2/V4/V5 not_run.

Route A is a generic result for the same P1 package: candidate identity artifact
only, all six gates `not_run`. The P1 archive contains no Route A execution, so
this does not copy Route B and does not claim a Route A pass.

The host worker invoked `attempt_driver`; no ELF was executed. `p2_acceptance.py`
exited 0 with `synthetic=false`; verdict is `inconclusive /
required_check_not_run / identity` (Route A V0 not_run). V5 remains not_run, so
the second guest replay is still pending.

## V2 actual value

P1 Route A and Route B both have **V2 = not_run** (no V2 artifact in the P1
archive). This is not the 124 result: 124's V2 is the separate 5/5 static
interface check. Do not copy 5/5 onto P1.
