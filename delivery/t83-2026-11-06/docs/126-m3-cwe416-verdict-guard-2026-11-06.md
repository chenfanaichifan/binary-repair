# 126 — correction: the first wall is `interface`, not `symbolic`

- Date: 2026-11-06 (host only; no guest window, no binary executed)
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput`
- Evidence: `docs/handoffs/evidence/cwe416-verdict-guard-2026-11-06/`
- Decision unchanged: V4 `not_run`, V2 `not_run`, T8.3 blocked, no second sample

## 0. What this record is

Record 125 said a hand-written V4 could not land, and illustrated it with prose.
This pass replaced the prose with a call into the real acceptance engine, using
the real `gate-index.json` from the 124 bundle. The call found that record 125
was **wrong on one point**, so the correction comes first.

## 1. The correction

Record 125 wrote: "the only way from this bundle to `success_within_scope` is to
stop requiring the symbolic obligation". That is false. Two gates are required
and unavailable, and the engine reports the **earlier** one:

```
[A] bundle as it stands              inconclusive / required_check_not_run / interface
[B] `interface` no longer required   inconclusive / required_check_not_run / symbolic
[C] neither required                 success_within_scope, "4 required obligations passed"
```

So the first wall is V2, and V4 is the second. The conclusion 125 drew — that
nothing M3 can produce turns this bundle into a pass — survives; the mechanism
it named did not.

## 2. How that was measured

`show_verdict.py` imports `app.domain.acceptance.decide_attempt_outcome` and
`app.services.orchestration.build_obligations`, passes the six gate results the
bundle already carries, and prints the verdict. No binary runs; no symbolic
engine starts; no file is edited.

`[C]` is reached by passing `required={"V2": False, "V4": False}` to a function
call. That is a counterfactual, not a result: it is not achievable by evidence,
it needs two contract-owner edits, and quoting it as this bundle's outcome would
be the fabricated pass these records keep refusing to write. It is printed only
to show that nothing *else* stands in the way — the other four obligations pass
(V0, V1, V3, V5), which is what the candidate genuinely demonstrates.

## 3. Why both walls exist

`01-call-chain.txt` carries the greps:

- `app/services/orchestration.py:24-31` — all six gates declared `required=True`.
- `app/services/worker.py:305` — `evaluate_attempt` is called without a
  `required=` mapping, so those defaults are the bar.
- `routeb/attempt_writer.py:221` — `"V4": "not_run"`.
- `routeb/attempt_writer.py:228` — `"V2": "interface check not implemented in
  Route B executor"`.

Route B therefore sets two of six required gates to `not_run` by construction.
No candidate, however well repaired, changes that. This is not an evidence gap
on M3's side; it is a design fact, and it is the honest reason T8.3 stays
blocked rather than "M3 has not delivered V4 yet".

## 4. And nothing reads a V4 file anyway

`02-readers.txt` greps `app/`, `routeb/`, `scripts/`, `tools/`, `tests/` for
`v4-symbolic`, `v2-interface`, `gate-index`, `gate_index`: no match in Python,
HTML or JS.

- A **fake** V4 is inert. It cannot become a verdict.
- An **honest** V4 is inert too, until a writer path exists.

The second point is the one worth carrying forward: item 8 of record 125's
definition of done is not paperwork. A harness that satisfies items 1–7 and
stops there produces a file with no consumer — which is a worse outcome than
`not_run`, because it looks like progress.

## 5. What this asks of the contract owner, not of M3

Two questions, each answerable only by editing `contract.json` or the domain:

1. Is `interface` genuinely required for a **no-input** binary whose entry takes
   no arguments and reads no stdin? Route B has no interface check, so requiring
   it guarantees `inconclusive` forever.
2. Is `symbolic` required for this class of repair, given Route B cannot record
   it? Either the writer grows a V4 path, or the obligation is removed on
   purpose — not left as a permanent inconclusive.

Neither is M3's file to change, and this record does not change them.

## 6. Unchanged

- 124 bundle untouched: 31/31, `sha256(SHA256SUMS)` = `08288ee5…c41a`;
  `gate-index.json` still `V0 pass, V1 pass, V2 not_run, V3 pass, V4 not_run, V5 pass`.
- V4 `not_run`, `claimed_scope: null`. V2 `not_run`, `scored: false`.
  Neither got a substitute verdict.
- T8.3 blocked. One sample, one repair, one observation.

## 7. Reproducing

```sh
cd "$(git rev-parse --show-toplevel)"
python3 docs/handoffs/evidence/cwe416-verdict-guard-2026-11-06/show_verdict.py
```

Expected output is `00-verdict.txt` in the same directory. If it differs, the
code moved and this record is stale; the code is right.
