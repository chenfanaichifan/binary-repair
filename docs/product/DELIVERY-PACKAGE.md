# Delivery package

Status: prototype (M3, 2026-11-17). This document defines what a customer
receives for one engagement. Package assembly is automated by
`BT`scripts/product/build_delivery_package.py`BT`; **no package has been shipped to
a real customer yet** (customer acceptance remains not_run).

## 1. Package layout

`BT``BT``BT`text
binaryrepair-demo-<YYYYMMDD>.zip
  README.md                     package description, boundary, regeneration
  COMMANDS.md                   exact commands and host used
  manifest.json                 package-level index (path, bytes, sha256)
  SHA256SUMS                    checksums for every file except itself
  REPORT.md / report.html       English report
  REPORT.zh.md / report.zh.html Chinese report (when generated)
  EVIDENCE-INDEX.json           hash of every evidence file in the source run
  demo-run.json                 run metadata + per-fixture product records
  evidence/<fixture>/scan.json
  evidence/<fixture>/engine-evidence/
      results.json, README.md, SHA256SUMS
      samples/<sample_id>/{outcome,metadata,plan,verifier-report}.json
  05-limitations/
      LIMITATIONS.md            canonical limitations (verbatim copy)
      NOT-RUN.md                explicit not_run list with reasons
      NOT-CLAIMED.md            canonical not-claimed list (verbatim copy)
`BT``BT``BT`

The package intentionally does **not** contain original or candidate binary bytes
(they are regenerable with `BT`tools/product/run-demo.sh all <outdir>`BT` and would
bloat the delivery). No API key, customer binary or credential is included.

## 2. Inclusion rules (fail closed)

| Rule | Enforcement |
|---|---|
| Only text/JSON evidence is packaged; binary suffixes are excluded | `BT`BINARY_SUFFIXES`BT` filter in the builder + post-build verification |
| A verified claim requires the independent verifier decision | report fail-closed self-check; the builder packages the generated report as-is |
| `BT`analysis_only`BT` / `BT`unsupported`BT` / `BT`invalid`BT` / `BT`rejected`BT` results ship as analysis evidence, never as patches | generated from the run records |
| `BT`LIMITATIONS.md`BT` and `BT`NOT-CLAIMED.md`BT` are canonical text | copied from `BT`docs/acceptance/LIMITATIONS.md`BT` and the run boundary record |
| `BT`NOT-RUN.md`BT` lists every not_run row with a reason | generated from the run records |
| No API keys, internal repository paths, or unrelated customer data | pre-send checklist + secret scan |

## 3. Building the package (automated)

`BT``BT``BT`bash
.venv/bin/python scripts/product/build_delivery_package.py <outdir> [--out PATH] [--json]
`BT``BT``BT`

The builder:

1. reads `BT`demo-run.json`BT` from the demo output directory;
2. collects every text/JSON evidence file (skips binary suffixes, the package
   directory and files above 2 MiB);
3. adds `BT`README.md`BT`, `BT`COMMANDS.md`BT` and the three limitation documents;
4. writes `BT`manifest.json`BT` (path, bytes, SHA256 per file) and `BT`SHA256SUMS`BT`;
5. writes the zip to `BT`<outdir>/delivery-package/binaryrepair-demo-<date>.zip`BT`;
6. re-reads the zip and verifies every file digest, the SHA256SUMS presence and
   that no binary suffix leaked in; the CLI exits 1 on any verification failure
   and prints the package digest.

Example output:

`BT``BT``BT`text
package: artifacts/m3-product-2026-11-17/demo/delivery-package/binaryrepair-demo-20261116.zip
sha256:  cd419d7d34d7b23e1683918393a95e906fa913d3b9dcb77ae722565828d8534d
bytes:   100283
files:   31 (excluded binaries: 0)
`BT``BT``BT`

(The example run had already been trimmed; on a full run the excluded-binary
count and byte total are reported in the same summary.)

## 4. Usage notes for the customer

- Verification is scoped to one target function plus the supplied PoC/regression
  cases; it is not proof for the whole binary.
- The candidate patch is delivered as evidence metadata (plan + digests) in this
  package; the binary bytes are regenerated with the documented command.
- The customer owns integration testing and the release decision; no
  production-safety claim is made; see `BT`05-limitations/`BT`.

## 5. Pre-send checklist

- [ ] Generated report fail-closed self-check is "passed";
- [ ] `BT`shasum -a 256 -c SHA256SUMS`BT` passes inside the package;
- [ ] `BT`manifest.json`BT` lists every packaged file and no binary suffix appears;
- [ ] All not_run rows from the run are present in `BT`NOT-RUN.md`BT`;
- [ ] Canonical LIMITATIONS / not-claimed text is the current committed version;
- [ ] No secrets, keys, or unrelated customer binaries are present;
- [ ] Customer authorization for binary modification is on file (see
      `BT`DEPLOYMENT-AND-PACKAGING.md`BT`);
- [ ] Delivery channel and retention window agreed with the customer.

## 6. Known gaps (prototype honesty)

- No customer acceptance has been obtained; all packaging is prototype;
- Evidence retention/deletion automation is not implemented;
- The package does not include a production deployment recipe for the candidate
  binary on purpose: integration and rollout remain the customer's decision;
- The builder packages an existing run; it does not re-run repairs (use
  `BT`tools/product/run-demo.sh`BT` for that).

The generated zip is not committed to the repository: build it on demand. The
committed demo artifact is evidence-only (about 0.45 MB) and excludes both the
binary bytes and the generated zip.
