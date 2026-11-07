# M4 — record 124 CWE416 candidate verification (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** the requested candidate/gate identity checks only. No repair verdict,
no merge, no tag, no live success.

---

## 0. Verdict

**PASS for every requested item — and the outcome cannot be
`success_within_scope`.**

| Requested check | Result |
|---|---|
| 62/62 | **PASS** — top-level `SHA256SUMS`, 62 entries, 62 OK |
| 31/31 | **PASS** — candidate evidence `SHA256SUMS`, 31 OK |
| 10/10 | **PASS** — contract-sync `SHA256SUMS`, 10 OK |
| candidate `46d16e99…fcd0` | **PASS** — exact match, 25,344 B |
| V3 1/1 | **PASS** — `valid: 1/1`, `invalid: not_applicable` |
| control 0/1 | **PASS** — same runner on the unrepaired original, `passed=0 total=1` |
| V5 twice identical | **PASS** — `c9c2632e…` ×2 and `46d16e99…` ×2 |
| outcome | **`inconclusive` / `required_check_not_run`** — never `success_within_scope` |

---

## 1. Manifests

```text
top-level SHA256SUMS            62 entries   62/62 OK
evidence/cwe416-candidate/…     31 entries   31/31 OK
evidence/cwe416-contract-sync/… 10 entries   10/10 OK
```

All three are complete and pass. The three counts are three different sets, not
three opinions about the same set.

---

## 2. Candidate and gate index

| Field | Value |
|---|---|
| candidate | `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0` |
| original | `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9` |
| size | 25,344 → 25,344 |
| edit | 5 bytes at file offset 4869: `call free@plt` → 5 × `nop` |

| Gate | Result | Basis |
|---|---|---|
| V0 identity | **passed** | candidate built from this original |
| V1 structure | **passed** | 5 changed bytes, one interval, headers identical |
| V2 interface | **not_run** | static observation only, no scored verdict |
| V3 behaviour | **passed** | `input_mode=none`, valid **1/1**, `invalid: not_applicable` |
| V4 symbolic | **not_run** | no engine ran; not a binary-level claim |
| V5 reproducibility | **passed** | source `c9c2632e…` ×2; patch `46d16e99…` ×2 |

**Important:** `v2-interface.json` contains `"pass": true`, but it is a
**measured static observation**, not a scored interface verdict. `gate-index.json`
correctly records V2 as `not_run`. The observation must not be promoted to a
passed gate.

---

## 3. V3, control, V5

```text
V3 candidate : valid 1/1   invalid not_applicable   passed 1 / total 1   repaired_pass True
control      : valid 0/1   passed 0 / total 1        repaired_pass False  (stdout_hex 4ba2020a)
V5 source    : [c9c2632e… , c9c2632e…]   byte_identical True
V5 patch     : [46d16e99… , 46d16e99…]   byte_identical True
```

The control matters: the same runner and manifest, pointed at the **unrepaired**
original, produce `0/1` with allocator residue on stdout. The candidate's `1/1`
is therefore discriminating, not a runner that always passes.

---

## 4. Outcome — inconclusive, not success

With the actual gate results **V0 pass, V1 pass, V2 not_run, V3 pass, V4 not_run,
V5 pass** (all required), the acceptance engine returns:

```text
outcome = inconclusive
reason  = required_check_not_run
failing = interface          (V2, the first required not_run)
```

Counterfactuals:

```text
V2 passed, V4 not_run  -> inconclusive / required_check_not_run / failing=symbolic
all six passed         -> success_within_scope
```

So `success_within_scope` is impossible while **either** V2 or V4 is `not_run`.
The matching candidate hash and a reviewed scope do not override a missing
required check.

---

## 5. Record 118

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

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
| `M4-124-candidate-evidence-2026-11-05.txt` | three manifest checks, candidate hash, V3/control/V5, gate index, acceptance outcome |
| `M3-124-cwe416-candidate-handoff-2026-11-05.zip` | the handoff package |
| `_m4-verify/124/` | extracted package used for the checks |
