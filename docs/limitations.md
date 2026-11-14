# Verification boundaries and current capability ceiling

This project proves bounded, evidence-gated repairs.  It is not a
general-purpose binary rewriter and does not claim universal correctness.

## What the oracle currently covers

- PoC trigger/non-trigger and regression behaviour;
- process exit code and crash status;
- exact stdout and the explicit `stdout_signature` gate;
- optional syscall-errno **set/unset** signature through
  `poc_runner`'s opt-in `errno_probe: "strace"` (a proxy; not a full TLS/libc
  errno read after the repaired function);
- container reparse, repaired-action identity, runtime tier and gate profile.

## What it does not cover

- exact errno values or `__errno_location()` TLS state after the function;
  the new optional `ld_preload` probe captures **process-exit** errno on native
  dynamic ELF only, while `strace` remains a syscall proxy;
- heap allocator internal layout/metadata, file-descriptor offsets, locks,
  signal handlers, locale, and other process-global state;
- whole-program equivalence; verification is scoped to the supplied
  PoC/regression cases and (when target-scoped) the declared function;
- arbitrary libc symbols: `symbol_resolver` has pure templates
  (`strlen/memcpy/memset/strcat/atoi`), syscall templates
  (`write/exit`), a reviewed `fputs(x, stderr)` rewrite, and a typed
  `malloc/free` refusal.  Memory-management semantics are not templated;
- general non-loop Path A/B success.  CWE121 is a single-function non-loop
  closure, not a family result.

## 4-model matrix conclusion

| model | AI verified |
|---|---:|
| deepseek-flash | 6/12 |
| deepseek-v4-pro | 6/12 |
| Qwen/Qwen3-8B (CN free) | 0/12 |
| Qwen/Qwen2.5-7B-Instruct (CN free) | 0/12 |

The two capable models solve the loop family (6/6); the two free small models
fail every case under the same prompt and symbol resolver.  Model swapping is
not the lever for non-loop repair; symbol/relocation and call-graph context are.

## Path B context A/B

One controlled case (`hard-multicall`): verified 0/1 with and without direct
callee context.  The context changed the failure mode, not the verified outcome.
This is a negative single-case result, not a general rejection of context.

## Non-negotiables

- No AI output, assembly acceptance, or successful injection is treated as
  verification; only the deterministic gate/evidence can promote a candidate.
- Unavailable evidence stays `not_run`/`unavailable`, never fabricated success.
- Capacity/coverage work is maintained on its own branch and merged only through
  a reviewed rebase/CI.
