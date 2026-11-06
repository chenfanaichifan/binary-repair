# M4 — canonical pin lock `d1ce352` (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** pin lock and pending count corrections. No gate promotion, no merge,
no tag.

---

## 0. Status

| Item | Value |
|---|---|
| **canonical pin** | **`d1ce352`** — confirmed at 16:25 |
| `integration/live-bridge` | `7817a20` |
| old `dc3bcd3` / `1938c31` | **not accepted** as current canonical |
| `d1ce352` count | actual **449 passed / 9 skipped / 0 failed** |
| `6d67140` / `41ff540` count | actual **513 passed / 9 skipped / 0 failed** |
| count corrections | **pending M1** |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. Pin confirmation

Fresh `ls-remote` at **2026-11-06T16:25+0800**:

```text
d1ce352f60057ab3cd389c6af609c7b5ed3bcefd  refs/heads/canonical/m1-m5-integration
7817a20cd5a215e4423de6e045bf754691671120  refs/heads/integration/live-bridge
```

`d1ce352` is the merge of `dc3bcd3` (partial usage) and `40a4153` (v3 no-input
baseline). The canonical line moved `1938c31 -> dc3bcd3 -> d1ce352`; only
`d1ce352` is current, and the older two are history.

---

## 2. Count corrections pending

M4 does not rewrite commit messages; M1 must correct or qualify:

| Location | Message says | Measured |
|---|---|---|
| `d1ce352` | `449 passed / 2 skipped` | **449 passed / 9 skipped / 0 failed** |
| `41ff540` / `6d67140` | `506 passed / 9 skipped` | **513 passed / 9 skipped / 0 failed** |

No failures in either case; the difference is a count/selection artifact. The
record should name the exact tree and command if the lower numbers are to stand.

---

## 3. 124

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The pin and count corrections do not upgrade V4; 124 remains provisional.

---

## 4. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
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
| `M4-canonical-pin-lock-evidence-2026-11-06.txt` | fresh `ls-remote`, `d1ce352` identity, three suite results, 124 gate index |
| `_m4-verify/d1ce352/` | clean canonical archive |
| `_m4-verify/6d67140/`, `_m4-verify/41ff540/` | clean archives for 513/9/0 |
