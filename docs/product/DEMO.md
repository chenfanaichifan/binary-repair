# BinaryRepair 10-minute product demo

Audience: prospective customer, partner, or reviewer.
Goal: show a bounded repair with auditable evidence, and show that the product
refuses what it cannot do. **No API key and no external network are used.**

## 0. What the demo proves (and what it does not)

Proves:

- one command runs scan -> repair -> independent verify -> evidence export;
- two committed fixtures reach the deterministic verified disposition and the
  independent verifier confirms them;
- one out-of-matrix input is refused with no candidate bytes (fail closed);
- every claim in the report is backed by a SHA256 evidence index.

Does not prove:

- arbitrary-binary repair, unknown-vulnerability discovery, or whole-program
  proofs;
- a repair success rate: the public benchmark is **2/24 verified (8.3%)** and
  hidden is **0/8 verified**;
- production safety of a repaired binary.

## 1. Prerequisites (1 minute)

- repository checkout with a Python virtual environment at `BT`.venv`BT`
  (created by `BT`./start-gui.sh`BT`, Python 3.11);
- no network access is needed for the demo itself;
- optional: a running Lima VM used as the guest runtime oracle for ELF x86-64.
  Without it, the same command still runs but the two positive fixtures report
  `BT`NOT_VERIFIED`BT` with an explicit not_run reason (environment-degraded,
  fail closed). The demo never fakes verification.

Check the entry point:

`BT``BT``BT`bash
tools/product/run-demo.sh --list
`BT``BT``BT`

Expected: three fixture ids with their expectations.

## 2. Fixtures

| id | expectation | what it is |
|---|---|---|
| `BT`strcpy-stack-x86_64`BT` | verified | CWE-121 stack strcpy overflow (ELF x86-64); committed benchmark sample `BT`stack-strcpy-x86_64`BT` |
| `BT`marcx-capacity`BT` | verified | capacity-check confusion (ELF x86-64); committed benchmark sample `BT`heap-capacity-x86_64`BT` |
| `BT`unsupported-bigendian`BT` | refused | synthetic 64-byte big-endian ELF64 header; not a real program, only a fail-closed negative control |

## 3. Run the negative control first (1 minute)

`BT``BT``BT`bash
tools/product/run-demo.sh unsupported-bigendian /tmp/binaryrepair-demo-neg
`BT``BT``BT`

Expected output (abridged):

`BT``BT``BT`text
[1/1] unsupported-bigendian: REFUSED (disposition=unsupported, verifier=not_run, oracle=not_run, tier=None)
      reason: big-endian elf/x86_64 is outside the repair matrix
      not_run: ... no candidate produced (disposition=unsupported); nothing is downloadable
`BT``BT``BT`

Talking point: the product refuses matrix-outside input, emits an explicit
reason, and produces **no** candidate bytes. That is the fail-closed guarantee.

## 4. Run the full demo (3 minutes)

`BT``BT``BT`bash
tools/product/run-demo.sh all artifacts/m3-product-2026-11-17/demo
`BT``BT``BT`

Expected output (on the reference host with the guest oracle available):

`BT``BT``BT`text
== BinaryRepair product demo (deterministic, no key, no network) ==
[1/3] strcpy-stack-x86_64: VERIFIED_WITHIN_SCOPE (disposition=verified_patch, verifier=verified, oracle=pass, tier=emulated_run)
[2/3] marcx-capacity: VERIFIED_WITHIN_SCOPE (disposition=verified_patch, verifier=verified, oracle=pass, tier=emulated_run)
[3/3] unsupported-bigendian: REFUSED (disposition=unsupported, verifier=not_run, oracle=not_run, tier=None)
report (en): .../REPORT.md
report (zh): .../REPORT.zh.md
boundary: public benchmark 2/24 verified (8.3%) | hidden 0/8 | one target function/sink per candidate
`BT``BT``BT`

Measured elapsed time on the reference host: about 45 seconds
(`BT`demo-run.json`BT` field `BT`elapsed_seconds`BT`).

If the guest oracle is unavailable, the two positives print `BT`NOT_VERIFIED`BT`
with `BT`not_run: runtime oracle status=...; no runtime evidence`BT`. Say so
explicitly: the environment could not produce runtime evidence, so the product
does not claim verification.

## 5. Walk through the report (2 minutes)

Open `BT`artifacts/m3-product-2026-11-17/demo/REPORT.md`BT`:

1. Section 0 states the boundary numbers (2/24 public, 0/8 hidden) and the
   not-claimed list;
2. Section 1 is the execution summary (fixture, verdict, disposition,
   independent verification, oracle, runtime tier);
3. Section 2 per fixture shows the input SHA256, scan view, repair fields
   (disposition, candidate SHA256, patch plan SHA256, gate, oracle, tier), the
   independent verifier checklist, limitations and not_run;
4. Section 3 is the fail-closed self-check (must read "passed");
5. Section 4 is the SHA256 evidence index; section 5 repeats the not-claimed
   wording.

Verify the evidence:

