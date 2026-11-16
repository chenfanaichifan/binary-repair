# tools/product - product delivery tools

Product-layer tools for the BinaryRepair delivery. They wrap the existing
deterministic engine and independent verifier; they do not change repair
algorithms and do not touch the gate.

| Tool | Usage | What it does |
|---|---|---|
| `run-demo.sh` | `tools/product/run-demo.sh --list` | list the three demo fixtures |
| `run-demo.sh` | `tools/product/run-demo.sh <fixture-or-all> [outdir]` | run scan -> repair -> independent verify -> export; writes `REPORT.md`, `report.html`, `EVIDENCE-INDEX.json`, `SHA256SUMS` and per-fixture evidence |
| `fixtures/unsupported-bigendian-elf64.bin` | n/a | synthetic 64-byte big-endian ELF64 header used as a fail-closed negative control (not a real program or vulnerability; see `fixtures/README.md`) |

Fixtures:

| id | expectation | meaning |
|---|---|---|
| `strcpy-stack-x86_64` | `verified` | committed benchmark sample `stack-strcpy-x86_64` (CWE-121 stack strcpy) |
| `marcx-capacity` | `verified` | committed benchmark sample `heap-capacity-x86_64` (capacity-check confusion) |
| `unsupported-bigendian` | `refused` | synthetic matrix-outside input; must be refused with no bytes |

Guarantees (enforced by the scripts, not by convention):

- deterministic path only: no AI provider, no API key, no outbound network;
- a fixture is reported `VERIFIED_WITHIN_SCOPE` only when the independent
  verifier returned `verified`, the disposition is `verified_patch` and a
  candidate digest exists; otherwise the report stays `NOT_VERIFIED` /
  `REFUSED` / `REJECTED` with an explicit reason;
- refused inputs produce no candidate bytes;
- the report always carries the boundary statement (public benchmark 2/24
  verified / 8.3%, hidden 0/8) and the `not_run` list.

Outputs (default `artifacts/m3-product-2026-11-17/demo`):

```text
demo-run.json                 run metadata + per-fixture product records
REPORT.md / report.html       customer-readable report
EVIDENCE-INDEX.json           hashed index of every evidence file
SHA256SUMS                    full checksum list (excluding itself)
evidence/<fixture>/scan.json  product scan view
evidence/<fixture>/engine-evidence/
                              results.json, README.md, SHA256SUMS and
                              samples/<sample_id>/{original.bin,candidate.bin,
                              outcome.json,metadata.json,plan.json,
                              verifier-report.json}
```

Boundary: see `docs/product/PRODUCT-POSITIONING-2026-11-17.md` and
`docs/product/DEMO.md`. The repo-wide canonical limitation text remains
`docs/acceptance/LIMITATIONS.md` and `docs/status/claims.json`; if they
conflict with a product doc, the canonical files win.

## Delivery package builder (M3 follow-up)

    .venv/bin/python scripts/product/build_delivery_package.py <outdir> [--out PATH] [--json]

Builds a portable delivery zip from a demo output directory: reports, textual/JSON
evidence, limitation documents (LIMITATIONS / NOT-RUN / NOT-CLAIMED), README,
COMMANDS, manifest.json (per-file SHA256) and SHA256SUMS. Binary suffixes are
excluded on purpose (regenerable with run-demo.sh); the builder re-reads the zip,
verifies every digest and exits 1 on any mismatch.
