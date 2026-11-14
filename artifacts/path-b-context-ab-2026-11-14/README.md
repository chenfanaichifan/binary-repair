# Path B direct-callee context A/B (2026-11-14)

One controlled case: `hard-multicall` (target `multicall_bad`), DeepSeek
`deepseek-flash`, same prompt/contract and target-mode call whitelist.  The only
difference is `scripts/export_with_callees.py` context for `helper_copy`,
`__stack_chk_fail`, and `puts` passed as `callee_context`.

| arm | AI status | native gate | verified |
|---|---|---|---:|
| without callee context | accepted | fail | 0/1 |
| with callee context | accepted | no_candidate (injection rejected) | 0/1 |

**Result: no verified improvement (0 vs 0).**  The context changes the failure
mode (candidate injection rejected rather than executed and failing) but does
not produce a verified non-loop repair.  This is a controlled negative result,
not evidence that context is useless; it is one case and the assembly path is
still constrained by leaf/call/injection policy.

Context: `context/multicall_bad.context.json` (callees exported; no missing
entries).  Native PoC ran in the Linux VM for the without-context candidate; the
with-context candidate had no injectable candidate.