`BT``BT``BT`bash
cd artifacts/m3-product-2026-11-17/demo
shasum -a 256 -c SHA256SUMS
`BT``BT``BT`

Evidence layout per fixture:

`BT``BT``BT`text
evidence/<fixture>/scan.json
evidence/<fixture>/engine-evidence/results.json
evidence/<fixture>/engine-evidence/samples/<sample_id>/original.bin
evidence/<fixture>/engine-evidence/samples/<sample_id>/candidate.bin     (verified only)
evidence/<fixture>/engine-evidence/samples/<sample_id>/plan.json
evidence/<fixture>/engine-evidence/samples/<sample_id>/verifier-report.json
evidence/<fixture>/engine-evidence/samples/<sample_id>/metadata.json
evidence/<fixture>/engine-evidence/samples/<sample_id>/outcome.json
`BT``BT``BT`

## 6. Boundary conversation (2 minutes)

Say:

- "This is bounded repair plus auditable evidence: one target function/sink, a
  supplied PoC/regression, and an independent verifier."
- "Public benchmark: 2/24 verified, 8.3%. Hidden: 0/8. These are the numbers; we
  do not claim generalisation."
- "When we cannot verify, we refuse or report not verified; no bytes are offered
  and no success is claimed."
- "AI is a candidate generator only; acceptance belongs to the deterministic gate
  and the independent verifier. This demo does not call any model."

Do not say:

- "arbitrary binaries", "100%", "universal repair", "guaranteed safe";
- "the binary is production-ready after the patch";
- any hidden-set or multi-model capability number that is not in the report.

## 7. Troubleshooting

| Symptom | Meaning | Action |
|---|---|---|
| `BT`ERROR: python venv not found`BT` | `BT`.venv`BT` missing | run `BT`./start-gui.sh`BT` once (installs dependencies); the demo needs no network |
| positives print `BT`NOT_VERIFIED`BT` with `BT`not_run: runtime oracle status=...`BT` | guest runtime oracle unavailable on this host | expected fail-closed behaviour; do not claim verification |
| `BT`unknown fixture(s)`BT` and exit code 2 | typo in the fixture id | run `BT`--list`BT` |
| report shows `BT`FAIL-CLOSED CHECK FAILED`BT` | an internal inconsistency was detected | stop the demo and report it; do not present the run |
| `BT`FAILED`BT` printed for a fixture | its expected outcome was not reached | use the printed reason; do not retry silently |

## 8. Demo acceptance criteria

The demo is successful when:

1. `BT`run-demo.sh --list`BT` lists exactly three fixtures with the expected labels;
2. the negative control returns `BT`REFUSED`BT` with an explicit reason and produces
   no candidate bytes;
3. the two positive fixtures are either `BT`VERIFIED_WITHIN_SCOPE`BT` with
   `BT`independent_decision=verified`BT`, or `BT`NOT_VERIFIED`BT` with an explicit
   runtime not_run reason (environment-degraded);
4. the report fail-closed section reads "passed";
5. `BT`shasum -a 256 -c SHA256SUMS`BT` succeeds;
6. the presenter states the 2/24 and 0/8 numbers and the not-claimed list.

## 9. Timing plan

| minute | step |
|---|---|
| 0-1 | boundary framing: bounded repair + evidence, not universal repair |
| 1-2 | prerequisites and fixture list |
| 2-3 | negative control: fail closed |
| 3-6 | full demo run (about 45 s; use the time to explain scan/repair/verify stages) |
| 6-8 | report walkthrough and checksum verification |
| 8-10 | boundary conversation and next steps |

## 10. Related documents

- `BT`docs/product/PRODUCT-POSITIONING-2026-11-17.md`BT` - positioning, ICP, SLOs;
- `BT`docs/product/CUSTOMER-REPORT-TEMPLATE.md`BT` - customer report structure;
- `BT`docs/product/DELIVERY-PACKAGE.md`BT` - what is handed to a customer;
- `BT`docs/product/TRIAL-GUIDE.md`BT` - five guided trial tasks;
- canonical limits: `BT`docs/acceptance/LIMITATIONS.md`BT` and
  `BT`docs/status/claims.json`BT`;
- Chinese versions: `BT`delivery/zh/product/`BT`.

## 11. CI, committed artifact and binary regeneration notes

- The committed demo artifact under artifacts/m3-product-2026-11-17/ is
  evidence-only: original/candidate binary bytes are not shipped (a full run is
  about 11 MB). Regenerate them with: tools/product/run-demo.sh all <outdir>
- Regenerating the run overwrites the reports and checksums; EVIDENCE-INDEX.json
  and SHA256SUMS always describe the files actually present in the output
  directory. The candidate digests are still recorded in demo-run.json and in
  each verifier-report.json.
- CI runs the structural/fail-closed tests only (tests/test_product_demo.py).
  The CI host has no guest runtime oracle, so a "verified" result is not expected
  in CI; never gate CI on a verified outcome.
- Delivery package: scripts/product/build_delivery_package.py builds a portable
  zip (reports + textual evidence + limitation documents + README + manifest +
  SHA256SUMS, no binary bytes) and verifies every digest after writing.
