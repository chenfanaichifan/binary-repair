# 131 — Lead: the `verified_by` gate holds; M4's own replay is the only blocker

- **Owner:** Lead (decision only; no product code in this record)
- **Date:** 2026-11-06
- **Status:** binding for 124, V4 and T8.3; changes no gate, no verdict, no merge, no tag
- **Basis:** M4's status lock plus a re-run of the gate on `3f21d317…`; commands and
  outputs in `131-lead-verified-by-gate-evidence-2026-11-06.txt`
- **Numbering:** 125–130 are already used across the M3 root series (125–128) and the
  M1 branch series (128–130); this record takes 131 so nothing existing is renumbered

---

## 0. Decision

| Item | Decision |
|---|---|
| `replay.verified_by="m4"` gate | **Valid and sufficient for its purpose.** It stops a bundle status from promoting V4. |
| V4 | **`not_run`**, unchanged |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED**, independent of T8.3 |
| T8.3 | **BLOCKED** |
| Single blocker | M4 has **no environment to replay** the V4 analysis itself |
| Producer-only acceptance (`require_independent=False`) | **Not authorized**; that is a downgrade, not Standard B |
| Merge / tag / live success | none |

The gate answers the question "can a bundle assert its own V4 pass?" — no. It does
**not** answer "is the producer's V4 analysis correct?" — that is M4's replay, and
today that is the only thing standing between V4 and `not_run`.

## 1. What was measured, not repeated

Re-run on `_m4-verify/3f21d31` (HEAD `3f21d317…`), Python 3.11 + pydantic 2.14 —
the same tree M4 measured, an independent process:

| # | Fact | Location | Measured |
|---|---|---|---|
| 1 | The marker is a replay field with one legal value | `app/domain/v4.py:131` `verified_by: Literal["m4"] \| None = None` | present |
| 2 | The validator refuses a claim without the marker | `app/domain/v4.py:432-437` | `require_independent=True` → **REJECTED**: "V4 is producer/ingest provisional; independent M4 replay is missing" |
| 3 | Production callers pass `require_independent=True` | `tools/route_bundle_ingest.py:363`, `app/services/obligations.py:160` | both |
| 4 | The adapter cannot set the marker, even if the harness tries | `app/domain/v4.py:370-380` builds `replay` without the key; test `tests/test_v4_harness_adapter.py:117` | forged `"verified_by": "m4"` → adapter output `None` |
| 5 | The rerun bundle declares V4 passed anyway | `delivery/cwe416-124-v4-rerun-2026-11-06/bundle.json` | `gates.V4.status = passed`, but the product evidence has `replay.verified_by: None` |
| 6 | The gate keeps the attempt inconclusive | `require_independent=False` on the same file | ACCEPTED — and that path is why the flag must stay `True` in production |
| 7 | The tests that pin all of this | `tests/test_v4_harness_adapter.py`, `tests/test_v4_evidence.py`, `tests/integration/test_v4_bundle_gate.py` | 39 passed, 3 passed |

## 2. The trust boundary — stated so it is not overclaimed

The marker is an **operator statement, not a signature**. Measured: hand-adding
`"verified_by": "m4"` to the product `v4-symbolic.json` is accepted by
`validate_v4_evidence(..., require_independent=True)`. There is no key, no
attestation, and no binding to a replay transcript at the code level.

So the gate's guarantee is narrow and worth having: **a bundle cannot promote V4
by declaring it**, and a harness cannot smuggle a marker through the adapter. What
it cannot guarantee is that no human ever edits the JSON. That is covered by
process, not by code:

- M4's own record must cite the replay command, its two digests, and the engine
  versions;
- the digest must match the producer's (`cb2137a2…`), so a hand-written marker with
  no replay has nothing to cite;
