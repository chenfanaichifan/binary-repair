# D04 heap-malloc ABI rejection analysis (2026-11-17)

- fixture: `fixtures/hard-cases/vuln-heap-malloc-x86_64.elf` sha256 `0f65a2d2ffe1ebf91f717d5edc78928cb8ee219e3f73e623b256f87bdcc4381f`
- candidate: sha256 `ea22260535efca37dca19404c700ce29e6da1f45b3af24d3903c8d27fdf6fb73` (matches Phase-8C: True)
- independent verifier: decision `rejected`, ABI check `failed`
- injected cave ABI: `ok=True`; declared function-block ABI: `ok=False`
- classifications: `generator_plan_incorrect` (primary), `abi_proof_insufficient` (primary), `verifier_rule_incorrect` (contributing rule gap), `analysis_evidence_insufficient` (Phase-8C rejection message lacked target resolution). `generator_patch_invalid` and `root_cause_inconclusive` are excluded.
- no verifier rule was modified; the candidate remains rejected.

The function block contains legal `call [rip+...]` to malloc/puts and a legal `jmp [rip+...]` tail call to free. The plan declared that whole function as `abi_blocks[0]` instead of the injected cave. The checker does not resolve memory-indirect targets/tail calls, so it reports `call_target_not_allowed` and `no_ret`. The cave itself passes ABI.
