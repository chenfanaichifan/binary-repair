# M4 V4 marker — model-scope CWE416 sample — 2026-11-07

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
this is role-separated verification, not an independent two-person signature.
**Scope:** the T8.3 CWE416 no-input sample only. This is model-scope evidence,
not a binary-level proof.

This is a **post-Gate-0 V4 record**. It does not change the Gate 0 acceptance
record or D5 (`V4=not_run` for that round) in `docs/handoffs/142` and
`docs/handoffs/149`. It writes a separate M4-owned marker; the producer's
`v4-symbolic.json` is not edited.

## 1. Guest and self-check

```text
guest:  10.11.0.132:2222
user:   m4verify (uid 1004, no sudo)
cd /opt/binrepair-handoff/M4-v4-handoff-2026-11-06
sha256sum -c SHA256SUMS        -> exit 0, 12/12
sh run_selfcheck.sh            -> exit 0, 18/18 checks, recipe identical
sh verify_all.sh               -> exit 0, ALL PASS 3/3
```

The end-to-end `verify_all` output is byte-identical to
`9c6eeda7684f2e405fbceb83fec4a3962687559b1d35e738431c631b7d58ca8c`.

Logs: `m4-selfcheck.log`, `m4-verify-all.log`.

## 2. Two independent harness runs

Both commands were run from `/opt/binrepair-handoff/T8.3-evidence-2026-11-06`:

```text
/opt/angr-venv/bin/python v4/v4_harness.py \
  --candidate candidate/candidate.elf \
  --original fixture/original.elf \
  --contract fixture/contract.json \
  --out /tmp/m4-run-a.json --replay-runs 2

/opt/angr-venv/bin/python v4/v4_harness.py \
  --candidate candidate/candidate.elf \
  --original fixture/original.elf \
  --contract fixture/contract.json \
  --out /tmp/m4-run-b.json --replay-runs 2
```

| Field | Run A | Run B |
|---|---|---|
| exit | 0 | 0 |
| JSON size | 5172 | 5172 |
| output SHA256 | `9c6eeda7…8ca8c` | `9c6eeda7…8ca8c` |
| replay digest | `cb2137a2…cb14` | `cb2137a2…cb14` |
| replay runs / identical | 2 / true | 2 / true |

`cmp -s run-a.json run-b.json` exited 0. The two files are byte-identical.

## 3. Five criteria

| # | Criterion | Observed | Result |
|---|---|---|---|
| 1 | candidate / original / contract identity | `46d16e99…fcd0` / `c9c2632e…23c9` / `8a2b408c…e3c3b` | PASS |
| 2 | known_good | `holds`, sat=0, unsat=1, steps 11/64 | PASS |
| 3 | known_bad control | `violated`, sat=1, unsat=0, steps 14/64 | PASS |
| 4 | independent replay | two runs, two invocations, byte-identical output; replay digests identical | PASS |
| 5 | completeness and scope | complete=true, unexplored=[], unknown=0, timeouts=0, entry `0x4012aa`, scope=model | PASS |

Machine-readable results: `M4-V4-FIVE-CRITERIA.json`.

## 4. M4 marker

`M4-V4-MARKER.json` is an M4-owned V4 evidence object derived from the producer
schema, with:

```text
replay.runs = 2
replay.identical = true
replay.evidence_sha256 = cb2137a20d838e3f48e02f2d38f258487ddc3a588a371970d9ef41b63304cb14
replay.verified_by = "m4"
state = "passed"
scope = "model"
```

It was validated with:

```text
validate_v4_evidence(marker, candidate_sha256=..., original_sha256=...,
                     require_independent=True)
-> passed, verified_by="m4"
```

Marker SHA256: `fc4802d05c277e27e12f5bfd9f0c906115263b43a0403b222131ecdbb6702b06`.
The producer copy `producer-v4-symbolic.json` has SHA256
`710eb252e4eea0f495569737ed22fc7c3135d71820aae3587e7af242056e0923` and is
unchanged.

## 5. 124 and T8.3 check

### T8.3

The T8.3 gate index has V0, V1, V2, V3 and V5 passed, and V4 `not_run` because
the producer did not write a marker. With this M4 marker, **the V4 portion of
T8.3 is verified at model scope**. T8.3 closure remains a separate Lead/M4
acceptance decision; this report does not write `success_within_scope` and does
not turn the producer's `gate-index.json` into an M4 verdict.

### 124

The 124 package `delivery/cwe416-124-v4-rerun-2026-11-06/` still has:

```text
gate-index.json: V2 not_run, V4 not_run
record 129 ingest: V2 passed, V4 not_run
attempt: inconclusive / required_check_not_run / symbolic
```

The M4 marker applies to the same candidate bytes but does **not** mutate the
124 package or its `v4-symbolic.json`. Without an explicit 124 re-ingest using
the marker, **124 remains provisional/inconclusive**; this report does not
promote V2, V4, or 124 to `success_within_scope`.

Machine-readable dependency status:
`M4-V4-T8.3-124-STATUS.json`.

## 6. Boundaries

- Record 118 remains **VERIFIED** for the T30 rebuild evidence package,
  independent of T8.3; no 118 file was changed.
- Record 91 is **unchanged**; no M5 record was edited.
- Review items 9/10/11/12 are **separate work**.
- Same operator: M4 = Lead; role-separated, not human-independent.
- No merge, no tag, no live-success claim.
- V4 is **model scope**; the candidate's `unsat` remains the disclosed
  empty-disjunction case, not a solved constraint.
