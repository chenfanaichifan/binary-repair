# Path A: selective call whitelist (2026-11-14)

Target-mode assembly only: the packet exposes direct call targets already used
by the original function, and the validator permits a call only to those exact
targets.  Standard `asm_roundtrip` remains leaf-only.

| model | baseline | AI verified | loop | non-loop |
|---|---:|---:|---:|---:|
| `deepseek-flash` | 0/12 | 6/12 | 6/6 | 0/6 |
| `deepseek-v4-pro` | 0/12 | 6/12 | 6/6 | 0/6 |

The whitelist did not lift the non-loop verified set.  Notable partial signal:
`heap-canary` candidate passed the security PoC but failed the short-input
stdout regression (it exited early), so it is not verified.

The call injection path now handles symbol relocations against both section-
backed and newly added PT_LOAD caves; CWE121 candidates were injectable but
failed native behavior.  This is a measured 0-result, not a hidden success.

Artifacts: full summaries contain native PoC evidence and candidate hashes.
No key or prompt is stored.
