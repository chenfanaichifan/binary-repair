# 74 — M4 review of Gate 4 head `a69638ae`: A–E pass, F1/F2 not verified; no M4/Lead signature

**From:** M4 (independent verifier; same person/operator as Lead — role-separated, not human-independent)
**To:** Lead, M5, M3, M1
**Date:** 2026-10-31 22:05 (Asia/Hong_Kong)
**Head reviewed:** `main` `a69638ae951ba57499c8a5d0687b1be5ed507dac`
**Gate 4 record:** `docs/route-b/23-gate4-record.md`, SHA-256
`E9D91CA16248378F187BD7F58F94BB3551AB2407BEA212FBA75B80C4A357FB2B`
**Verdict:** **M4 verifier row cannot be signed PASS. Gate 4 remains DRAFT / NOT RUN.**
Lead approval withheld. No `gate4_pass`, no merge/tag, no fixture freeze.

## 1. What independently passes

| Check | Result |
|---|---|
| P4 checker (main a696) | PASS 26/26 |
| P4 own SHA256SUMS recompute | 26/26, 0 mismatch/unlisted |
| P4 `gate4-status` / native manifest | `gate4=pass`; `same_count=6`, `total=6`, `gate4_pass=true` |
| P4 identity/isolation | original `aa428157…8393`; patched `decdcdb8…954b`; uid 1003, CapEff=0, NoNewPrivs=1, egress blocked; snapshot/chain/revert present |
| P3A sums (LF) | 26/26; blob SHA `fa3e16b0a37605133fb03f3d05c2e0c998f0fcbe3a5e72f3b298fe7898bfd48f`; checker PASS; CR=0, BOM absent |
| P3B sums (LF) | 22/22; blob SHA `fa098a38137fd5142fff2b3feb0b203c7e12263b0d8faaf3b665d9cf26b85a13`; checker PASS; CR=0, BOM absent |
| P3A/P3B dist zip hashes | match record: P3A `6F16A933…F24E`; P3B `CA8E1E50…97B6` |
| P2 fresh job log | job `5c04833b…`, `synthetic=false`, `phase=finished`, both routes 6 obligations; verdict `inconclusive/solver_unknown/symbolic` |

## 2. Why I cannot sign the M4 row

### F2 — independent p2 re-run is missing

Checklist `docs/handoffs/42` §3-F requires M4 to re-run
`python tools/p2_acceptance.py --job-id <id> --base-url <controller>` and get exit 0.
No controller is reachable here (`127.0.0.1:8000` and `:8801` refuse connection), and no
controller/data directory for job `5c04833b…` is present in this checkout. Therefore F2 is
**NOT VERIFIED**; I cannot substitute M5's recorded exit-0 claim for my own re-run.

### F1 — raw p2 log does not contain the required PASS line

`docs/handoffs/logs/P2-v6-acceptance.txt` contains only the JSON summary. It has **no
`P2 ACCEPTANCE PASSED phase=finished job=<id>` line**, no command invocation, and no captured
exit code. The Gate4 record says "p2_acceptance.py exit 0", but that is a record claim, not raw
output. The current tool's verification-only mode (`--job-id`) returns 0 after the JSON summary
and does not print the pipeline's PASS line; the log therefore does not satisfy F1 as written.
F1 is **NOT VERIFIED**.

### E — record/signature state

- The record is still **DRAFT / NOT RUN**; M5 row is filled, **M4 and Lead rows are blank**.
- The required same-person identity/independence annotation for the M4/Lead rows is not yet in
  the signature table. I will not sign a PASS row without it.
- Gate 4 record contains an external V4 model-level ruling; that is not a Gate 4 formal pass and
  does not substitute for F1/F2.

## 3. What unblocks the signature

1. **M5/M1:** start the controller with the job `5c04833b…` data (or provide the base URL/data
   directory) so M4 can run:
   `python tools/p2_acceptance.py --job-id 5c04833b4b104461966650a965364f2b --base-url http://127.0.0.1:<port>`
   and observe exit 0 / the JSON summary.
2. Capture the **full command, stdout, stderr, exit code** in
   `docs/handoffs/logs/P2-v6-acceptance.txt`; for F1, either run the pipeline mode that prints
   `P2 ACCEPTANCE PASSED ...` or have the Lead explicitly revise F1's evidence format to accept
   the verification-only JSON+exit code (not silently).
3. Add the same-person limitation annotation to the M4 and Lead rows; M5 re-confirms its row is
   unchanged.
4. M4 then fills only its verifier row (PASS/FAIL/NOT VERIFIED) and pins the new record hash;
   the Lead may approve only after that.
5. No `gate4_pass`, merge, tag, or fixture freeze before those steps.

## 4. Status

| Item | Status |
|---|---|
| Gate 4 formal | **DRAFT / NOT RUN** |
| M4 verifier row | **blank** (cannot sign PASS; F1/F2 NOT VERIFIED) |
| Lead approval | **blank** |
| V4 | model-level PASS (external ruling); not a Gate 4 formal criterion |
| Gate 5 | BLOCKED |
| Fixture | **NOT FROZEN** |

**Signature:** none. This is a review record, not an M4 gate signature.

## 5. Exact next command for M4 (once controller exists)

```powershell
python tools/p2_acceptance.py --job-id 5c04833b4b104461966650a965364f2b --base-url http://127.0.0.1:8000
# capture stdout/stderr and $LASTEXITCODE verbatim; any non-zero is NOT VERIFIED/FAIL
```

If the controller serves a different port, use that URL; the job ID and evidence must be the
same real job, not synthetic.
