# M4 — V4 `verified_by` gate and 124 provisional state (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** status lock and gate verification. No symbolic run, no gate promotion,
no merge, no tag.

---

## 0. Status

| Item | Status |
|---|---|
| Adapter replay | **PASS** |
| Symbolic replay (`v4_harness.py`) | **NOT RUN** — no angr, guest unreachable |
| V4 | **`not_run`** |
| `replay.verified_by` | **absent** — M4 has not written it |
| Gate behavior | **enforced** — bundle declares V4 `passed`, product rejects without the marker |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED (rebuild evidence package)** — independent of T8.3 |
| T8.3 | **BLOCKED** |

The marker is not a formality: without it, a bundle that says `V4 = passed` is
downgraded by product ingest, and the attempt stays inconclusive.

---

## 1. Gate implementation

Current HEAD `3f21d317b9c61a5ed7cc5f22b233a8bad62169c2`
(`test(m1): prove the V4 adapter cannot set M4 verification`); the gate itself
landed in `73e1911`, and `3f21d31` adds the regression test and record 130.
`app/domain/v4.py` is unchanged between the two.

```python
verified_by: Literal["m4"] | None = None      # replay field
...
def validate_v4_evidence(..., require_independent: bool = False):
    ...
    if require_independent and evidence.replay.verified_by != "m4":
        raise V4EvidenceError(
            "V4 is producer/ingest provisional; independent M4 replay is missing"
        )
```

`route_bundle_ingest` and `persist_obligations` call with
`require_independent=True`. The adapter and writer never add the marker; even a
forged `"verified_by": "m4"` in the harness input is dropped.

---

## 2. Measured gate behavior

The rerun bundle declares V4 passed:

```text
delivery/cwe416-124-v4-rerun-2026-11-06/bundle.json
  gates.V4 = {"status": "passed", "artifacts": ["v4-symbolic.json"]}
```

But its product evidence has no marker:

```text
bundle v4-symbolic replay.verified_by: None
require_independent=True:  REJECTED - V4 is producer/ingest provisional;
                                      independent M4 replay is missing
require_independent=False: ACCEPTED
forged marker -> adapter:  None
```

So the producer cannot self-certify, and the bundle cannot smuggle the marker
through the adapter.

Tests at `3f21d31`:

```text
tests/test_v4_harness_adapter.py
tests/integration/test_cwe416_124_v4_rerun.py
tests/integration/test_v4_bundle_gate.py
→ 14 passed
```

---

## 3. 124 rerun — final six gates and outcome

`tests/integration/test_cwe416_124_v4_rerun.py` asserts exactly:

```text
results = {V0: passed, V1: passed, V2: passed, V3: passed,
           V4: not_run, V5: passed}
details.V2 = "5/5 static interface checks passed"
"V4" not in payload["evidence"]
"independent M4 replay" in details["V4"]
final.outcome = inconclusive
final.reason = required_check_not_run
final.failing_obligation = symbolic
obligations: behaviour/identity/interface/reproducibility/structure passed,
             symbolic not_run
run phase: screening   (Route A has no result bundle)
```

So the final state is **inconclusive / required_check_not_run / symbolic**, with
V4 `not_run` despite the bundle's `passed` declaration.

---

## 4. When `verified_by="m4"` may be written

Only after M4 independently runs, on the same bytes:

1. candidate → **unsat** (empty-disjunction, `free_calls=0`);
2. original → **sat** (the same symbolic pointer reaches `free()` and `printLine()`);
3. two replay digests identical.

Then, and only then, M4 writes `replay.verified_by="m4"` in a separate verifier
record; the producer/adapter/writer must not. No environment is available today
(`import angr` fails; guest `192.168.30.128` times out; no cache/VM/Docker), so
the marker stays absent and V4 stays `not_run`.

V4 remains **model-level, not binary-level**: `scope="model"`,
`claimed_scope="model"`, `not_claimed` excludes binary-level proof.

---

## 5. Record 118 and T8.3

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
| `M4-verified-by-gate-evidence-2026-11-06.txt` | commit, clean status, gate lines, require_independent probes, forged-marker drop, 14 tests, rerun assertions |
| `_m4-verify/3f21d31/` | clean archive of current HEAD used for all runs |
| `delivery/cwe416-124-v4-rerun-2026-11-06/` | the provisional rerun bundle |
