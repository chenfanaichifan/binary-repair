# 134 — `partial` is already at live-bridge `6d67140`; `1938c31` is the ancestor without it

> **Correction (2026-11-06, record 135):** this is a historical audit of
> `6d67140`, which is now an **ancestor** of `integration/live-bridge`
> `7817a20`, not its head. Current pins: canonical **`d1ce352`**
> (`449 / 9 / 0` full suite) and integration **`7817a20`**
> (`6d67140` and `41ff540`: `513 / 9 / 0`). `1938c31` and `dc3bcd3` are history
> and are not current pins. See `135-m1-pin-and-count-correction-2026-11-06.md`.

- Date: 2026-11-06 (audit window 16:10–16:30 +0800)
- Owner: Member 1 (host backend / acceptance)
- Scope: read-only audit of `integration/live-bridge` @ `6d67140`, and its
  relation to the `canonical/m1-m5-integration` baseline @ `1938c31` (record
  132's pin when the audit started; the branch head moved during the audit —
  section 4; the current pin is `d1ce352`). No product code was changed and
  this audit moved no ref, merge, tag or push.
- Probe: `probe_134_partial_6d67140.py` — 15/15 checks read from git objects
  (`134-partial-report.json`).
- Evidence: `134-m1-live-bridge-partial-evidence-2026-11-06.txt` (419 lines).

## 0. Verdict

All three required behaviours are already in `6d67140`:

| # | Requirement | Evidence at `6d67140` |
|---|---|---|
| 1 | `aggregate_job_usage` returns `partial` | `app/services/model_calls.py:98`; field at `:136` — `"partial": len(real) != len(rows)` |
| 2 | `_ai_usage_for_job` passes it through | `app/controller_api.py:267`; `:302` — `return aggregate_job_usage(...)` untouched |
| 3 | plan fallback is `partial=false` | `app/controller_api.py:315` — `"partial": False` |

**No patch is needed and none was applied at `6d67140`.** The request's
conditional ("if absent, add it to live-bridge") is therefore not triggered;
no commit was added to either head. A "fix" commit would move the pin that
record 132 and its consumers already use, for no behavioural gain. While this
audit ran, live-bridge fast-forwarded to `7817a20` (16:21:56, a descendant); it
still carries all three statements and the V4 gate — section 3 records the
movement and its own test run.

The three facts are not merely present: they are tested (section 2), and the
probe re-checks them against immutable git objects, so a later rewrite that
drops the field fails the audit instead of passing silently.

## 1. What the code does

`aggregate_job_usage` keeps the wide canonical query (`job_id` or
`attempt_id`-via-`runs`; the `OR` cannot double count a row):

- no calls → `None`
- calls but no real tokens → `None`
- some NULL, some real → sum the real rows, `partial=True`
- all real → sum, `partial=False`

A NULL count is never read as zero and never erases a sibling's real usage; it
only marks the sum partial. `_ai_usage_for_job` returns the aggregate unchanged
whenever `model_calls` rows exist, including when the aggregate is `None`
(calls exist, none carries real tokens) — it does not fall back to the plan and
mix two sources under one label. Only a job with no `model_calls` rows at all
reads the single stored plan record, which is complete by construction, so the
fallback reports `partial: False`.

## 2. Tests at `6d67140`

Run in detached worktree `_m1-work/audit-6d67140`; interpreter
`role5-kit/.venv` (pytest 8.4.2).

| Suite | Result |
|---|---|
| `tests/integration/test_ai_usage_helper.py` | 6 passed |
| `tests/integration/test_ai_usage_sources.py` + `test_assistant_plan.py` | 15 passed |
| `tests/test_v4_harness_adapter.py` + `test_cwe416_124_v4_rerun.py` | 11 passed |
| `tests/test_fixture_contract.py` + `test_cwe416_noinput_fixture.py` | 2 passed |
| full suite | **513 passed, 9 skipped, 0 failed** |

Directly named pins for the three questions:

- `test_a_null_row_keeps_the_real_sum_and_passes_partial_through` →
  `{9, 3, partial: True}`
- `test_complete_rows_are_summed_and_not_partial` → `partial: False`
- `test_plan_fallback_reports_not_partial` → `{7, 2, partial: False}`
- `test_one_incomplete_call_keeps_the_sum_and_marks_it_partial` → API-level
  `partial=True`
- `test_all_complete_calls_are_not_partial` → API-level `partial=False`
- `test_partial_model_call_is_none_not_zero` → a lone NULL row is `None`

