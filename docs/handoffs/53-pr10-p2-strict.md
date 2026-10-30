# 53 — PR #10 p2 acceptance strictness fix

Base: `ca553c3` (M4 FAIL head).

## Restored strictness

- outcomes are limited to the six `Outcome` enum values;
- `success_within_scope` with any route whose obligations are all `not_run` is rejected;
- a success verdict with an all-not_run route is rejected;
- offline `--data-dir` requires explicit `--synthetic`;
- `--synthetic` requires `--data-dir`; no live-controller synthetic label.

## Negative tests

`tests/integration/test_p2_acceptance.py`:

```text
test_rejects_success_with_all_not_run
test_rejects_invalid_outcome_enum
test_synthetic_mode_requires_explicit_label
test_synthetic_flag_cannot_use_live_controller
test_synthetic_offline_finished_snapshot_still_passes
```

Command:

```bash
python -m pytest -q tests/integration/test_p2_acceptance.py
# 5 passed
```

Synthetic pipeline still exits 0 with `synthetic: true`; unreachable controller
still returns 2 BLOCKED.

Do not merge/tag until M1 updates PR #10 and M4/Lead approve.
