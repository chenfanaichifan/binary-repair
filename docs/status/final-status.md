# Final status — 2026-11-08

This repository is the curated public snapshot of the accepted BinaryRepair MVP.

Current release: v1.1.0 (2026-11-08). The earlier v1.0.0 tag is the historical initial MVP snapshot and is not moved.
The source development repository remains
`chenfanaichifan/binary-repair`; the snapshot source is branch
`delivery/all-hands-2026-11-07` at
`b61774d04e793b3a5f34574df03ba6e1a034d700`.

## Acceptance state

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

The recorded run is Linux with Chrome CDP. Windows hosts are not the acceptance
record; they skip Linux-only cases and have POSIX-fixture differences. Use the
Linux run for the canonical count.

## Canonical evidence

```text
artifacts/p1-real-window-2026-11-07/
  controller/snapshot.json
  p2/p2-rc.txt
  p2/p2-result.txt
  v5-replay-2026-11-07/        16/16 HOST-SHA256SUMS

artifacts/p1-routea-v4-symbolic-2026-11-07/
artifacts/p1-routea-real-v4-2026-11-07/
artifacts/p1-routea-v4-input-2026-11-07/
artifacts/v4-harness-2026-11-07/
artifacts/cwe416-124-v4-rerun-2026-11-06/
artifacts/m4/v4-2026-11-07/
artifacts/m4-revalidation-ebc92a8/
artifacts/p1-v5-logs-2026-11-07/

docs/development/reviews/review-9-12-m4-verdict-2026-11-07.json
docs/development/handoffs/182-project-audit-2026-11-08.md
```

P1 job: `9247357c54714546a7ff84891f7766f8`  
P2: exit 0, `synthetic=false`, both routes `success_within_scope`.

## Recorded limitations

- **V4 is model scope.** It is not a binary-level proof or whole-program proof.
- **M4 verifier and Lead approver are the same operator.** Role-separated, not
  independent two-person review.
- **Review 9–12 original text is not recovered.** The review verdict is against a
  canonical reconstruction and must not be described as verbatim original.
- **Coverage is one public fixture family.** Other binaries, architectures,
  compilers and stripped production binaries are not covered.
- **Windows is not the acceptance environment.** Linux-only tests and POSIX
  fixtures are skipped or differ there.
- **No merge to the original development repository's main.** This public
  repository is a curated delivery snapshot with its own release tags.

## Boundaries

```text
private keys / credentials        not included
client binaries / private logs    not included
guest credentials                 not included
fabricated/regenerated V5 logs    not included
```

The host never executes uploaded or repaired binaries. Execution, compilation
and symbolic analysis belong to the disposable guest under the broker.