Note: `6d67140`'s own `MEMORY.md` says "full suite 506 passed / 9 skipped".
That line is **superseded** (record 135): the accepted count is
**513 / 9 / 0** for both `6d67140` and `41ff540`, and no tested tree reproduces
`506` (this host measures 513 / 9; section 2). The delta does not touch the
three checks.

## 3. Where `partial` came from

Both partial commits sit on the live line, before the merge:

- `de48d6a` `feat(usage): report a partial sum instead of discarding it`
- `165891d` `feat(ai-usage): pass partial through instead of dropping it`

They are ancestors of `6d67140` and **not** of `1938c31`. The topology is:

```
6d67140 (docs)  ->  41ff540 (merge 3f21d31 into c217046)
                      |-- c217046  live line, carries partial
                      `-- 3f21d31  m1/t30 line, carries the typed V4 stack
```

So the merge that produced `6d67140` kept the live line's `partial` and added
m1/t30's V4 work. The three checks in section 0 are the **post-merge** state,
not an inheritance assumption.

### Head movement after the audited commit

`integration/live-bridge` fast-forwarded while this audit ran:

| Time (+0800) | Commit | Change | `partial` | V4 |
|---|---|---|---|---|
| 16:21:39 | `0233d34` | fix(api): order obligation rows V0..V5 | kept | kept |
| 16:21:56 | `7817a20` | docs(api): pin the obligation evidence contract | kept | kept |

- `rev-list --left-right --count 6d67140...7817a20` = `0 2`: a descendant, no
  rewrite.
- `7817a20` adds only `app/controller_api.py` ordering (+16/−2) and a doc; the
  partial lines stay at `model_calls.py:136` / `controller_api.py:315`, and
  `app/domain/v4.py` is untouched.
- targeted suites at `7817a20`: 21 partial-file tests + 11 V4/124 tests pass.
- This record **audits `6d67140`** (the commit the request names). `7817a20`
  is measured here but is not audited as a pin; pin one commit and cite it.

## 4. Relation to canonical `1938c31`

```
merge-base(1938c31, 6d67140)        = 1938c31
rev-list --left-right --count       = 0   66      # left=canonical-only, right=live-only
```

- `1938c31` is a strict ancestor of `6d67140`: 0 commits on the canonical side,
  66 on the live side.
- `1938c31` carries **no** `"partial"` field in either file and has **no**
  `app/domain/v4.py`.
- Therefore `6d67140` is not "`1938c31` + docs"; it is the V3 baseline plus the
  M5 partial line and the whole typed V4 stack.

### Canonical follow-up, as measured

The canonical **head was moving while this audit ran**; the commits are
immutable, the head is not:

1. **~16:01** — record 132 pins `1938c31`.
2. **16:11:01** — `dc3bcd3` (record 133): parent `1938c31`; 6 changed files;
   adds only the `partial` semantics; still **no** `app/domain/v4.py`.
3. **16:16:40** — `d1ce352` "merge(canonical): bring the v3 no-input baseline
   in with the partial usage fix": parents `dc3bcd3` + `40a4153`; 26 files;
   keeps `partial` (`model_calls.py:137`, controller `:314`); still **no**
   `app/domain/v4.py`.

`dc3bcd3` and `6d67140` are siblings (`1 / 66`); 135 paths differ. `d1ce352`
adds the V3 no-input baseline on top of the partial commit; it is not a merge
of live-bridge and does not bring V4.

So, explicitly:

- **`partial`**: canonical has already followed, first at `dc3bcd3`, retained
  by `d1ce352`. This is a **new canonical commit**, not a rewrite of
  `1938c31`. `1938c31` remains a valid immutable baseline but stopped being
  the branch head at 16:11; every pin must repeat `git ls-remote` (132's own
  rule), never copy an earlier table.
- **V4 / `verified_by` / 124**: canonical has **not** followed at `1938c31`,
  `dc3bcd3` or `d1ce352` — none has `app/domain/v4.py`. It follows only when
  (a) M4 replays the 124 V4 evidence and records `verified_by="m4"`, (b) the
  Lead accepts that replay, and (c) canonical explicitly merges the V4 stack
  from live-bridge. No date is claimed here.

## 5. Downstream rule — do not mix

| Consumer need | Use | Do not use |
|---|---|---|
| `partial` in `ai_usage` | canonical `d1ce352`; integration `7817a20` (`6d67140` audited) | `1938c31`; `dc3bcd3`; `m1/t30` @ `e6689e4` |
| typed V4 evidence / `replay.verified_by` gate / 124 V4 ingest | integration `7817a20` (`6d67140` audited) | `1938c31`, `dc3bcd3`, `d1ce352` (none has `v4.py`); `m1/t30` has V4 but no `partial` and is not the integration head |
| combined acceptance (V4 + partial) | integration `7817a20` (current head; `6d67140` is an ancestor) | a mixture of commits, or any ref without its own run |
| CWE121 v2 / CWE416 120 pins | canonical `d1ce352` for CWE121; live-bridge `6d67140`/`7817a20` for the 120 fixture (section 7) | — |

`1938c31 ⊂ 6d67140` as history. `dc3bcd3 ∥ 6d67140` and `d1ce352 ∥ 6d67140`
as siblings. Neither relation permits calling the trees interchangeable,
cherry-picking one onto the other, or labelling `1938c31` as "canonical with
partial + V4".

## 6. V4 `verified_by` gate and 124 at `6d67140` (unchanged)

- `Replay.verified_by: Literal["m4"] | None` — `app/domain/v4.py:131`
- `validate_v4_evidence(..., require_independent=True)` raises unless the value
  is exactly `"m4"` — `app/domain/v4.py:432`
- production callers pass `require_independent=True`:
  `app/services/obligations.py:160`, `tools/route_bundle_ingest.py:363`
- the harness adapter/writer never sets the marker
  (`test_adapter_and_writer_never_add_m4_verification`)

The 124 rerun bundle **declares** `V4: passed` with `v4-symbolic.json`, but
ingest validates it, sees no M4 marker, and downgrades:

```
V0 passed  V1 passed  V2 passed  V3 passed  V4 not_run  V5 passed
attempt: inconclusive / required_check_not_run / symbolic
symbolic obligation: not_run
run phase: screening
```

No `success_within_scope`, no gate upgrade. `tests/integration/test_cwe416_124_v4_rerun.py`
asserts exactly this and passes.

## 7. Contract pins recomputed at `6d67140`

| Pin | File sha256 | Canonical hash |
|---|---|---|
| CWE121 v2 `contract.json` | `15f6b492…0ad8df` | `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` |
| CWE416 120 no-input `contract.json` | `8a2b408c…0e3c3b` | `c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c` |

Both are recomputed through `app.domain.contracts` (not copied from a note),
and the fixture tests in section 2 pass.

## 8. Constraints

- **T8.3 blocked** — `6d67140`'s record says "T8.3 BLOCKED; no merge to main
  (still 472aa94), no tag, no live-success claim." This audit adds nothing.
- `main` remains `472aa94`; no tag was created; no live-success claim is made.
- No ref moved by this audit: the audit checkout is a detached worktree at
  `6d67140`. Both branch heads moved on other people's commits while the audit
  ran (live-bridge section 3, canonical section 4); this record reports them,
  does not repin them and does not claim them as M1's.

## 9. Residual

- `app/controller_api.py:297-298` at `6d67140` has a cosmetic comment seam
  ("...including when their / Calls exist..."), inherited from `c217046`.
  It does not change behaviour and was not fixed, because a commit would move
  the pinned head. Canonical's copy (`dc3bcd3`) is clean.
- The API JSON carries `partial`, but the static UI formatter
  (`app/static/js/poll.js:62-66`) prints only input/output tokens and drops the
  flag. That is M2's copy surface; flagged here, not changed.
- The audit venv uses pytest 8.4.2 while `requirements.txt` asks for `>=9`;
  the suite is green, but a future run should use the pinned toolchain.

## 10. Replay

```
python3 probe_134_partial_6d67140.py --repo binary-repair --json 134-partial-report.json
cd _m1-work/audit-6d67140
../../role5-kit/.venv/bin/python -m pytest \
  tests/integration/test_ai_usage_helper.py \
  tests/integration/test_ai_usage_sources.py \
  tests/integration/test_assistant_plan.py \
  tests/test_v4_harness_adapter.py \
  tests/integration/test_cwe416_124_v4_rerun.py \
  tests/test_fixture_contract.py \
  tests/integration/test_cwe416_noinput_fixture.py
git -C ../../binary-repair ls-remote origin \
  refs/heads/canonical/m1-m5-integration refs/heads/integration/live-bridge
```
