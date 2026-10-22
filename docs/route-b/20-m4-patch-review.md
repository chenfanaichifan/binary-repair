# M4 Route A patch review — 2026-10-22

**Patch:** `docs/route-a/m4-patches/0001-member-4-routea-gate3-...patch` on
`origin/member-4-verification` @ `dea8316`
**SHA-256:** `4c2d480e1511126814a9e57f07bb645c29335b8fc0cc3d9e270dd7cfafb3f142`
**Base:** `33235f5a9f5f58fd4b081a593be05da8b77d8c37`
**Apply:** `git apply --check` clean; no conflicts.

**Verdict: CHANGES REQUESTED — not approved, not gate-3 evidence.**

## What is good

- Patch applies cleanly to the declared base.
- `byteaudit.py` is dependency-free and its 9 pure-byte tests pass.
- `evidence.py` bundle is static: readelf/objdump only; it does **not** execute the
  candidate; items 4–5 are conservatively `not_run`.
- `routea_vm_check.sh` stops before candidate execution.
- Manifest schema is materially richer than schema 1 (displaced bytes, added code/data
  hashes, header fields, intervals).

## Blocking findings

### B1. Patch targets the old contract, not canonical `24bfe568…`

The patch's `contract.route-a-v1.json` hash is
`ba33b4d070b8799b778a9ca1a257190079627bda72b5c42933edfebb0f5d8fc4`, not the
canonical `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`.
Differences include:

- patch entry 3/4 authorize `fprintf@plt` + `stderr`; canonical entries authorize
  fd-2 write/exit;
- patch environment assumptions use four different strings (CET/seccomp wording);
- patch entry 5 pins `0x8e9 -> 0x1000`/`0x402000`; canonical keeps a generic tail
  extension.

M4's message says "24bfe MATCH", but the patch does not contain 24bfe. The
implementation must be rebased or a separate scope must be approved.

### B2. Patch targets the old candidate `f3cb9cbb…`, not `c4a159…`

`tests/test_routea_cave.py` and `scripts/routea_vm_check.sh` hardcode:

- golden candidate `f3cb9cbb503fb0d47ebebab7053fa2ed37b7876ffe5122157d31fefc783f9fa7`
- contract `ba33b4d0…`
- test expects a `call` to `fprintf@plt 0x401120`, `single_syscall`, and
  `sub rsp,8`.

The canonical candidate `c4a159…` uses a `write(2)` syscall, no `fprintf`, and
71-byte code; it would fail those checks. This creates a second competing candidate
and a second golden contract.

### B3. `manifest.py` enum conversion crashes on pyelftools 0.33

`routea/manifest.py:85` / `:89`:

```python
"e_ident_class": int(header["e_ident"]["EI_CLASS"]),
"e_version": int(header["e_version"]),
```

pyelftools returns strings (`ELFCLASS64`, `EV_CURRENT`), so every ELF-dependent
test fails with `ValueError: invalid literal for int()`.

### B4. `audit.py` rejects the actual tail cave

`routea/audit.py:293`:

```python
segment if seg["vaddr"] <= cave_addr < seg["vaddr"] + seg["memsz"]
```

The cave starts at `0x4018e9`, exactly the original RX `p_memsz` end, so
`inside_rx_load` is false. `cave_within_memsz` would also be false before the
authorized extension. The audit therefore cannot pass the candidate it is meant
to approve. It must audit the extended segment / page tail, not the original
`memsz`.

### B5. Test expectation is wrong

`test_audit_rejects_unpatched_binary` expects
`changed_bytes_inside_declared_intervals` to be false for `original == patched`.
The byte audit correctly returns true (no changed bytes, no residue), so the test
fails. Either the test should assert a different no-op check, or the audit needs
an explicit "candidate differs from original" check.

### B6. VM helper hardcodes old identity

`scripts/routea_vm_check.sh` hardcodes candidate `f3cb9cbb…` and contract
`ba33b4d0…`; it will fail canonical `24bfe`/`c4a159` and is not a valid Gate 3
record for the current candidate.

## Test result on the review host

```text
pytest tests/test_routea_manifest.py  -> 9 passed
pytest tests/test_routea_cave.py      -> 7 failed
```

Failures: `test_manifest_is_complete`, `test_cave_and_register_static_checks`,
`test_candidate_is_golden_and_reproducible`, `test_audit_rejects_unpatched_binary`,
`test_audit_rejects_byte_outside_declared_intervals`, `test_audit_rejects_header_tamper`,
`test_bundle_writes_hashed_static_evidence`.

So M4's "only py_compile / pure-bytes run" caveat is confirmed; the ELF-dependent
tests are not green.

## Required before approval

1. Rebase/re-target to canonical contract `24bfe568…4e37` and candidate
   `c4a159…aa82`; remove the competing `f3cb9…` evidence.
2. Fix pyelftools enum extraction.
3. Fix `inside_rx_load` / `cave_within_memsz` for the authorized page-tail
   extension.
4. Fix the no-op test or add an explicit candidate-diff check.
5. Update `routea_vm_check.sh` expected candidate/contract hashes.
6. Re-run `test_routea_manifest.py` + `test_routea_cave.py` and provide output.
7. Re-submit patch hash/base; M5 re-reviews.

Gate 3 remains **CONDITIONALLY FEASIBLE**; M4's implementation remains
**NOT APPROVED / NOT REVIEWED AS CANONICAL** until the above is re-submitted.
