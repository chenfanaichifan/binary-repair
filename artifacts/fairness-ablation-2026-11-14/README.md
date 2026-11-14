# Fairness ablation: localization vs repair-strategy scaffolding

Generated 2026-11-14.  Real provider (`deepseek-flash`) generated candidates on
macOS; every candidate was executed and gated by native PoC+regression in the
Linux x86-64 VM.  No API key, raw prompt or raw response is stored.

## Design

- 10 hard cases whose deterministic baseline fails while a correct repair exists
  in principle: six inlined-copy loop variants, CWE121 semantic bounds check,
  multicall, sprintf and non-constant-length copy.
- Conditions:
  - deterministic blind (`repair_any`)
  - deterministic target-aware (same target function/capacity hint)
  - AI blind (public assembly path, no target)
  - AI target-localized with contract levels `full`, `generic`, `none`
- Multiple repeats: 3 full-contract runs, 2 generic, 2 none.

## Result

| condition | verified / 10 |
|---|---|
| deterministic blind | 0 |
| deterministic target-aware | 0 |
| AI blind | 0 |
| AI target-localized `full` | 6 (3/3 runs) |
| AI target-localized `generic` | 6 (2/2 runs) |
| AI target-localized `none` | 6 (2/2 runs) |

- **Localization effect: +6** (target hint is necessary; blind AI cannot start).
- **Repair-generation effect: +6** vs target-aware deterministic, but both
  conditions received the same target hint; the AI produced code the template
  writer could not.
- **Contract strategy specificity effect: 0** on this set — `generic` and
  `none` contracts also solved all six loop cases.  The disassembly itself
  supplied enough information; this benchmark does **not** support a claim that
  detailed repair contracts are required.
- Six loop cases pass; CWE121, multicall, sprintf and non-constant copy fail
  (external calls/ABI beyond the leaf-only assembly path).  Repeats were stable
  at 6/10; the sample is not independent and no statistical generalization is
  claimed.

## Interpretation

The previous "increment 1" was under human target localization.  This ablation
makes the qualification explicit: the measured increment is **target-localized
repair generation**, not autonomous discovery.  Deterministic target-aware
baseline remains 0, so the repair-generation part is real; blind AI remains 0,
so localization scaffolding is currently necessary.
