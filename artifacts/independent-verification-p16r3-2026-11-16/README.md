# P16-R3 independent verification (2026-11-16)

The benchmark verifier used a real `patch-plan` replay, PT_LOAD-backed cave ABI
mapping and the external PoC oracle. Results for 10 benchmark case records:

- 7 independently verified;
- 1 rejected (CWE-121 security/behavior);
- 2 `ARTIFACT_MISSING` (CWE-787, CWE-134 candidate artifacts are not present in
  the selected run directories).

No generator gate is used in the decision. The two missing artifacts are
reported separately and are not counted as model failures in this evidence.
