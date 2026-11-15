# Independent benchmark verification (2026-11-16)

The existing byte-level independent verifier was applied to 10 candidate
records: 6 independent **verified**, 1 rejected (CWE-121 security semantics),
3 not_run (missing candidate artifacts for CWE-122/CWE-787/CWE-134 in the
selected run dirs).

The verifier decision is derived from raw original/candidate bytes, action
replay (including an explicit `allow_resize` append path), container/ABI
checks, and a real external PoC oracle.  The generator gate is recorded only
for comparison, never used in the decision.

This is a first unified-verification pass, not yet 8/8 complete.
