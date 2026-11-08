# Acceptance summary — 2026-11-08

**Decision:** accepted with recorded limitations.

The current authoritative status is `FINAL-STATUS.md`; canonical evidence is
listed in `delivery/INDEX.md`.

## Current state

```text
T8.3  COMPLETE
P1    success_within_scope
P2    ACCEPTANCE PASSED
V4    passed at model scope, not binary-level proof
124   V0-V5 passed; M4 confirmation recorded
118   VERIFIED (independent)
```

Recorded acceptance run:

```text
pytest -q   714 passed / 2 Linux-only skipped / 0 failed
e2e         12 passed (Chrome CDP)
```

P1 job: `9247357c54714546a7ff84891f7766f8`  
P2: exit 0, `synthetic=false`, both routes `success_within_scope`.

## Evidence

```text
delivery/p1-real-window-2026-11-07/
delivery/p1-routea-v4-symbolic-2026-11-07/
delivery/p1-routea-real-v4-2026-11-07/
delivery/p1-routea-v4-input-2026-11-07/
delivery/v4-harness-2026-11-07/
delivery/cwe416-124-v4-rerun-2026-11-06/
delivery/m4/v4-2026-11-07/
delivery/m4-revalidation-ebc92a8/
delivery/p1-v5-logs-2026-11-07/
```

## Reading order

1. `FINAL-STATUS.md`
2. `docs/acceptance/LIMITATIONS.md`
3. `delivery/INDEX.md`
4. `docs/reviews/review-9-12-m4-verdict-2026-11-07.json`

## Historical

`docs/acceptance/HISTORICAL-ACCEPTANCE-2026-10-31.md` is the earlier CWE-121
MVP acceptance record. It is retained for history and is not the current
acceptance state.