- M4 is the same operator as the Lead (M4's own status says so). "Independent"
  here therefore means **independent provenance and a separate replay process**,
  not a second human. Do not describe it as a two-person signature.

## 3. The blocker, in one paragraph and one table

M4 can verify the adapter now (no angr needed) and has done so. M4 cannot verify
the symbolic claim, because the verifier's host has no angr. The producer's
environment is recorded and reachable on the guest at `/opt/angr-venv`; the
correct next move is to give M4 that environment (or an equivalent one), not to
relax the gate.

Environment contract — all four must hold, or V4 stays `not_run`:

| Requirement | Value | Why exact |
|---|---|---|
| Python | 3.12.x | the recorded replay used 3.12.3; angr wheels are version-matched |
| angr | 10.0.4.post1 | the analysis semantics (state counts, hook behaviour) are version-dependent |
| z3 | 5.1.0 | solver counts (`sat`/`unsat`/`unknown`) are part of the accounting |
| Inputs reachable | `candidate.elf` (`46d16e99…fcd0`), `original.elf` (`c9c2632e…`), fixture `contract.json` (`8a2b408c…`) | hashes are bound by the validator |

Acceptance test for the environment — run before any replay is booked:

```sh
/opt/angr-venv/bin/python -c "import sys, angr, z3; \
  print(sys.version.split()[0], angr.__version__, z3.get_version_string())"
# expected: 3.12.3  10.0.4.post1  5.1.0
```

Then M4's replay, per record 128 §6, must produce, in order:

1. `state: passed`, `ran: true`, `scope: model`;
2. `replay.runs = 2`, `replay.identical = true`, and **the same
   `replay.evidence_sha256 = cb2137a20d838e3f48e02f2d38f258487ddc3a588a371970d9ef41b63304cb14`**;
3. calibration: `known_good` holds, `known_bad` violated (1 passed / 1 failed);
4. the candidate-side `unsat` is the empty-disjunction case (`free_calls = 0`),
   disclosed as such — not a solved constraint;
5. the property text matches the contract's `forbidden_behavior`, and hooks do not
   over-approve the target function.

A **different** digest is a finding: either the environment differs or the
analysis is nondeterministic. Do not adjust the expected digest; report it.

## 4. What cannot substitute for it

1. **The producer's harness output is not M4's replay.** It is the claim to
   verify; the same file cannot be both.
2. **`require_independent=False` must not be used in production.** It turns the
   gate into a comment; a bundle-declared pass would become a product pass.
3. **A bundle that says V4 passed is not V4 passed.** Measured in §1 row 5-6.
4. **118's VERIFIED does not relieve T8.3.** Different artefact, different
   obligation, and T8.3 needs a second defect class, not a second verification.
5. **Producer-only acceptance is a downgrade.** If the Lead ever chooses it, it is
   recorded as reduced scope — never as Standard B, and never as `verified_by="m4"`.

## 5. Assignment

**M1 — host backend.**
Keep `require_independent=True` in `route_bundle_ingest` and `persist_obligations`.
Keep 124 at `inconclusive` / `required_check_not_run` / `symbolic`. Provide the
angr environment or a guest entry point for M4; if neither exists, V4 stays
`not_run`. Keep CWE121 v2 `24bfe568…4e37` and the 120 contract gate. T8.3 blocked;
no merge to `main`, no tag, no live-success text.

**M3 — producer.**
Keep 128's product evidence as shipped; never write `verified_by="m4"` yourself.
Make the environment reproducible (the `/opt/angr-venv` recipe with exact pins, or
an offline wheel set, or a guest path M4 can use). V4 may be discussed as `passed`
only after M4's replay. T8.3 blocked; no invented second defect class.

**M4 — verifier.**
Maintain the current lock: adapter replay PASS, symbolic replay NOT RUN, V4
`not_run`, 124 `inconclusive` / `failing=symbolic`, 118 VERIFIED independent.
When the environment exists, replay candidate/original/replay-digest yourself and
write `verified_by="m4"` **only** when §3 items 1-4 all hold. Record 91 unchanged;
same operator; reviews 9-12 counted separately; no merge, no tag, no live success.

**M2 — console.**
Continue T8.2 (`assistant_llm.py`, `test_assistant_llm.py`). Result screens render
`input_mode=none`, V3 1/1, invalid `N/A`; never "2/2 passed" for zero invalid
cases; keep partial usage visible. A V4 `not_run` renders as `not_run`, not as a
pending spinner and not as a failure.

## 6. State carried forward

| Item | Value |
|---|---|
| 124 candidate | `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0` |
| V4 claim (producer) | `state: passed`, `verified_by: None`, digest `cb2137a2…cb14`, angr 10.0.4.post1 / Python 3.12.3 |
| V4 product verdict | `not_run` |
| 124 outcome | `inconclusive` / `required_check_not_run` / `symbolic` |
| 118 | VERIFIED (independent) |
| T8.3 | BLOCKED |

## 7. Not claimed

- No claim that the producer's V4 dossier is wrong; it is **unverified**, not
  refuted.
- No claim that the marker is tamper-proof (§2).
- No claim that M4's replay will pass; a failed replay is a valid outcome.
- No gate, verdict, merge or tag was changed to publish this record.

## 8. Signature

| Role | Name | Date | State |
|---|---|---|---|
| Lead | Lead | 2026-11-06 | published |
| M1 | — | — | pending acknowledgement |
| M3 | — | — | pending acknowledgement |
| M4 | — | — | pending acknowledgement |
| M2 | — | — | pending acknowledgement |
