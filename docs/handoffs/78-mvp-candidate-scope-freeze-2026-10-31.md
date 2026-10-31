# 78 — MVP candidate scope freeze — 2026-10-31

**Tag:** `mvp-candidate-2026-10-31`  
**Scope:** candidate / integration demonstration only. This is **not** a full MVP
acceptance tag and does not claim `success_within_scope`.

## Accepted basis

```text
Gate 4: PASS (strict unchanged round-trip scope)
Gate 5 Route A: PASS (final; record 51 signed, record 77 approved)
V4: PASS (model-level, bound 64; not binary-level/whole-program)
P3A v7 / P3B v6: checker PASS, LF SHA256SUMS
P4 v3: checker PASS 26/26, native manifest 6/6
```

## Fixture freeze (candidate scope)

The fixture is **FROZEN for the candidate scope**:

```text
original.elf: aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393
P3A candidate: c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
P3B candidate: 208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717
P4 roundtrip:  decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b
```

The signed Gate 4 record remains the historical record at its pinned hash; this
freeze record supersedes only the earlier "fixture NOT FROZEN" candidate status.

## Open item

```text
Gate 5 Route B: NOT RUN / deferred for candidate
```

Gate 5 Route B is not covered by `mvp-candidate-2026-10-31`; its separate record
remains open. No full-acceptance tag is created.

## Boundaries

```text
full MVP acceptance: NOT APPROVED
full-acceptance tag: NOT CREATED
fixture: FROZEN (candidate scope only)
MVP: candidate / integration only
```

Do not present this tag as a complete-MVP acceptance.
