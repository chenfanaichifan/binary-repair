# 92 — T6.0 baseline migration (2026-11-05)

**Status:** baseline established for the live-bridge work; documentation only, no product code changed, no gate status changed, no merge/tag.

**Branch:** `integration/live-bridge-2026-11-03`, created from `origin/post-final/host-importer-broker` @ `1da22ff` (D0).

## What was done

1. Created the live-bridge branch from the post-final baseline in a separate worktree, so the existing consolidation worktree and its uncommitted files were not disturbed.
2. Carried the three documentation commits from the consolidation line by cherry-pick:
   - `77f0650` docs: archive live-bridge records and add documentation map
   - `39f4515` docs: translate remaining Chinese documents to English
   - `da7fd7e` docs: add onboarding handoff for a new agent
3. Conflict resolution: `docs/handoffs/BOARD.md` update log conflicted between the post-final board and the newer 2026-11-04 document. The conflict was resolved in favour of the newer translated document; older duplicate rows remain available in git history. No production file was touched.
4. Preserved the newer uncommitted documentation from the consolidation worktree and carried it onto the branch:
   - `HANDOFF.md`, `MEMORY.md` (record-90 review state)
   - `docs/handoffs/90-live-bridge-continuation-2026-11-05.md` (untracked there, added here)
5. Confirmed baseline product files exist on the branch: `workers/route_a/*`, `tools/host_importer.py`, `tools/host_broker.py`, `docs/handoffs/INTERFACE-v1.md`; `app/services/orchestration.py` already passes `expected_sha256=None` (post-final fix preserved).

## Observed checks

Run in the baseline worktree on this Windows host, Python 3.14.6, pytest 9.1.1:

```text
python -B -m pytest tests/unit/test_acceptance.py -p no:cacheprovider
-> 29 passed, exit 0

python -B -m pytest tests/integration/test_host_broker.py -p no:cacheprovider
-> 2 passed, exit 0
```

Host note: the host-broker test needed the local pytest temp-directory shim because this host's Windows sandbox cannot access `0o700` temp directories; the shim changes only temp-directory permissions, not test code or product code.

## Boundaries

- No product code, fixture, contract, or acceptance rule changed; this is a documentation/baseline migration.
- No gate status changed: Gate 4/5/6 and the fixture scope remain as recorded.
- No merge, no tag; the branch is the working baseline for T6.1/T6.3/T7.1 host-side work and later guest work.

## Next

- Host-only: T6.1 ingest conformance, T6.3 controller read surface, T7.1 flow endpoints, P0.4/P0.5.
- Guest/VM: record 88 staging/snapshot note is still required before T6.2 conformance; `tools/p2_acceptance.py` remains the only live-pipeline gate.
- M5 branch records 91 and the M4 verifier row remain on the M5 branch; they are not merged here.
