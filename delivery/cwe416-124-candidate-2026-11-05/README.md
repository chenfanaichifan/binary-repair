# CWE416 candidate 124 — controller-ingest package

Source: M3 handoff `M3-124-cwe416-candidate-handoff-2026-11-05.zip`
(top-level sha256 `58ed53401dbcb7c17349d19ce3989813a50a2f2072ee7efde675e6e60523e3cc`)
and record 124.

- original: `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9`
- candidate: `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0`
- edit: 5 bytes at file offset 4869, `call free@plt` -> `nop; nop; nop; nop; nop`
- fixture contract: v3 `input_mode: "none"`, canonical hash
  `c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c`

## Controller ingest result

Created as a normal controller job, approved with the 120 fixture contract, then
ingested as a Route B bundle:

```
V0 passed   V1 passed   V2 not_run   V3 passed   V4 not_run   V5 passed
attempt outcome: inconclusive (required_check_not_run)
obligations: behaviour/identity/reproducibility/structure passed;
             interface and symbolic not_run
```

The V3 1/1 result is real, but it is not a success: V2 and V4 remain `not_run`,
so the attempt is `inconclusive`, not `success_within_scope`.

V4 is `not_run` because there is **no reviewed solver-accounting harness**; the
guest does have angr 10.0.4.post1 and z3 5.1.0. This is a harness gap, not an
engine-availability limitation.
This package does not claim a gate promotion or T8.3 relief.
