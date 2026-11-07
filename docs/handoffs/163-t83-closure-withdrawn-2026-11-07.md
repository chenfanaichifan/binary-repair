# 163 — T8.3 closure withdrawn after V2 gate reconciliation

Date: 2026-11-07  
Status: correction; supersedes the closure claim in record 150

M1's final P2/P1 review and M4's rehash agree that P1/P2 V2 is `not_run`.
The earlier 124 result used the ingest-side 5/5 producer observation as a gate;
that is not the same as the attempt gate. Record 150's `T8.3 COMPLETE` is
withdrawn until V2 is wired and re-verified on the final head.

```text
T8.3: BLOCKED
124: inconclusive / required_check_not_run / symbolic
V4 marker: retained as verifier evidence, not a 124 gate promotion
V2: not_run in P1/P2 controller snapshots
```

The M4 marker archive remains valid as an independent V4 artifact. It does not
by itself make 124 success while V2 is not a gate.

No code, tag, merge or live-success claim is made here.
