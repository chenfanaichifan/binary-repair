# Path B injection retry / failure classification (2026-11-14)

Root cause of the earlier `hard-multicall` `no_candidate` was **not** Patcherex2
symbol/space failure:

```text
assembly validation: ValueError: forbidden assembly construct: ud2
```

The assembly validator rejects `ud2` by policy.  The benchmark now:

- classifies the failure (`assembly_forbidden`, token, stage);
- exposes `candidate.no_candidate_reason` and summary counters;
- gives the model one feedback retry with the validator error, without
  rewriting `ud2` automatically;
- records every attempt.

Fresh DeepSeek run:

- model returned a non-`ud2` assembly on the first attempt;
- injection succeeded (`method=new-pt-load`, 81 bytes, 2 call relocations);
- native gate: **fail** (candidate semantics), not `no_candidate`.

This moves the bottleneck from validator/injection to **model repair semantics**
for this case.  It does not claim a verified repair.
