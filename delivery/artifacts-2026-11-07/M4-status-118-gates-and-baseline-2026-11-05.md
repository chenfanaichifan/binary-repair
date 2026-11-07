# M4 — 118 gates re-run and M1/M5 v3 baseline (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** 118 five-gate re-check and baseline status only. No merge, no tag, no
live success, no gate promotion beyond 118.

---

## 0. Status

| Item | Status |
|---|---|
| 118 five gates (re-run) | **PASS** — 5/5 |
| 118 status | **VERIFIED (rebuild evidence package)** — the “keep REPORTED until it passes” condition is satisfied |
| M1/M5 v3 on the same baseline | **NO** — `7c279a1` and `4c36898` are siblings |
| End-to-end four checks | **DEFERRED** until the baseline is shared |
| CWE121 v2 hash | **PASS — `24bfe568…4e37`** on both copies |

If the intent is to hold 118 at `REPORTED` until the same-baseline re-check,
say so and I will revert the label immediately; nothing else changes.

---

## 1. 118 five gates — re-run

| Gate | Evidence | Result |
|---|---|---|
| 1. Dual manifests | `06-SHA256SUMS` 5/5; `SHA256SUMS` 10/10; `06` is covered by `SHA256SUMS` | **PASS** |
| 2. Build | `exit=0`, `sha256=c9c2632e…23c9`, `size=25344` | **PASS** |
| 3. Trigger | `50x` + `200x` + single = **251**, one distinct `05040a`, ASLR-on contrast | **PASS** |
| 4. Window | `snapshot.current "11"`, uid 11 = `gate4-harness`, 0 `.lck`, boot 21:43, `~/cwe416` absent | **PASS** |
| 5. Conformance | 21/21 `build_json` rows match canonical; only `window.is_baseline` differs by design | **PASS** |

The package is unchanged since the earlier pass; the re-run reproduces the same
digests and the same conformance result.

**Standing caveat:** M4 did not rebuild or re-run the binary; this is
verification of the hash-bound evidence package.

---

## 2. M1/M5 v3 — not on the same baseline

| Repo | HEAD | Content |
|---|---|---|
| `_m1-work/live-bridge` | `7c279a1 feat(m5): add v3 no-input contract mode` | v3 schema **+** intake `1b08ae5` |
| `_m1-work/m5-schema` | `4c36898 feat(m5): add v3 no-input contract mode` | v3 schema only |

- merge-base of the two heads: `af01baf79eeca2ef565aa09b16839a4b250d6960`;
- `7c279a1` is **not** an ancestor of `4c36898`, and `4c36898` is **not** an
  ancestor of `7c279a1`;
- the `contracts.py` content is identical in both
  (`cc976f62cc79c1f98188d7cdec9bdb40abd40797e1d1c5156e7443b76ff5fd6a`).

So they are **sibling ports** of the same schema, not one baseline. A shared
baseline would require a merge/rebase of one onto the other (or a third commit
carrying schema + intake + acceptance).

---

## 3. End-to-end four checks — deferred

| # | Check | Current state |
|---|---|---|
| 1 | rejection fields absent (contract + intake + V3) | schema **PASS**, intake **PASS**, V3 **pending** |
| 2 | sentinel rejected (contract + intake + V3) | schema **PASS**, intake **PASS**, V3 **pending** |
| 3 | V3 exactly **1/1** no-input | **not implemented** |
| 4 | CWE121 v2 hash unchanged | **PASS — `24bfe568…4e37`** |

The schema and intake layers are ready; the behaviour layer is the missing
third. These four checks will be run once M1/M5 are on one baseline.

---

## 4. CWE121 v2 hash — re-checked

```text
live-bridge : 24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37  match=True  input_mode=False
m5-schema   : 24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37  match=True  input_mode=False
```

The reviewed v2 hash is unchanged in both copies; the v3 addition does not alter
the v2 canonical payload.

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
| `M4-status-118-gates-and-baseline-evidence-2026-11-05.txt` | gate re-run, baseline identities, CWE121 hash |
| `probe_conformance.py` | the 21-row conformance comparison |
| `M1-T30-118-evidence-2026-11-05/t30-rebuild-2026-11-05/` | the evidence package |
