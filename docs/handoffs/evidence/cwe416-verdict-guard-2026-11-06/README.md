# CWE416 — what the acceptance engine actually does with the 124 bundle

- Date: 2026-11-06 (host only; no guest window, no binary executed)
- Owner: Member 3
- Question: with V4 `not_run`, what verdict does this bundle get **in code**, and
  could a hand-written V4 have changed it?
- Answer: `inconclusive / required_check_not_run`, failing obligation
  `interface` — and a V4 would only move the failure to `symbolic`.

## 1. Why this exists

Record 125 argued V4 stays `not_run` because a hand-rolled harness cannot land.
That claim used prose about `scopes.py`, `attempt_writer.py` and
`acceptance.py`. Prose is checkable only by reading, so this pass replaced it
with a call into the real code, given the real `gate-index.json` from the 124
bundle.

Nothing here executes a binary. `show_verdict.py` imports
`app.domain.acceptance` and `app.services.orchestration`, feeds them the six gate
results the candidate already has, and prints the verdict.

## 2. What it says

```
[A] bundle as it stands        inconclusive / required_check_not_run / interface
[B] with `interface` not required   inconclusive / required_check_not_run / symbolic
[C] with both not required          success_within_scope, "4 required obligations passed"
```

`00-verdict.txt` is the run that produced those three lines.

- **[A] is the truth about this bundle.** Note the failing obligation is
  `interface`, not `symbolic`: the gates are evaluated in order and V2 comes
  before V4, so V4 is not even the first thing standing in the way.
- **[B] is why a V4 harness would not have bought a pass.** Take `interface` out
  of the required set and the attempt still fails, now on `symbolic`.
- **[C] is a counterfactual and must never be quoted as this bundle's outcome.**
  It requires two contract-owner edits, it is not achievable by producing
  evidence, and reporting it as a result would be exactly the fabricated pass
  these records keep refusing to write.

`[C]` also says "4 required obligations passed". Those four are V0, V1, V3 and
V5 — the four this candidate genuinely demonstrates, and the four the reviewer
already accepted.

## 3. Why both walls exist, in code

`01-call-chain.txt` has the greps. In short:

- `app/services/orchestration.py:24-31` declares all six gates `required=True`;
- `app/services/worker.py:305` calls `evaluate_attempt` without a `required=`
  mapping, so those defaults are what an attempt is judged against;
- `routeb/attempt_writer.py:221` writes `"V4": "not_run"` and `:228` writes
  `"V2": "interface check not implemented in Route B executor"`.

So Route B sets two of the six required gates to `not_run` by construction. That
is not a gap in M3's evidence; it is a design fact about Route B, and it is why
`success_within_scope` is unreachable from this bundle whatever the candidate
does.

## 4. Nothing reads the three review artifacts

`02-readers.txt` greps `app/`, `routeb/`, `scripts/`, `tools/`, `tests/` for
`v4-symbolic`, `v2-interface`, `gate-index` and `gate_index`: no match in Python,
HTML or JS.

That has two consequences, and the second is the uncomfortable one:

1. **A fake V4 file cannot help.** It would be inert. So "don't write a fake
   verdict" is enforced by the architecture, not only by discipline.
2. **A real V4 file cannot help either.** A harness that produces honest
   accounting still has no route into an obligation, because the writer does not
   read it. Item 8 of record 125's definition of done — a writer path — is
   therefore not paperwork; without it the other seven items change nothing.

## 5. What this does not change

- V4 stays `not_run`, `claimed_scope: null`.
- V2 stays `not_run` / `scored: false`. No substitute verdict was invented.
- V0, V1, V3, V5 stay `passed`; the 124 bundle is untouched (31/31,
  `sha256(SHA256SUMS)` = `08288ee5…c41a`).
- T8.3 stays blocked. No second sample is described.
- No contract file was edited. [C] was computed by passing a `required` mapping
  to a function call, not by changing `contract.json`.

## 6. Reproducing

```sh
cd "$(git rev-parse --show-toplevel)"
python3 docs/handoffs/evidence/cwe416-verdict-guard-2026-11-06/show_verdict.py
```

Expected: the three blocks in `00-verdict.txt`. If they differ, the code moved
and this record is stale — the code is right.

## 7. Files

| File | What it is |
|---|---|
| `00-verdict.txt` | the run: gate results, the three verdicts, and the reading |
| `01-call-chain.txt` | greps showing GATES, the call from the worker, and the two hardcoded `not_run`s |
| `02-readers.txt` | greps showing no code reads the three review artifacts |
| `show_verdict.py` | the script that produced `00-verdict.txt`; no hidden steps |
