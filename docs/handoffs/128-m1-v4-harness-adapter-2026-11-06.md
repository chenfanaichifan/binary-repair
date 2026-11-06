# 128 — one product V4 schema; M3 harness output goes through a converter

- Date: 2026-11-06
- Owner: Member 1 (host backend)
- Branch: `m1/t30-acceptance-ab-2026-11-05`
- Scope: schema ownership and a converter. No gate result changes.
- Not claimed: V4 pass, 124 upgrade, T8.3 relief, merge/tag/live success.

---

## 0. Status

| Item | State |
|---|---|
| Product V4 schema | `app/domain/v4.py` — `V4Evidence`, `write_v4_evidence` |
| M3's `v4_evidence.py` | **draft, not product**; no product import; superseded by the adapter |
| Harness converter | `app/domain/v4.py#from_v4_harness`, CLI `tools/v4_harness_to_evidence.py` |
| Actual M3 output | `v4-evidence.json` converts and validates |
| 124 V4 | **not_run**; producer file does not upgrade it |
| 124 outcome | `inconclusive / required_check_not_run / symbolic` |
| T8.3 | blocked |

## 1. One schema, one writer

The only product definitions are:

```
app/domain/v4.py::V4Evidence
app/domain/v4.py::write_v4_evidence
```

`tools/route_bundle_ingest.py`, `app/services/obligations.py` and the tests import
those names. M3's workspace file `v4_evidence.py` defines a separate dataclass
writer; it is a producer draft, not the product API, and must not be imported by
M3's next change. The product has no second schema and no second writer.

## 2. Minimal converter

```
M3 v4_harness output (v4-evidence.json)
        |
        v
from_v4_harness(data) -> V4Evidence
        |
        v
write_v4_evidence(path, evidence)
```

CLI:

```sh
python tools/v4_harness_to_evidence.py \
  --input v4-evidence.json \
  --output v4-symbolic.json
```

The converter maps only facts the harness actually records:

- `cases` -> calibration: `cases=2`, `known_good=True`, `known_bad=True`,
  `known_bad_rejected=True`, `passed=1`, `failed=1`; every known-bad case must
  be rejected;
- `states` -> exploration counts (`initial`, `deadended`, `errored`,
  `unconstrained`, `deferred`, `active`, `pruned`) plus `complete/unexplored`;
- `solver` + top-level `steps/max_steps` -> solver accounting (`queries` is the
  sum of eval/sat/unsat/unknown);
- `engine`, `hooks`, `replay`, `input_domain`, `property_text`,
  `target_entry`, `entry_address`, `contract_sha256` and per-case `cases` are
  preserved in `source`;
- `claimed_scope` is the literal `"model"`;
- `property_kind` is `"pointer-flow"` for this harness; empty
  `forbidden_ranges` is allowed only for pointer-flow, while `memory-range`
  requires at least one range. The converter omits the field rather than
  silently writing `[]`;
- `known_bad_rejected` requires **every** known-bad case to be rejected, not just
  one (no `any`);
- `not_claimed` must include the binary-level exclusion. When the candidate case
  is unsat with `free_calls == 0`, the empty-disjunction disclosure is forced if
  the harness did not already carry it.

A missing or inconsistent section raises `V4EvidenceError`; the converter does
not add defaults, a negative control, or accounting. The only derived text is
the conditional empty-disjunction disclosure.

## 3. What was verified

```
actual M3 v4-evidence.json
  -> from_v4_harness: passed
  -> candidate 46d16e99..., original c9c2632e...
  -> calibration 1/1, known_bad_rejected True
  -> exploration deadended=2, unexplored=[]
  -> solver queries=4
  -> source entry 0x4012aa, contract 8a2b408c...
```

Tests: `tests/test_v4_harness_adapter.py` (actual output conversion, writer
round-trip, empty-disjunction disclosure, missing accounting/negative-control
rejection); `tests/test_v4_evidence.py` covers the typed constraints and
calibration regressions.

## 4. 124 is not upgraded

The converter produces a typed artifact; it does not ingest it and does not
change `gate-index.json`, V4, the attempt or the run. 124 remains:

```
inconclusive / required_check_not_run / symbolic
V4 not_run
```

A producer file existing is not a gate result; V4 needs its own Route B path plus
independent review.

## 5. Checks

```
M1 full suite   500 passed / 2 skipped / 0 failed
```

CWE121 v2 hash and the 120 contract file/canonical hash gate are unchanged.

T8.3 blocked. No merge to `main`, no tag, no live success.
