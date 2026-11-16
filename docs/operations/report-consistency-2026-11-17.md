# Report and claims consistency review (2026-11-17)

Status: P1-1. Owner: M4. **Report only - no master report, claims or code was
modified.** Every finding lists file + line and a suggested fix for the Lead to
apply.

Audit baseline: repository `binary-repair-gui`, branch
`final/consolidated-2026-11-16`, HEAD `ae89f88` (Lead's ASCII-docs
relocation), with the M1/M2/M3 working changes present but uncommitted.
After the relocation the Chinese delivery documents live under `delivery/zh/`
(master report, session analyses, project history, consolidation record, handoff
task packages); `docs/**/*.md` is ASCII-English and the markdown language gate
passes (`python scripts/check_markdown_language.py --allowlist
docs/operations/markdown-language-allowlist.json` -> exit 0, 203 files, 0
violations).

## 1. Non-loop capability wording: should read 3/6 (single model)

Correct wording (master report section 1.5.2): Path A 12-case matrix was 0/6
before `a8934fe`; after it hard-multicall / hard-sprintf / hard-nonconst are AI
VERIFIED -> **3/6**, single model deepseek-flash, v4-pro 0/3; CWE-121 public /
UAF-noinput / heap-canary remain 0; multi-model/multi-binary generalisation not
proven.

The requested sections were checked in
`delivery/zh/consolidation/PROJECT-MASTER-REPORT-2026-11-16.md`:

| Section | Line | Text as written | Verdict |
|---|---|---|---|
| 1.4 | 76 | "non-loop family 3/6 (only hard-multicall / hard-sprintf / hard-nonconst, single model deepseek-flash; CWE-121 public / UAF-noinput / heap-canary still 0 ...)" | PASS |
| 1.5.2 | 91-92 | explicit 0/6 -> 3/6 correction with model qualifier | PASS |
| 3.6.1 | 318-325 | "3/3 non-loop AI VERIFIED" for the three hard cases + flash 3/3 vs v4-pro 0/3 | PASS (see clarity note N1) |
| 3.8 | 391 | "hard-multicall / hard-sprintf / hard-nonconst ... 3/6, single model deepseek-flash; v4-pro 0/3; CWE-121 public / UAF-noinput / heap-canary still 0" | PASS |
| 5.3.3 | 750 | "non-loop hard cases 3/3 ... same 12-case matrix non-loop total 3/6, v4-pro 0/3" | PASS |
| 6.1 A1 | 886-891 | "non-loop family: 3/6 (single model, remaining 3 still 0)" with full qualifier | PASS |
| 6.5 row 3 | 1135 | "non-loop 3/6 (single model; the other 3 still 0)" | PASS |
| 7.3 A1 | 1284 | "non-loop 3/6 -> 4/6+" | PASS |
| 7.5 item 7 | 1380 | "non-loop remaining 3 cases (3/6 wording)" | PASS |

Result: the master report is internally consistent on the 3/6 wording. Two
clarity notes (not contradictions):
- N1: section 3.6.1 title/body say "3/3" for the three hard cases without the
  "12-case matrix total 3/6" context that sections 3.8 and 5.3.3 carry. A reader
  who stops there can over-read it as "non-loop solved". Suggest adding
  "(12-case matrix non-loop total 3/6; single model)" to the section 3.6.1
  heading or first bullet.
- N2: section 3.6.2 (line 334) reports "DeepSeek flash 4/6 AI verified" for the
  P7 cross-binary benchmark. That is a different experiment (4 binaries / 6
  cases) and is correctly labelled there; flagging it only because "4/6" also
  appears as the Phase-10 goal for the non-loop matrix. No change required, or
  optionally add "P7 cross-binary benchmark" to the row label.

