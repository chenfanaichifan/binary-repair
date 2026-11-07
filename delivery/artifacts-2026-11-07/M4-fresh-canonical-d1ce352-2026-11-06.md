# M4 — fresh canonical pin `d1ce352` (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** fresh remote pin only, plus the accepted 513/9/0 count. No gate
promotion, no merge, no tag.

---

## 0. Verdict

| Item | Result |
|---|---|
| **fresh canonical** (16:22) | **`d1ce352`** — merge of `dc3bcd3` + `40a4153` |
| old `dc3bcd3` | **superseded** — not accepted as current canonical |
| old `1938c31` | **superseded** — not accepted as current canonical |
| `integration/live-bridge` | **`7817a20`** — `6d67140` is an ancestor, no longer the head |
| `6d67140` / `41ff540` tests | **513 passed / 9 skipped / 0 failed** — accepted |
| claimed `506/9/0` | **pending M1 correction or explanation** |
| `d1ce352` full suite | **449 passed / 9 skipped / 0 failed**; its message says `449/2/0` |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. Fresh `ls-remote` (2026-11-06T16:22+0800)

SSH and HTTPS agree:

```text
d1ce352f60057ab3cd389c6af609c7b5ed3bcefd  refs/heads/canonical/m1-m5-integration
7817a20cd5a215e4423de6e045bf754691671120  refs/heads/integration/live-bridge
e6689e47c0987afb8ec302d61050c6702f8c340f  refs/heads/m1/t30-acceptance-ab-2026-11-05
42d00181e03c17eaf54d18924b4ea8d2de499406  refs/heads/m3/cwe416-v3-noinput
```

The canonical head moved during this session: `1938c31 -> dc3bcd3 -> d1ce352`.
Only `d1ce352` is current; the earlier two are history.

---

## 2. What `d1ce352` is

```text
commit d1ce352f60057ab3cd389c6af609c7b5ed3bcefd
Merge:  dc3bcd3 40a4153
subject merge(canonical): bring the v3 no-input baseline in with the partial usage fix
```

The message says the partial-usage commit sat on `1938c31`, which lacked the v3
no-input tests, so the 120 contract gate could not be measured there. The merge
brings the local canonical v3 baseline `40a4153` in, with no fixture byte,
contract rule, or gate status changes. It reports 84 gate tests, 19
usage/controller tests, `449 passed / 2 skipped`, and the CWE121 v2 hash
reproduced.

**Measured here:** `449 passed, 9 skipped, 0 failed` — the passed count matches;
the skipped count does **not** (9 vs 2). No failures. This is the same
count-documentation issue as the other records and should be corrected or
qualified with the exact tree/command.

---

## 3. Integration head also moved

```text
7817a20  docs(api): pin the obligation evidence field contract with a real response
parent   0233d34  fix(api): order obligation rows V0..V5 in evidence and route summary
```

`6d67140` is an ancestor of `7817a20` (`6d67140..7817a20` is fast-forward), so
`6d67140` is no longer the integration head. Its own test result is unchanged:
**513/9/0**, as is `41ff540`'s.

Canonical `d1ce352` and integration `7817a20` are separate lines; their
merge-base is `40a4153`, neither is an ancestor of the other.

---

## 4. 513/9/0 is the accepted count; 506 needs correction

Measured on clean archives, full suite, `pytest -q -o addopts=""`:

| Commit | Result |
|---|---|
| `6d67140` | **513 passed, 9 skipped, 0 failed** |
| `41ff540` (merge) | **513 passed, 9 skipped, 0 failed** |

`6d67140` collects 522 tests (513 + 9). The merge message's
**506 passed / 9 skipped / 0 failed** is 7 fewer passed and is not reproduced.
**M1 must correct it to 513/9/0 or explain the exact tree/selection that yields
506.**

---

## 5. 124

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

No canonical/integration movement changes 124; V4 remains `not_run`.

---

## 6. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 7. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 8. Evidence

| File | Content |
|---|---|
| `M4-fresh-canonical-d1ce352-evidence-2026-11-06.txt` | fresh SSH/HTTPS `ls-remote`, `d1ce352` merge/parents, merge-base, `d1ce352`/`6d67140`/`41ff540` suites, integration movement, 124 gate index |
| `_m4-verify/d1ce352/` | clean archive used for the full suite |
| `_m4-verify/6d67140/`, `_m4-verify/41ff540/` | clean archives for the accepted 513/9/0 |
