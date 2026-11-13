# Hard-case AI increment benchmark (2026-11-13)

This is the first benchmark aimed at the actual research question, not another
gate: deterministic baseline must fail while a correct repair exists; the AI
must produce a candidate accepted by a real native PoC + regression run.

## Cases

| case | baseline | AI |
|---|---|---|
| `inline-byte-loop` — inlined byte-loop into a 16-byte stack buffer; analyzer sees no copy call | `rejected` (deterministic candidate fails gate) | **AI assembly candidate verified** under native PoC in Linux VM |
| `cwe121-unchecked-strcpy` — CWE121 stack overflow; baseline `analysis_only`; correct fix requires a semantic bounds check | `analysis_only` | model returned a `call` in the assembly block; leaf-only validator rejected; no candidate |

## Result

- baseline verified: **0 / 2**
- AI verified: **1 / 2**
- AI increment: **1** on this hard-case set
- negative case is preserved honestly: CWE121 needs external calls/behavior
  (`printLine`, stderr/exit path) that the current leaf-only assembly path
  forbids; this is evidence for the paradigm-A gap, not hidden.

The AI call ran on macOS with the configured provider; candidate execution and
PoC/regression ran natively in the Linux VM.  Raw prompt/response and API keys
are not stored.  Candidate bytes are included for audit; `summary.json` records
model/latency/usage metadata only.

This is one hard case, not a general capability claim.  A larger benchmark and
the C/A route remain future work.
