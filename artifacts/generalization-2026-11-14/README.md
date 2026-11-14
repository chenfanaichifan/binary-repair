# Non-loop generalization triage (2026-11-14)

Three non-loop assembly cases, DeepSeek `deepseek-flash`, same prompt/contract
and target-mode call whitelist.  Native PoC ran in the Linux VM.

| case | AI status | injection | native gate | classified reason |
|---|---|---|---|---|
| hard-multicall | accepted | success (`new-pt-load`, 81 B, 2 relocations) | fail | model semantics (no `no_candidate_reason`) |
| hard-sprintf | accepted | none | no_candidate | `assembly_assemble` (assembler rejected `^`) |
| hard-nonconst | accepted | success | fail | model semantics |

Result: **0 new verified non-loop cases**.  The important change is that
failures are now typed: only the syntactic assembler failure is a
`no_candidate`; the other two reached native execution and failed behaviorally.
No source was modified per case; this is the current generalization ceiling.
