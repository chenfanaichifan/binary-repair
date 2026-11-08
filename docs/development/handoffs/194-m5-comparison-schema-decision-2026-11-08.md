# 194 — M5 answer: comparison schema

Decision: yes, field-level schema for v1.1.2.

Artifact: `docs/interfaces/behavior-comparison-v1.md`

Key rule:

```text
not_provided | available | invalid
```

`invalid` is unavailable, never pass. `same` is not acceptance evidence;
`different` is not a failure verdict by itself.

M2 can implement the draft now. M5 adds validation; M1 exposes `invalid` in the
endpoint. v1.1.1 is not changed.
