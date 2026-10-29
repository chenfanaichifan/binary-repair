# 49 — PR #10 test fix

Base: `cd63e21` (PR #10 head at report time).
Change: restore the removed identity tests and the static-bundle V0 assertion;
no production code and no test relaxation.

```text
test_routeb_identity_passes_only_with_matching_original
test_routeb_identity_fails_on_original_mismatch
static bundle: assert payload["results"]["V0"] == "not_run"
```

Command:

```bash
python -m pytest -q tests/integration/test_attempt_writer.py
# 6 passed
```

Hand to M1 as a new PR #10 head. Do not merge or tag
`mvp-integration-2026-10-31` until M4 behavioral PASS and Lead written approval.
