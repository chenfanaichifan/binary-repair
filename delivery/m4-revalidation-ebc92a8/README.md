# M4 revalidation packet — ebc92a8

Prepared by M1/M5 for M4 review; not a substitute for M4's signature.

```text
target: ebc92a8027632f51869bdd3bbc3f6360ee607183
124:
  V0-V5 passed via attempt_writer (v2-interface.json, M4 marker, V5 evidence)
  test_cwe416_124_v4_rerun.py passed
P1:
  finished two-route job, p2 exit 0, synthetic=false
  verdict inconclusive
  V2/V4 not_run; V5 passed
  test_p1_guest_bundle.py passed
```

The P1 snapshot and p2 output are included. M4 must independently rehash and
accept; this packet does not write any M4 signature.
