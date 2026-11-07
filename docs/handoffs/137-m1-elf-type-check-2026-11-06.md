# 137 — M5 ELF e_type check reviewed and cherry-picked

- Date: 2026-11-06
- Owner: Member 1
- Source: `m5/elf-type-check` @ `a63f80d`
- Destination: `canonical/m1-m5-integration` @ `d1ce352` + this commit
- M5 frozen branch: unchanged. No M5 usage line merged.

## 1. Change

`tools/fixture_intake.py::_check_elf` now reads the first 20 bytes, resolves
EI_DATA, and requires `e_type == 2` (ET_EXEC). Any other type gets:

```
elf_not_non_pie
```

`ET_DYN/PIE` (3) is rejected. The magic/truncated/invalid-EI_DATA findings
remain distinct.

## 2. CWE122 non-PIE product

Artifact:
`_m3-run/fixtures/public/CWE122_c_CWE129_fgets_01/original.elf`

```
e_type          2 (ET_EXEC)
_check_elf      no findings
sha256          c9ddb9c257a81d97a32e3026eacfd2e3453b41bebbaab36e53505e47421c4915
```

Same bytes with `e_type = 3`:

```
elf_not_non_pie / original.elf
```

The type check therefore passes ET_EXEC and rejects ET_DYN as required.

## 3. Pre-existing CWE122 intake finding

A full `check_fixture` on that delivered CWE122 fixture still reports
`contract_schema_invalid` (`missing ['allowed_calls']`) and the older
`build_output_hash`/`case_sha_mismatch` findings for the modified copy. Those
are pre-existing fixture-contract/hash issues, not caused by this ELF check;
the ELF-type assertion is measured separately above. No fixture byte or
contract rule was changed here.

## 4. Tests and invariants

```
tests/test_fixture_intake.py   40 passed
canonical full                 450 passed / 2 skipped / 0 failed
```

Canonical partial semantics are unchanged: wide `job_id OR attempt_id` query,
`partial` passthrough, plan fallback `partial=false`.

CWE121 v2 hash and the 120 contract gate are unchanged. 124 remains
`inconclusive / required_check_not_run / symbolic`. T8.3 blocked; no merge to
`main`, no tag, no live-success claim.
