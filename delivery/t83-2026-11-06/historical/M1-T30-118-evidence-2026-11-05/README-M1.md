# M1 delivery: record 118 evidence, readable by M4/M5

- Date: 2026-11-05
- Owner: M1 (host backend)
- Source: `origin/m3/cwe122-fixture-build` @
  `87f63502d0fc5679f9dd797b7adc20c2069a5d39`
- Status: **evidence delivered**. T30 build/trigger status is unchanged; M1 does
  not ask M4 to upgrade record 118.

## What is here

```
t30-rebuild-2026-11-05/                  the 11 evidence files, byte-identical to M3
  00-window-host.txt
  01-window-and-isolation.txt
  02-build.txt
  03-readelf.txt
  04-trigger.txt
  05-asan.txt
  06-SHA256SUMS
  07-rebuild.json
  collect.sh
  README.md
  SHA256SUMS
M3-t30-rebuild-evidence-2026-11-05.zip   original transport zip (11 members)
M3-t30-rebuild-evidence-2026-11-05.zip.sha256
PROVENANCE.md                            canonical T30 path + c274893 git binding
VERIFICATION.txt                         the checks run on this copy
SHA256SUMS                               hashes for the files at this level
```

The zip's top-level SHA-256 is
`968fb8d9a80f991567c0cdd1e082a844556ef6405ee366786e2b3b7a010fcbd5`.

## How to verify

```sh
# top-level transport hash
shasum -a 256 -c M3-t30-rebuild-evidence-2026-11-05.zip.sha256

# extracted directory manifest: 10/10
cd t30-rebuild-2026-11-05 && shasum -a 256 -c SHA256SUMS

# guest transport manifest: 5/5
shasum -a 256 -c 06-SHA256SUMS

# zip members
unzip -l ../M3-t30-rebuild-evidence-2026-11-05.zip
```

The package's own `07-rebuild.json` is the conformance record: 21 tabulated
fields, 20 match, 1 differs by design (`window.is_baseline`; the rebuild is the
baseline-clean run). The trigger is `exit 0`, `stdout 05040a`, 3 bytes, 251 runs
with one distinct observation.

## Canonical path and c274893

T30's artifact is at exactly:

```
docs/handoffs/evidence/T30/build/original.elf
```

on `member-3/t62-host-safe` at commit
`c274893d3cc495fd8c1cbc9e28847b565b341f7e` (branch head `472b26e`).
`PROVENANCE.md` records the remote, branch, commit, blob hash and the three
aliases that are not identities (`build/original.elf`, `T30/build/original.elf`,
`/var/tmp/cwe416/original.elf`).

## Upgrade boundary

This delivery makes the missing bytes readable. It does **not**:

- promote T30 `V0`–`V5`;
- claim M4 verified the rebuild;
- ask M4 to upgrade record 118;
- relieve T8.3.

M4 can now re-hash the package and decide whether to verify. If M4 verifies, that
is M4's record to write. Until then, record 118 stays **reported**, and T30
build/trigger stays **PASS WITH LIMITATIONS** on the M1 side.

## Boundaries held

- T8.3 remains blocked.
- No merge to `main`, no tag, no live-success claim.
- No fixture byte changed.
- CWE416 contract remains absent/unloadable; no `invalid_*` invented.
