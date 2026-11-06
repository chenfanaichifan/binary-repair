# 135 — M1 pin and count correction (2026-11-06)

- Date: 2026-11-06 (measurement window 16:25–16:40 +0800)
- Owner: Member 1
- Scope: **documentation only.** No code, contract, fixture, ref, merge or tag
  was changed by this record.
- Supersedes:
  - record 132's pin table (`1938c31` / `6d67140`);
  - record 133's `449 passed / 2 skipped` line and the same line in the
    `d1ce352` commit message;
  - the `506 passed / 9 skipped` line in `6d67140`'s `MEMORY.md` bullet.

## 0. Corrected counts (the sentence this record exists for)

```text
d1ce352:        449 / 9 / 0
6d67140/41ff540: 513 / 9 / 0
```

`integration/live-bridge` is **`7817a20`** now; `6d67140` is only an ancestor.
Canonical is pinned at **`d1ce352`**; `1938c31` and `dc3bcd3` are history and
must not be used as current pins.

## 1. Fresh remote pins

Measured with `git ls-remote origin` (SSH; HTTPS agrees):

```text
d1ce352f60057ab3cd389c6af609c7b5ed3bcefd  refs/heads/canonical/m1-m5-integration
7817a20cd5a215e4423de6e045bf754691671120  refs/heads/integration/live-bridge
```

| Ref | Head | Status |
|---|---|---|
| `canonical/m1-m5-integration` | **`d1ce352`** | current pin |
| `integration/live-bridge` | **`7817a20`** | current head |
| `6d67140` | ancestor of `7817a20` | audited commit, **not** the head |
| `41ff540` | merge inside that ancestry | tested, **not** the head |
| `1938c31` | history | superseded; not a current pin |
| `dc3bcd3` | history | superseded by `d1ce352` |

`134-partial-report.json` is the 16:16 probe snapshot of the then-heads
(`1938c31` canonical, `6d67140` live). Its `canonical`/`followup` coordinates
are historical evidence, not current pins.

Ancestry proof:

```text
$ git merge-base --is-ancestor 6d67140 7817a20     # exit 0
$ git rev-list --left-right --count 6d67140...7817a20
0	2
```

`7817a20` is `0233d34` (obligation ordering) plus one doc commit on top of
`6d67140`; `6d67140` remains a valid historical reference, not the head.

## 2. Full-suite counts, re-measured

Command (full suite, nothing ignored, `tests/e2e` included):

```bash
python -m pytest -q -o addopts=""
```

| Tree | Result |
|---|---|
| canonical `d1ce352` | **449 passed / 9 skipped / 0 failed** |
| integration `6d67140` | **513 passed / 9 skipped / 0 failed** |
| integration `41ff540` (merge) | **513 passed / 9 skipped / 0 failed** |

### Why `d1ce352` was written as `449 / 2 / 0`

The earlier number excluded `tests/e2e`. The 9 skips on `d1ce352` are the 7
`tests/e2e/test_gui_journey.py` skips (`Microsoft Edge is not installed;
browser e2e cannot run`) plus the 2 `tests/test_fixture_v3_manifest.py` skips
(`ELF execution requires Linux`). 7 + 2 = 9. A skip is not a pass, so the full
row is `449 / 9 / 0`, not `449 / 2 / 0`.

### Why `506 / 9 / 0` is withdrawn

`6d67140`'s `MEMORY.md` bullet says "full suite 506 passed / 9 skipped". No
tested tree reproduces 506. Measured on the same suite:

| Tree | Result |
|---|---|
| `c217046` (live line, partial, no V4) | 419 / 9 / 0 |
| `3f21d31` (m1/t30 line, V4, no partial) | 503 / 9 / 0 |
| `41ff540` (merge) | 513 / 9 / 0 |
| `6d67140` (merge + docs line) | 513 / 9 / 0 |

The accepted count for `6d67140` and `41ff540` is **513 / 9 / 0**. The
`506/9/0` line is superseded; it is not a second, equally valid measurement.

`41ff540 → 6d67140` changes only `MEMORY.md` (+1 line), so the two trees are
the same test tree: 513 / 9 / 0 in both.

## 3. What did not change

- **`partial` passthrough** — `aggregate_job_usage` keeps the wide
  `job_id = ? OR attempt_id IN (attempts JOIN runs)` query and returns
  `partial = len(real) != len(rows)`; `_ai_usage_for_job` returns the
  aggregate untouched; the plan fallback is
  `{"input_tokens": ..., "output_tokens": ..., "partial": False}`. Present at
  `d1ce352`, `6d67140` and `7817a20`.
- **CWE121 v2 hash** — `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`
  recomputed through `app.domain.contracts` in the canonical tree, and
  `tests/test_fixture_contract.py` passes.
- **120 gate** — canonical `d1ce352` carries the `v3 none` schema/intake gate
  (`test_v3_none_*`, `test_v2_rejects_input_mode_field`, the no-input intake
  cases); the 84-test gate run below is green. The real CWE416 no-input
  `contract.json` (`c1684f15…`) is a live-bridge `6d67140` fixture, not a
  canonical file; this record does not move it and does not change the gate
  definition.
- **T8.3 stays BLOCKED**; no merge to `main`; no tag; no live-success claim.

## 4. Observed commands

```text
# canonical d1ce352, full suite (9 skips: 7 Edge e2e + 2 Linux ELF)
449 passed, 9 skipped, 1 warning

# integration 6d67140 / 41ff540, full suite
513 passed, 9 skipped, 1 warning

# canonical d1ce352, CWE121 + 120 gate selection
84 passed

# canonical d1ce352, CWE121 canonical hash
24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
```

## 5. Why the pinned documents are not edited in place

`d1ce352` is an immutable pinned commit and `133-m5-partial-usage-merge-2026-11-06.md`
lives inside it; rewriting that file would move the canonical head and break
the pin this record establishes. The same applies to `6d67140`'s `MEMORY.md`
and to record 132's committed table. Those lines are therefore **superseded by
this record** rather than rewritten. Runtime consumers should cite
`d1ce352` (canonical) and `7817a20` (integration), and measure counts with the
full suite rather than copying an older table.
