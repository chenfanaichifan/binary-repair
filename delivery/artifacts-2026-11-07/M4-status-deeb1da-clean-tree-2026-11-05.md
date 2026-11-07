# M4 — deeb1da four checks PASS (clean archive); working tree now clean (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** status lock only. No new verification claim beyond `deeb1da`, no
CWE416 end-to-end, no merge, no tag, no live success.

---

## 0. Status

| Item | Status |
|---|---|
| `deeb1da` four checks | **PASS** — verified on a clean `git archive deeb1da` tree |
| Working tree now | **clean** — no conflicts; HEAD = upstream = `deeb1da`; no merge in progress |
| M3 `v3 none` contract/fixture | **still absent** — record 119 unchanged (`schema_version: 2` + `input_mode` + `invalid_exit_code: 0`) |
| CWE416 four end-to-end checks | **DEFERRED** until M3 ships `v3 none` |
| Record 118 | **VERIFIED (rebuild evidence package)** — independent of T8.3 |
| T8.3 | **BLOCKED** |

---

## 1. The annotation, and why it was needed

The four `deeb1da` checks were run on **`git archive deeb1da`**, not on the
working tree, because the working tree was **mid-merge**:

```text
UU MEMORY.md
UU docs/fixtures.md
UU tests/test_fixture_intake.py
UU tools/fixture_intake.py
9 conflict markers in tests/test_fixture_intake.py
```

That caveat is explicit in `M4-deeb1da-v3-full-chain-2026-11-05.md`: the PASS
describes the **commit**, not the conflicted working copy.

**Current state (measured):**

```text
git status --short        -> (empty)
HEAD                      -> deeb1da
upstream (@{u})           -> deeb1da
MERGE_HEAD                -> absent
conflict markers          -> 0
```

So the archive caveat is now **historical**: the working tree is clean at the
same commit, and the branch is in sync with its upstream. The next round can run
on the working tree without the archive step, if it is still clean then.

---

## 2. `deeb1da` four checks — unchanged

| # | Check | Result |
|---|---|---|
| 1 | rejection fields absent | **PASS** |
| 2 | sentinel rejected | **PASS** (executor test environment-blocked, not semantic) |
| 3 | V3 exactly 1/1 | **PASS** |
| 4 | CWE121 v2 hash unchanged | **PASS — `24bfe568…4e37`** |

No re-run was needed; the working tree is byte-identical to the verified commit
(`git status` empty, `HEAD = deeb1da`).

---

## 3. CWE416 — still deferred

- `fixtures/public/CWE416_…_noinput/` **still absent**;
- record 119 is unchanged at 22:36, still `schema_version: 2` with
  `input_mode` and `invalid_exit_code: 0`;
- so the four CWE416 end-to-end checks cannot be applied yet.

---

## 4. Record 118

`118 = VERIFIED (rebuild evidence package)` remains an independent record. It does
not promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 5. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 6. Evidence

| File | Content |
|---|---|
| `M4-deeb1da-clean-tree-evidence-2026-11-05.txt` | clean status, HEAD/upstream, no MERGE_HEAD, 0 markers, M3 absence, CWE121 hash |
| `M4-deeb1da-v3-full-chain-2026-11-05.md` | the four-check record (clean archive) |
| `_m4-verify/deeb1da/` | the clean archive used for the four checks |
