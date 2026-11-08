# P1 Route A — executor run with V3 enabled (2026-11-07, run 4)

**Result: `rc=0`. V0/V1/V2/V3/V5 `passed`; V4 `not_run`.** Route A now only lacks
V4, which belongs to M4. P1 overall is still not `success`.

## Package (unchanged, as instructed)

```
p1-routea-package-2026-11-07.zip
sha256 661727cd1320de1ce6ffadafeca873d4595d31ea397c7595262e809855983988
```

No package byte was modified; `sha256sum -c SHA256SUMS` stays 13/13 OK.

## Upstream defect found in the new executor code (one line)

The delivery branch (`head 0ab94cd0381c4357820532a2f346c0d01d237bde`) added
`workers/route_a/run_candidate.py` and wired it into `run_job.py`, but the output
path does not match what the collector reads:

```
run_job.py line 674 : --out <out>/manifest-repaired.json
result_bundle.py    : reads <work>/evidence/v3/manifest-repaired.json
```

Consequence with the code exactly as shipped: `run_candidate` succeeds (step-2
rc=0, `repaired_pass: true, passed 1/1`) yet `result_bundle` still emits
`V3: not_run`, `missing: ["check not run"]`, because the file is in the wrong
directory.

Verified by isolated experiment before changing anything: copying the same
`manifest-repaired.json` into `evidence/v3/` in a scratch copy of the bundle made
the collector return `V3: pass` with
`{"repaired_pass": true, "passed": 1, "total": 1, "input_mode": "none",
  "note": "no-input single-case execution"}`.

### Local fix applied (clearly not upstream)

```
/opt/binrepair/executor-repo/workers/executor/run_job.py
  before: bca838fab2a1b187d30208fba5f51a5f43f93ad91fe533e9ecada84e3c8b28ec
  after : a68a0f1ca61dc8ff05f8d2fba93803492a2374813f919200b94a5bbef7f9887c
  change: "--out", str(out / "manifest-repaired.json")
       -> "--out", str(out / "evidence" / "v3" / "manifest-repaired.json")
```

The patched file is shipped here as `run_job.py.local-patched` so the difference is
auditable. **Upstream must apply this (or move the collector) and bump the head**;
this bundle is evidence that the wiring works, not a claim that the shipped code
is already correct.

## Gates

```json
{"V0":"passed","V1":"passed","V2":"passed","V3":"passed","V4":"not_run","V5":"passed"}
bundle_sha256 = a23b7057945fe07b44818cc1d821219fa5f180fa390ac4f5c4eb919109659884
verified_files = 13
```

| gate | evidence |
|---|---|
| V0 | contract.json, original.elf, route_a/candidate.elf, route_a/status.json, tests/valid.json |
| V1 | evidence/v1/lief.json, route_a/audit.json, route_a/edit-manifest.json, route_a/readelf-audit.txt |
| V2 | evidence/v2/interface.json |
| V3 | evidence/v3/manifest-repaired.json (`sha256 bf336410…554f`, 647 B) |
| V4 | — |
| V5 | evidence/v5/replay.json |

`evidence/v3/manifest-repaired.json`: `repaired_pass true`, `passed 1/1`,
`stdout_bytes 100`, `stdout_sha256 028411ec…f043`, `exit_code 0`,
`stderr 0 bytes`.

## Isolation (measured, attested)

```
uid=1003 euid=1003 gid=1003 groups=[]
CapEff 0000000000000000 · NoNewPrivs 1 · Seccomp 2
netns net:[4026532221] · jobwrap /usr/local/sbin/jobwrap-executor
attestation /run/binrepair/executor/attest-6714.json (root-owned 0444)
```

The candidate execution happened **inside** the executor sandbox (step-2), not via
the earlier ad-hoc `unshare`/`setpriv` path, so this V3 observation carries
`Seccomp: 2`.

## Remaining gap

- **V4 Route A symbolic — M4.** Must not reuse the Route B marker.
- Until V4 exists, P1 overall stays `inconclusive`.

## Files

```
out/                        full executor bundle
jobwrap-attestation.json    root-owned attestation copy
run_job.py.local-patched    the exact executor file used (with the one-line fix)
NOTES.md                    this file
HOST-SHA256SUMS             hashes of everything above
```
