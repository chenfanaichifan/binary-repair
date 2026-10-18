# 05 — Shared public sample and vulnerable function

Work items 5–6. Status: ☐ not started — **sample not selected yet**

## Purpose

Pick the one public sample the whole team will use for both routes, then explain
the vulnerability at the binary level.

## Sample selection record

Fill this in once the team freezes the sample. Until then this page is a
placeholder: no sample, no hash, no analysis results.

| Field | Value |
|---|---|
| Sample name / case ID | TBD |
| Source (Juliet C/C++ 1.3 CWE-121, or other public source) | TBD |
| Build command | TBD |
| Compiler / flags | TBD |
| Compiler and libc version at build time | TBD |
| Build date and builder (who froze it) | TBD |
| SHA-256 of the ELF | TBD |
| Evidence the defect is reachable | TBD |
| Team decision reference (who froze it) | TBD |

Selection gate from the technical design — a candidate sample is usable only if
all of these hold:

- [ ] It has a meaningful valid-input domain (rejecting every input is not a fix).
- [ ] The violation is observable at the binary level (crash / overwrite).
- [ ] Route A patch feasibility is plausible (safe placement of an edit exists).
- [ ] Route B unchanged round trip is plausible.
- [ ] A verifier can detect the original violation.

If a candidate fails a gate, record why and try another public case. Do not swap
in two different samples.

## Vulnerability analysis (to fill in)

- **Vulnerable function:** TBD
- **What the code does:** TBD
- **Copied data / destination buffer size:** TBD
- **Missing or insufficient check:** TBD
- **Overwrite distance to the saved return address:** TBD
- **Deterministic crash input (length):** TBD
- **Observable effect (SIGSEGV, exit code, output):** TBD

### Contract sketch (to be reviewed by another team member)

| Element | Value |
|---|---|
| Valid-input domain | TBD (e.g. lengths 0–N, character constraints) |
| Expected behaviour on valid input | TBD (output and return value must be preserved) |
| Forbidden behaviour | out-of-bounds write for overlong input |
| Required response to invalid input | TBD (defined error path, no out-of-bounds access) |

## Honesty rules

- Mark anything you did not run as "not run".
- If a rehearsal sample is used before the shared sample exists, label every
  figure with "rehearsal" and keep it in a separate section.
