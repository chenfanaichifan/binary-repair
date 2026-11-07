# CWE416 no-input Route A kit (2026-11-07)

## Candidate

Move the read before free by swapping two call targets:

```text
0x401305  call free@plt   -> call printLine
0x401311  call printLine  -> call free@plt
```

This is the contract's authorized edit 1 ("Move the read ... before free()").
No added code, no segment/import change, size unchanged. It is independent of
the Route B candidate `46d16e99...` (which NOPs the free).

## Guest steps

1. Copy kit into the guest; run:
   ```sh
   python3 patch_routea.py --original original.elf --out candidate.elf --report routea-patch.json
   ```
2. Record candidate hash and compare with `routea-patch.json`.
3. Package as Route A:
   - `package.json` route `route_a`, purpose `repair`, input_mode `none`, run_manifest true,
     original/candidate/contract/tests paths, expected.original_sha256,
     expected.candidate_sha256 (from step 2), expected.contract_sha256;
   - `tests/invalid.json` is currently required by `run_job.py` route_a even for
     input_mode=none. If absent, the executor rejects the package; this is a
     known M1/M5 schema gap, not something to fake with sentinel invalid cases.
4. Run through `jobwrap-executor`; collect bundle and V0/V1/V3 evidence.

## Boundary

- Do not compile/execute on the host.
- Do not copy the Route B candidate as Route A.
- Do not invent invalid cases for a no-input contract.
- `tests/invalid.json` requirement is a blocker to report, not to bypass.
