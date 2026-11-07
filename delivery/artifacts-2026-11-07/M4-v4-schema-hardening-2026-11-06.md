# M4 — V4 schema hardening probe (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** probe of M1's V4 schema hardening against four rejected shapes. No
code change, no gate promotion, no merge, no tag.

---

## 0. Verdict

The hardening is **real but uncommitted**, and it has **one residual acceptance**
in the exact shape the Lead named.

| Probe | Hardened working tree | Committed `fa41102` |
|---|---|---|
| `cases=1, passed=1, failed=0` (no `known_*`) | **REJECTED** | ACCEPTED |
| same + `known_good/known_bad/known_bad_rejected=true` | **ACCEPTED** ← residual | ACCEPTED |
| `complete=True` + `unexplored` non-empty | **REJECTED** | ACCEPTED |
| `complete=True` + `unknown>0` | **REJECTED** | ACCEPTED |
| `claimed_scope="binary-level proof"` | **REJECTED** | ACCEPTED |
| `not_claimed` without “binary-level” | **REJECTED** | ACCEPTED |
| **124 outcome** | **`inconclusive` / `required_check_not_run` / `symbolic`** | same |

So: three of the four named shapes are truly rejected in the working tree; the
fourth is rejected only when the new booleans are absent. **None of the four is
rejected by the committed state** — the hardening has not landed.

---

## 1. Where the hardening lives

```text
HEAD: fa41102 feat(m1): wire typed v4-symbolic through bundle and persist
git status:  M app/domain/v4.py
             M tests/test_v4_evidence.py
             M tests/integration/test_v4_bundle_gate.py
             M tests/integration/test_worker.py
```

`fa41102`'s `v4.py` is the pre-hardening schema. The changes below are
**working-tree only**:

- `_complete_has_no_unexplored` — rejects `complete=True` with non-empty
  `unexplored`;
- `_complete_solver` — rejects `complete=True` with `unknown != 0` or
  `timeouts != 0`;
- `claimed_scope: Literal["model"]` — rejects “binary-level proof”;
- `not_claimed` must contain a “binary-level” exclusion;
- `Calibration` requires `known_good`, `known_bad`, `known_bad_rejected`.

Until committed, the production schema remains the old one and accepts all four
bad shapes.

---

## 2. Probe results — hardened working tree

```text
valid base: ACCEPTED
cases=1, passed=1, failed=0 (no known_*): REJECTED — 3 validation errors
cases=1, passed=1, failed=0 + known_* true: ACCEPTED
complete=True + unexplored nonempty: REJECTED — 1 validation error
complete=True + unknown>0: REJECTED — 1 validation error
claimed_scope="binary-level proof": REJECTED — 1 validation error
not_claimed without binary-level: REJECTED — 1 validation error
```

- The first rejection is **field-presence**, not semantics: the three new
  booleans are missing.
- Adding the three booleans (all `true`) makes `cases=1, passed=1, failed=0`
  **pass**. The model never ties `known_bad_rejected` to `failed >= 1`, so a
  producer can claim “the known-bad candidate was rejected” while reporting zero
  failed cases.
- `unexplored`, `unknown`, `claimed_scope`, and `not_claimed` are genuinely
  enforced.

## 3. Probe results — committed `fa41102`

```text
cases=1, passed=1, failed=0: ACCEPTED
complete=True + unexplored nonempty: ACCEPTED
complete=True + unknown>0: ACCEPTED
claimed_scope="binary-level proof": ACCEPTED
not_claimed without binary-level: ACCEPTED
```

The committed schema has no validators for these shapes; only the working tree
does.

---

## 4. Residual gap and fix

**Residual acceptance:** `cases=1, passed=1, failed=0` + all three `known_*`
booleans true is accepted. The booleans are self-declared and are not
cross-checked against `passed`/`failed`/`cases`.

**Minimal fix:** in `Calibration._counts`:

- if `known_bad_rejected` then require `failed >= 1`;
- if `known_good` then require `passed >= 1`;
- require `cases >= 2` (one good, one bad);
- optionally require `known_bad_rejected` to correspond to a specific
  `known_bad_cases` count.

Without that, the hardening closes three of four shapes and leaves the negative
control claimable on zero evidence.

---

## 5. 124 — unchanged

`tests/test_v4_evidence.py` + `tests/integration/test_cwe416_124_ingest.py`
→ **26 passed** on the hardened working tree. The 124 outcome is still:

```text
V2 passed 5/5; V4 not_run; all required
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The hardening does not touch 124 because its V4 is `not_run`; it only affects
what would be accepted if a V4 `passed` were submitted.

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
| `M4-v4-hardening-evidence-2026-11-06.txt` | git state, validator lines, hardened vs committed probes, 26 tests, 124 outcome |
| `probe_v4_hardening.py` | the seven-shape probe |
| `_m4-verify/fa41102/` | clean committed tree used for the “committed” column |
