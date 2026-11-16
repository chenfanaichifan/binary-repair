# Trial guide

Status: prototype trial design (M3, 2026-11-17). The goal is to validate whether
the bounded product is useful and honestly communicated, **not** to demonstrate
a general repair capability.

## 1. Trial rules

1. Only use binaries the trial user is **authorized** to analyze and modify
   (a licence/EULA allowing modification, or an explicit internal authorization);
2. Prefer the committed fixtures and non-production binaries; never upload or
   process production binaries during the trial;
3. Every trial run must be recorded with the exact command, host, elapsed time,
   verdict and not_run reasons;
4. A "successful" trial never means "arbitrary repair works"; it means the
   bounded workflow and its evidence were understood correctly;
5. Do not write customer-facing text that claims arbitrary-binary, 100%, or
   production-safe repair; the canonical numbers are public 2/24 verified (8.3%)
   and hidden 0/8.

## 2. Five trial tasks

### T1. Verify the fail-closed refusal (10 minutes)

Goal: confirm the product refuses matrix-outside input without producing bytes.

`BT``BT``BT`bash
tools/product/run-demo.sh unsupported-bigendian /tmp/trial-neg
`BT``BT``BT`

Success criteria:

- the fixture shows `BT`REFUSED`BT` with `BT`disposition=unsupported`BT`;
- the reason names the matrix boundary;
- no `BT`candidate.bin`BT` exists in the output tree;
- `BT`not_run`BT` rows explain why nothing was produced.

Failure criteria: a candidate file appears, success is claimed, or the reason is
missing.

### T2. Run the verified stack-strcpy fixture (20 minutes)

`BT``BT``BT`bash
tools/product/run-demo.sh strcpy-stack-x86_64 /tmp/trial-stack
`BT``BT``BT`

Success criteria:

- `BT`VERIFIED_WITHIN_SCOPE`BT` with `BT`independent_decision=verified`BT` and
  oracle `BT`pass`BT` (or `BT`NOT_VERIFIED`BT` with a runtime not_run reason on
  hosts without the guest oracle - record which case applies);
- the report fail-closed section reads "passed";
- `BT`shasum -a 256 -c SHA256SUMS`BT` passes;
- the trial user can state what was verified and what was not (one function plus
  the supplied PoC/regression, not the whole binary).

### T3. Run the marcx-capacity fixture (20 minutes)

Same as T2 with `BT`marcx-capacity`BT`. Success adds: the trial user can explain
the capacity-check confusion class and why a wrong-capacity candidate is rejected
by the runtime oracle rather than silently accepted.

### T4. Try a matrix-outside or unsupported input with the CLI (20 minutes)

Goal: see the general CLI fail-closed path (the demo registry is intentionally
limited to three fixtures).

`BT``BT``BT`bash
.venv/bin/python scripts/repair_binary.py <binary> /tmp/trial-out.bin \
    --target <SYMBOL-OR-VA-RANGE> --require-target \
    --poc <POC-MANIFEST.json> --report /tmp/trial-report.json
`BT``BT``BT`

(`BT`--poc`BT` may be omitted when no PoC manifest exists; the result then cannot
be verified and must fail closed.)

Success criteria:

- the tool returns an explicit disposition (`BT`analysis_only`BT`,
  `BT`unsupported`BT`, `BT`invalid`BT` or a verified/not-verified result) and a JSON
  report;
- exit code 2 with no output file is the expected fail-closed outcome for refused
  input;
- the trial user can point at the exact reason in the report.

Failure criteria: an output file is produced for a refused input, or a success is
reported without runtime evidence.

### T5. Audit the evidence package (15 minutes)

Goal: confirm the evidence can be independently checked by the customer.

`BT``BT``BT`bash
cd /tmp/trial-stack
shasum -a 256 -c SHA256SUMS
python3 -m json.tool EVIDENCE-INDEX.json > /dev/null
grep -n "failed|not_run|not claimed|2/24|0/8" REPORT.md
`BT``BT``BT`

Success criteria: checksums pass, the index lists every evidence file, and the
trial user finds the boundary numbers, limitations and not_run rows without
help.

## 3. Feedback template

Record per trial user:

`BT``BT``BT`markdown
Trial user / role:
Date / host:
Tasks completed: T1 T2 T3 T4 T5
Verdicts observed (per task):
Blockers (what stopped you):
Unexpected behaviour (with command + output):
Boundary clarity (1-5, 5 = completely clear):
Evidence usability (1-5, 5 = could audit alone):
Would you use it for a known-CVE no-source binary? (yes / no / depends: why)
What would make the next trial useful:
NPS (0-10) and why:
Pricing reaction (prototype question; no commitment): too high / plausible / too
low / need the value metric explained:
Quotes we may reuse (with permission):
`BT``BT``BT`

## 4. What success looks like for the trial program

- users complete T1-T3 without help and can explain the fail-closed behaviour;
- at least one user can audit T5 evidence alone;
- users do not over-interpret results (no "arbitrary repair works" conclusion);
- concrete blockers (oracle availability, report clarity, matrix gaps) are
  recorded as product backlog items, not hidden.

## 5. Explicit not_run

- No external trial user has been recruited or run yet (not_run);
- No pricing or packaging has been validated (not_run);
- No production binary has been, or should be, processed during trials.