### Inconsistency R1 (real): LIMITATIONS still states non-loop 0/6
`docs/acceptance/LIMITATIONS.md` section 17 (lines 214-222, duplicated at
lines 499-507) states: "Loop remains 6/12 verified; non-loop remains 0/6."
This has no "as of" date and directly contradicts the corrected 3/6 wording.
Suggested fix (Lead owns this file): either
(a) prefix the section with "As of 2026-11-14 (before a8934fe)" so it is clearly
a historical measurement, or
(b) update it to: "Loop 6/12; non-loop 3/6 after a8934fe (hard-multicall /
hard-sprintf / hard-nonconst, single model deepseek-flash; v4-pro 0/3; CWE-121
public / UAF-noinput / heap-canary still 0)".
Recommendation: (a) for the old dated section, since the same file has a
Phase-8C addendum that already carries the corrected facts.

## 2. Benchmark numbers: 2/24, hidden 0/8, false_verified=0, P16-R3 7/10

| Claim | Where checked | Value found | Verdict |
|---|---|---|---|
| public verified rate | master report 96, 594, 650, 770, 945, 1126 | 2/24 = 0.0833 (30 executed, 2 unsupported, 1 rejected, 1 withdrawn) | PASS |
| public verified rate | `docs/status/claims.json` `phase8c_ground_truth.public_benchmark` | verified 2, eligible 24, verified_repair_rate 0.083333, false_verified 0, repeats 2 identical | PASS |
| public verified rate | `docs/acceptance/LIMITATIONS.md` Phase-8C section (approx. lines 750-805) | 30 executed, 2 verified, 1 rejected, false_verified 0, 2/24 eligible | PASS |
| public verified rate | `docs/release-2026-11-16-phase8c.md` lines 34-70; `docs/release-phase8c-final-evidence-2026-11-16.md` lines 25-36 | 2/24 = 0.0833, false_verified 0 | PASS |
| hidden | master report 96, 98, 945; claims `hidden_benchmark`; LIMITATIONS Phase-8C; product doc | 8 samples, 8 executed, 0 candidates, 0 verified, 0 false_verified, hidden_available=false, material_committed=false | PASS |
| false_verified | claims (public 0, hidden 0); master report 770/945/1126; release notes | 0 everywhere | PASS |
| P16-R3 | claims line 305 ("7/10 ... 1 rejected and 2 artifact_missing"); master report 360 and 750; session-1 analysis | 7/10 (verified: hard-multicall, hard-sprintf, hard-nonconst, cwe122-heap-copy, cwe125-oob-read, cwe190-integer-overflow, cwe476-null-deref) | PASS where stated; see gap G1 |

Result: the headline benchmark numbers are consistent across the master report,
claims.json, LIMITATIONS and the two release notes.
- Gap G1 (documentation completeness, not a contradiction): `LIMITATIONS.md`
  does not mention P16-R3 7/10 at all. Optional: add a line under the
  Phase-8B/8C addenda so the boundary document references the 7/10 result.

## 3. CI evidence wording: gated SHA vs final release SHA

Facts:
- `claims.json` `ci_evidence.gated_sha` = `f1ba37eee5146b5bb5de97046a0f8b4b653538ff`,
  hosted CI run `43744573286` (success), Ubuntu verification `43744573230`
  (success); `latest_verified_ci` (lines 12-17) points at the same run.
- Final release SHA `4a7b2355ffc5225d013a777bc7d588abac58f944` has hosted CI
  `43748886046` and Ubuntu verification `43748886289`; this dual record is
  documented in the master report (655, 694-697, 1041, 1663), the session-2
  analysis and `docs/release-phase8c-final-evidence-2026-11-16.md` (lines 10-13).
- `self_hosted_nightly.status = not_run` in claims; LIMITATIONS Phase-8C and the
  master report say the same ("not_run and not claimed"). PASS on honesty.
- Release gate evidence artifact exists locally:
  `artifacts/release-gate-2026-11-16-phase8c/gate.json` -> ok=true, exit_code=0,
  release_sha=4a7b235..., 13 checks; `frozen_matches_release` true.

