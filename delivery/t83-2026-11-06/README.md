# BinaryRepair — T8.3 / CWE-416 evidence archive

This directory is a curated, immutable snapshot of the T8.3 work products,
prepared for review from the local workspace on 2026-11-06.

## Status (do not read as acceptance)

```text
T8.3: BLOCKED
V4:   not_run
124:  inconclusive / required_check_not_run / symbolic
118:  VERIFIED (rebuild evidence package), independent of T8.3
M5:   code complete on a63f80d; member-5/complete-m5 frozen at 4c36898
```

T8.3 is not complete. The missing step is M4's independent V4 replay in the
guest, followed by the verifier's `replay.verified_by="m4"`, M1 ingestion, a
fresh 124 run, and the Lead's acceptance. No marker is written here.

No merge to `main`, no tag, and no live-success claim is made by this archive.

## Layout

```text
docs/         decisions, handoffs, status and verification records
data/         JSON reports, public keys, small evidence files
packages/     handoff and evidence ZIPs
patches/      API and code patches
inputs/       build.sh, valid.json, fixtures.md
reference/    project PDFs / DOCX / PPTX
historical/   selected earlier evidence and kit directories
checksums/    detached .sha256 sidecars
SHA256SUMS    digest of every file in this archive
```

The `data/m4_guest_key.pub` file is a **public** key. No private key, SSH
identity, token or secret is included in this archive.

## Canonical coordinates

```text
canonical/m1-m5-integration 3a107ab
m5/elf-type-check           a63f80d
M1 acceptance branch        252ffb0
main                        472aa94
```

The code itself lives on the repository branches; this archive contains the
delivery and evidence records, not a replacement source tree.

## Key hashes

```text
CWE121 contract canonical      24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
CWE416 no-input contract file  8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b
CWE416 no-input canonical      c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c
CWE416 original                c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
CWE416 candidate               46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0
```

## Reproduce locally

The local checks in this archive are code, schema, hashes and adapter checks.
They do not replace the M4 guest replay.

```sh
sha256sum -c SHA256SUMS
```

Follow the individual README/record in `docs/` for tests and commands.

## Boundary

This archive is evidence organization only. It does not:

- mark T8.3 complete;
- write `replay.verified_by`;
- merge `main`;
- create a tag;
- claim live success.
