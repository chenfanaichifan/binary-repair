# M4 — M1 `deeb1da` v3 full-chain verification (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** the four v3 checks on M1's `deeb1da`. No CWE416 end-to-end (M3's
contract is still v2), no gate promotion beyond 118, no merge, no tag.

---

## 0. Verdict

| Check | Result |
|---|---|
| rejection fields absent | **PASS** |
| sentinel rejected | **PASS** (five fields; one consumer test environment-blocked) |
| V3 exactly 1/1 | **PASS** |
| CWE121 v2 hash unchanged | **PASS — `24bfe568…4e37`** |
| 118 five gates | **PASS** — remains VERIFIED (rebuild evidence package) |
| CWE416 end-to-end | **DEFERRED** — M3's `v3 none` contract still absent |

---

## 1. Tree state — why `git archive`

`deeb1da8cec85003b53799c0cfbd705c83288699` —
`test(v3): validate the no-input contract across intake, executor and runners`
— includes `38c1b1b feat(v3): integrate M5 schema, exact intake matrices,
no-input V3 1/1`.

The **working tree is mid-merge** and cannot be used as-is:

```text
UU MEMORY.md
UU docs/fixtures.md
UU tests/test_fixture_intake.py
UU tools/fixture_intake.py
9 conflict markers in tests/test_fixture_intake.py
```

I extracted the commit with `git archive deeb1da` into a clean tree
(`0` conflict markers) and ran every check there. Results describe the commit,
not the conflicted working copy.

---

## 2. Four checks

### 2.1 rejection fields absent — PASS

| Layer | Evidence |
|---|---|
| schema | `to_dict()` omits `invalid_input_response`, `invalid_exit_code`, `invalid_stdout`, `invalid_stderr`, `max_valid_input_bytes`; `from_dict()` treats any of them as `unknown contract fields` (even `null`) |
| intake | `no_input_invalid_fields_present` for any of the five; `test_fixture_intake.py` **39 passed** |
| runner | a v3 none contract with `invalid_input_response` → `rc=2`, no artifact written |

### 2.2 sentinel rejected — PASS

| Layer | Evidence |
|---|---|
| schema | empty string, zero and non-null values all rejected (`sentinel values are not allowed`) |
| e2e runner | `test_no_input_cli_rejects_a_sentinel_field` parametrised over all five fields — **5 passed** |
| attempt writer | `test_attempt_writer_rejects_a_sentinel_contract` — passed |
| executor | `test_executor_rejects_a_sentinel_contract_before_work` — **environment-blocked**, see §3 |

### 2.3 V3 exactly 1/1 — PASS

`test_no_input_cli_is_exactly_one_of_one` passed, and an independent M4 CLI probe
on the clean tree returned:

```text
rc = 0
summary = {input_mode: none, invalid: not_applicable, passed: 1, total: 1,
           repaired_pass: true}
artifact = {valid: "1/1", invalid: "not_applicable", total: 1}
```

### 2.4 CWE121 v2 hash unchanged — PASS

`test_shared_loader_uses_m5_schema_and_keeps_cwe121_hash` passed, and the shared
loader returns:

```text
24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37  match=True
```

The v3 work has not altered the reviewed v2 payload.

---

## 3. Test results and the one environment gap

| Suite | Result |
|---|---|
| `test_v3_no_input_e2e.py -k "not executor"` | **8 passed** |
| `test_fixture_intake.py` | **39 passed** |
| `test_run_manifest_compare.py` + `test_run_manifest_repaired.py` | **10 passed** |
| full `test_v3_no_input_e2e.py` | **1 failed** — `test_executor_rejects_a_sentinel_contract_before_work` |

The failure is **environmental**, not semantic:

```text
ModuleNotFoundError: No module named 'elftools'
```

`pyelftools>=0.33` is declared in `requirements.txt`, but no interpreter on this
host has it, no wheel is cached, and the network install failed
(`SSL: UNEXPECTED_EOF_WHILE_READING`). The executor imports `elftools` at module
level, so the test cannot reach the contract check. The same
`load_contract`/`SecurityContract.from_dict` adapter is exercised by the runner
CLI and the attempt-writer test, both passing.

This is a **test-environment gap**, not a demonstrated acceptance failure; it is
recorded rather than hidden.

---

## 4. 118 — five gates re-run

Manifests re-verified unchanged: `06-SHA256SUMS` 5/5, `SHA256SUMS` 10/10; build
`exit=0`, `c9c2632e…23c9`, 25,344; trigger `50x`+`200x`; window
`snapshot.current "11"`, `~/cwe416` absent. **118 remains VERIFIED (rebuild
evidence package)** — still an independent record.

---

## 5. CWE416 end-to-end — deferred

Not run here. The blocker is unchanged:

- record 119's contract is still `schema_version: 2` + `input_mode` +
  `invalid_exit_code: 0`;
- the `_noinput` fixture directory is still absent;
- until M3 ships a real `v3 none` contract/fixture, the four checks cannot be
  applied to CWE416.

---

## 6. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 7. Evidence

| File | Content |
|---|---|
| `M4-deeb1da-v3-evidence-2026-11-05.txt` | commit identity, merge-conflict state, test runs, independent CLI probe, CWE121 hash, 118 manifests |
| `probe_deeb1da_v3.py` | M4's independent 1/1 + sentinel + hash probe |
| `_m4-verify/deeb1da/` | clean `git archive deeb1da` tree used for all runs |