Findings:
- R2 (structural, known as B2): `claims.json` has no `final_release_sha` /
  `final_release_ci` field. The dual record only exists in prose/evidence.
  Suggested fix: add `ci_evidence.final_release_sha`, `final_release_ci_run_ids`
  (43748886046 / 43748886289) plus a note that the gated SHA is the code-gate
  SHA; keep the existing fields for compatibility. Then regenerate
  `verify_ci_evidence.py` expectations if the checker pins them.
- R3 (stale pointer): `claims.json` line 15 `latest_verified_ci.branch` =
  `"workbench-v3"`, but that branch was deleted in the 2026-11-16 cleanup
  (`git ls-remote origin refs/heads/workbench-v3` -> 0 lines). Suggested fix:
  keep the run id and head_sha (valid historical evidence) but change
  `branch` to a string that states the current carrier, e.g.
  `"workbench-v3 (deleted 2026-11-16; commit reachable from
  final/consolidated-2026-11-16)"`, or add a `branch_note` field.
- Not claimed: no live GitHub API check was performed (no `gh`, no token);
  CI status above is the recorded evidence, not a fresh query. Current HEAD
  `ae89f88` has no CI run recorded in the repository; see handoff-readiness
  checklist item 15.

## 4. Doc hierarchy / stale front-page documents (B10)

- `README.md` (root): top block correctly points at the consolidation branch and
  the gated SHA `4a7b235`; the "Current feature line (2026-11-15)" block still
  says "3/3 AI-verified non-loop hard cases" without the 12-case total. Low-risk
  wording suggestion: add "(12-case matrix non-loop total 3/6; single model)".
  README is allowlisted historical text and is also referenced from the
  consolidation index; no language issue.
- `DELIVERY.md`: still a v1.2.x / `workbench-v3` snapshot (889-test CI run
  43256887551) with no "historical" banner and no link to the consolidation.
  Suggest adding a one-line banner at the top: "Historical snapshot (v1.2.1,
  2026-11-09). Current delivery: branch final/consolidated-2026-11-16, see
  CONSOLIDATION.md."
- `docs/status/final-status.md`: dated 2026-11-08 / v1.2.0 and allowlisted as
  historical. Suggest adding the same one-line banner.
- These are documentation-hierarchy issues, not number errors; the owning
  documents are outside M4's write scope.

## 5. Language gate history (resolved)

- At HEAD `503b226` the docs tree failed the markdown language gate: 11 new
  non-allowlisted documents (the 5 consolidation docs, 4 handoff task files,
  handoff README, product positioning) contained 65,683 non-ASCII characters,
  which would have failed the CI "Markdown language policy" step.
- Lead commit `ae89f88` moved the Chinese delivery docs to `delivery/zh/` and
  the product doc was removed/relocated by M3; the checker now exits 0
  (203 files, 0 violations) at the audit baseline.
- M4 ops documents are ASCII-English and add no violations.

## 6. Summary

| Check | Verdict |
|---|---|
| master report non-loop 3/6 (9 sections) | PASS (2 clarity notes N1/N2) |
| 2/24 / hidden 0/8 / false_verified=0 | PASS across report, claims, LIMITATIONS, release notes |
| P16-R3 7/10 | PASS where present; LIMITATIONS omits it (G1, optional) |
| CI dual record gated vs final SHA | PASS in docs; claims lacks explicit fields (R2) |
| claims branch pointer | STALE (R3) |
| self-hosted nightly not_run | PASS |
| language gate on current tree | PASS (after Lead relocation) |
| doc hierarchy (README/DELIVERY/final-status) | PARTIAL - suggested banners/wording (R4) |

Open items handed to Lead: R1 (LIMITATIONS 0/6), R2 (claims final-release fields),
R3 (claims stale branch pointer), G1 (P16-R3 in LIMITATIONS, optional), R4
(historical banners), N1/N2 (wording only). No file outside M4's write scope was
modified.
