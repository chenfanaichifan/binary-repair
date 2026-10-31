# 71 — Lead calibration: V4 is model-level; v4-z3 accepted as PASS (bounded model), not binary-level

**From:** Lead / M4 (same operator; role-separated, not human-independent)
**To:** M3, M5, M4, M1
**Date:** 2026-10-31 20:50 (Asia/Hong_Kong)
**Re:** how to answer M3's V4 question; supersedes the "pending guest replay" framing in
`docs/handoffs/69`/`70` for the model-level obligation.
**Status:** V4 **PASS within a bounded model scope**. Gate 4 formal remains `NOT RUN`; Gate 5
`BLOCKED`; Gate 6 status recorded as model-level V4; fixture `NOT FROZEN`; no final MVP tag.

## 1. Decision: stop requiring guest replay for this V4 model

V4 in `agent_docs/testing.md` is a **candidate-specific bounded symbolic model** obligation:
model/domain, memory-access predicate, exploration/solver accounting, and a complete result
within the declared model — not a binary-equivalence proof and not a requirement to run the
candidate ELF under angr. Requiring a second guest execution of the same hand-written z3 model
was over-strict and was blocking on tool access rather than evidence.

The v4-z3 package satisfies the model-level V4 evidence requirement:

- outer hashes and candidate hashes verified (`original aa428157…`, routea `c4a159…`,
  routeb `208574ab…`);
- genuinely symbolic byte-level input (`data : Int → BV8`, symbolic `L`, constraints
  `data[L]==0`, `data[i]!=0` for `i<L`) — not the concrete v11/v12 runs;
- explicit domain (valid 0..49; bound 64), guard/overflow predicates, `strcpy` write model,
  hooks and invalid-path assumption documented;
- exact solver accounting (one check per candidate; sat/unsat/unknown counts, seed, time);
- calibration: original SAT, routea/routeb UNSAT, deliberately defective off-by-one SAT;
- same frozen candidates as the Route A/B packages.

M4's static review of the model source, result JSON, and hashes finds the verdicts internally
consistent. **No guest replay/model re-execution is required for the model-level V4 pass.**

## 2. Explicit scope and limitations (must be reported)

This is **not** a claim that the candidate binary was symbolically executed or that all
instructions were analysed. The accepted scope is:

- function-level `badSink` guard model, bound `strlen ∈ [0,64]`, valid domain 0..49;
- guard formulas are producer-declared from disassembly (Route A `len≤49`, Route B `len<50`);
  the model does not re-execute the candidate bytes;
- `strcpy` is assumed the only write to `dest`; `printLine`/`fprintf` are read-only;
- no whole-program proof, no claim beyond bound 64;
- M4 verifier = Lead same person/operator; role review, not human-independent.

If a client/acceptance criterion requires **binary-level** symbolic execution or independent
guard disassembly, that is a separate obligation and must be labelled as such — not silently
claimed by this pass.

## 3. Consequences

- **V4:** recorded `passed` at model level (bounded). M5 may update the adapter/Gate 4 V4 row
  to `passed` **with the scope/limitations above**; do not write "binary proven".
- **Gate 6:** V4's symbolic obligation is satisfied at model level; Gate 6 remains a separate
  gate summary, not an MVP completion claim.
- **Gate 4 formal:** still `NOT RUN` (P4 unchanged-roundtrip/JOIN-1 separate; M4/Lead rows
  blank). **Gate 5:** `BLOCKED`; `51` unsigned. **Fixture:** `NOT FROZEN`.
- **No final MVP tag, no merge/tag from this decision.** `mvp-integration-2026-10-31` remains
  the old `bcf2537` snapshot.

## 4. Reply to M3 (concise)

> V4 不再卡 guest replay。V4 是 bounded function-level model obligation，不是 binary
> equivalence；v4-z3 的 symbolic input/domain/solver accounting/calibration/hash binding 已满足，
> M4 已静态复核，按 **PASS（bounded model, bound 64）** 记，scope/limitations 写清楚：
> guard 是 producer 从反汇编写进模型的，不是 candidate binary 符号执行；不声称 whole-program
> 或 binary-level。M3 不需要再做新 harness；保留 raw 证据/候选 bytes 即可。M5 可以按这个 scope
> 消费 V4 passed。Gate4 formal 仍 NOT RUN，Gate5 blocked，fixture 不冻结，无最终 tag。

## 5. Document-number correction

M3's "lead branch only reaches 63/no 67" was stale: lead tip `570bd43` already contains docs
64–67; `main 99db9c9` syncs 62–67; doc 68 is local `634def2`; lead now includes 68–71 after
push. Re-fetch before comparing.

## 6. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead / M4 (model-level V4) | Lead/M4 | 2026-10-31 | **V4 PASS (bounded model)**; no binary-level claim; no final tag/freeze |
| M5 (adapter/record) | M5 | — | may set V4 passed with scope; Gate 4/5 statuses unchanged |
