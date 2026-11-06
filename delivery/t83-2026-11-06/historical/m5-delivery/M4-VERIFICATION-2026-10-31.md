# M4 verification — main 56a7447 — 2026-10-31

**Exact target:** `56a744736fb52759affe4a0e239fdb56814324f9`
**PR #10 head:** `aab162a4b74a526f9f37bba3a99ccc061160870c` (ancestor of main; PR is closed)
**Scope:** verification only. No gate pass, no merge, no tag.

## 1. Integration / test result — PASS (verifiable subset)

Commands run on `56a7447`:

```bash
pytest -q tests/integration/test_p2_acceptance.py
pytest -q tests/integration/test_attempt_writer.py
pytest -q -rA
pytest -q tests/unit/test_acceptance.py
```

Observed:

```text
p2 acceptance:                  5 passed
attempt writer:                 6 passed
acceptance unit:               29 passed
full suite:                    272 collected, 263 passed, 9 skipped, 0 failed, 0 errors
```

The 9 skips are environment-gated: 7 Microsoft Edge e2e (Edge absent on this
host) + 2 ELF-execution tests (non-Linux host). This differs from M1's Windows
host count (242 passed / 2 skipped / 5 uncollectable); both must be reported as
host-specific. No skip/xfail was added in the `aab162a..56a7447` test diff.

Test-file integrity on main:

```text
test_routeb_identity_passes_only_with_matching_original  present
test_routeb_identity_fails_on_original_mismatch          present
static V0 == "not_run"                                    present
p2 negative tests                                        5 present
```

**Integration verdict: PASS for the verifiable subset.** This does not certify
the uncollectable/environment errors on another host.

## 2. Evidence package verification

| Package | checker | files/sums | Python-normalized hashes | Standard `shasum -a 256 -c` |
|---|---|---|---|---|
| P2-real | PASS | 31/32 | 0 mismatches | **FAIL (CRLF)** |
| P3A v6 | PASS | 26/26 | 0 mismatches | **FAIL (CRLF)** |
| P3B v5 | PASS | 22/22 | 0 mismatches | **FAIL (CRLF)** |
| P4 v3 | PASS | 26/26 | 0 mismatches | **FAIL (CRLF)** |

The checker and a CRLF-tolerant Python reader agree on every byte. A portable
`shasum -c` fails because the shipped `SHA256SUMS` files contain CRLF; this breaks
the "independent teammate replay" requirement unless the verifier normalizes
line endings. **Fix M3:** regenerate `SHA256SUMS` with LF, or document the
normalizer in the replay instructions; do not call the package portable until
then.

## 3. P2-real — exit 0 is not success

| Job | Route | Outcome | Detail |
|---|---|---|---|
| job1 | A | `inconclusive` | V2 `not_run` |
| job1 | B | `inconclusive` | V2 `not_run` |
| job2 | A | `inconclusive` | V4 `not_run` |
| job2 | B | `rejected` | V2 `failed` (`extra_load_segments_within_contract`) |

`p2_acceptance.py` exits 0 because the snapshot is complete and internally
consistent. **It is not a repair success and not a Gate 4 pass.**

## 4. Gate 4 — FAIL / NOT READY

- `docs/route-b/23-gate4-record.md` is still **DRAFT / NOT RUN**, M4 and Lead
  rows blank.
- P4 v3 has execution evidence (`gate4-status.json=pass`, native
  `manifest-compare.json` 6/6), but **Gate 4 acceptance was not run**; P4's own
  `REMAINING-GAPS.md` says so.
- P3B v5 has V2 **failed** (2 extra PT_LOADs vs contract allowance of 1), and
  V4 `not_run`; therefore neither route has all required obligations.
- P3A v6 has V2/V5 evidence but V4 `not_run`.
- `hashes.json`/`harness-manifest`/`isolation.json` in P4 now bind
  `b232d60b…`, `a912e6b0…`, runner `515c4d60…`, kit `499f510c…`; this is good
  evidence, but it does not create `gate4_pass`.
- Gate 5 remains **BLOCKED**; `jobwrap` has no `gate5` mode and
  `jobwrap_gate5.sh` does not hash-check `GATE5_SCRIPT` (`docs/handoffs/41`).

**M4 Gate 4 verdict: FAIL / NOT READY.** No `gate4_pass`, no M4 signature.

## 5. MVP verdict

The PRD requires both routes to succeed, all required V0–V5 checks, replay, and
F1–F5. Current state:

```text
Route A: V0/V1/V2/V3/V5 pass; V4 not_run
Route B: V0/V1/V3/V5 pass; V2 failed; V4 not_run
Gate 4: DRAFT / NOT RUN
Gate 5: BLOCKED
Replay: V5 Route B is record re-verification, not a third executor run
```

**MVP is NOT COMPLETE.** The honest label is partial/inconclusive, not
success_within_scope.

## 6. Required actions before any acceptance

1. **Route B V2:** rebuild so the candidate adds at most one allowed R-X PT_LOAD
   (or obtain an explicit contract re-decision); rerun V2 and V3.
2. **V4:** produce real bounded-symbolic evidence for both final candidates, or
   record `not_run` and keep the overall result inconclusive. No solver output
   exists in this checkout.
3. **P4 acceptance:** run the real p2 job with the final packages; write only
   observed values; do not fill gate4_pass.
4. **Gate 5:** add a fixed `gate5` jobwrap mode and hash-check
   `GATE5_SCRIPT_SHA256`; otherwise keep blocked.
5. **Replay:** make `SHA256SUMS` LF-portable or provide a verifier that
   explicitly normalizes CRLF; an independent teammate must reproduce both
   routes.
6. **Freeze:** fixture stays NOT FROZEN until the above and Lead approval.

## 7. Release decision

```text
M4 integration row: PASS (verifiable subset on 56a7447)
M4 Gate 4 row:      FAIL / NOT READY
M4 MVP row:         NOT COMPLETE
merge/tag:          NOT ALLOWED
```

No merge, no `mvp-integration-2026-10-31` acceptance tag, no success claim.
