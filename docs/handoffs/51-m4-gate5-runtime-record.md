# 51 — Gate 5 Route A runtime placement record (PASS)

**Record owner:** M4 (independent verifier; Route A half of Gate 5)
**Gate:** Gate 5 — safe placement, Route A runtime
**Date opened:** 2026-10-29 (Asia/Hong_Kong)
**Status:** **PASS — Gate 5 Route A** (M4 verified; Lead approved). Gate 5 Route B
remains **NOT RUN**; this record covers Route A only.
**Subject:** candidate `routea/out/cave-probe.elf` (Route A), SHA-256
`c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`; original
`fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf`, SHA-256
`aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`.
**Probe:** M4-authored `scripts/m4_gate5_probe.py`, SHA-256
`f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb`, executed by
M3/VMer via the fixed-argv successor `jobwrap-gate5`
`90af91ef6b238428d202f891e5829ed81733b76dd9e7f184acd91f4cd769ff20`.
**Scope:** Gate 5 Route A runtime placement only. Not Gate 4, not V3/V4 acceptance,
not a repair claim; fixture remains `NOT FROZEN`.

**Identity/independence limitation:** the M4 verifier and the Lead are the **same
person/operator** (two AI windows of one person). The M4 verifier row and the Lead
approval row are therefore **not independent two-person signatures**; this record
must not be presented as independent human review. If the client requires a
genuinely independent second person, that requirement is **not satisfied**.

**Invocation:** `sudo /usr/local/sbin/jobwrap-gate5 probe m4-gate5 -- /srv/gate5-build /var/tmp/gate5-work`;
fixed execv: `/usr/bin/python3 /srv/gate5-build/scripts/m4_gate5_probe.py /srv/gate5-build /var/tmp/gate5-work`.
Old Gate 4 `jobwrap b232d60b…` is untouched; P4 is not re-signed.

**P3B note:** the P3B provenance hold does not change this Gate 5 Route A record;
Gate 4 P3B rows are separate and no P3B pass is written here.

## 1. Result rows — PASS

| ID | Check | Expected | Observed | Verdict | Evidence (file + SHA-256) |
|---|---|---|---|---|---|
| R1 | identity hashes | candidate `c4a159…aa82`, original `aa428157…8393`, script hash matches | all three match | **PASS** | `evidence/candidate.elf`, `original/original.elf`, `probe/m4_gate5_probe.py` |
| R2 | runtime mapping | `0x401000–0x401fff` mapped `r-xp` | `0x401000 0x402000 0x1000 0x1000 r-xp candidate.elf` | **PASS** | `probe-summary.json` R2 |
| R3 | memory = file | cave `0x4018e9–0x401fff` memory bytes equal candidate bytes (1815 B) | file = memory = `1926ce1f…6b1d`, 1815/1815 | **PASS** | `cave-file.sha256`, `cave-memory.sha256` |
| R4 | breakpoints / execution | `0x401304` → `0x4018e9` → `0x401309` → `0x401317`; cave decode; no early crash | all four markers reached; `cave` decode `mov %rsi,%r8` | **PASS** | `gdb-probe.log`, `probe-summary.json` R4 |
| R5 | six frozen cases | 6/6 byte-exact rc/stdout/stderr | 6/6 `ok=true`; invalid rc=1, valid rc=0 | **PASS** | `six-cases.json`, `case-*.{rc,stdout.bin,stderr.bin}` |
| R6 | isolation attestation | uid 1003, CapEff 0, NoNewPrivs 1, Seccomp active, no egress, independent netns, fixed argv | uid/gid 1003; CapEff 0; NoNewPrivs 1; Seccomp 2; `default_route=''`; `netns=net:[4026532222]`; fixed argv | **PASS** | `environment.txt`, `invocation.txt` |
| R7 | candidate stable | candidate SHA-256 before = after | `c4a159…aa82` stable | **PASS** | `probe-summary.json` R7 |
| R8 | evidence manifest | returned `SHA256SUMS` verifies every file; manifest hash recorded | evidence 29/29; root 43/43; evidence `SHA256SUMS` `05438764…ec8` | **PASS** | `SHA256SUMS`, `evidence/SHA256SUMS` |

**Overall:** **PASS — Gate 5 Route A**.

Scope note: R6 covers the successor's implemented isolation controls. The older
snapshot/revert and evaluator-unreadable checks belonged to the Gate 4/P4 chain;
this direct fixed-argv successor run does not claim them.

## 2. Exact commands / evidence custody

```text
window:         successor `jobwrap-gate5` probe m4-gate5; guest binrepair-vm, kernel 6.8.0-147
jobwrap-gate5:  /usr/local/sbin/jobwrap-gate5  SHA-256 90af91ef…ff20
invocation:     sudo /usr/local/sbin/jobwrap-gate5 probe m4-gate5 -- /srv/gate5-build /var/tmp/gate5-work
workdir:        /var/tmp/gate5-work
candidate_before= c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
candidate_after = c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
probe script:   scripts/m4_gate5_probe.py  SHA-256 f39a0302…d146cb
evidence manifest: evidence/SHA256SUMS  SHA-256 05438764a119ee979fa3ab175b8ec08250e392e112cd5203fbd52cdf77873ec8
root manifest:  SHA256SUMS  SHA-256 a193a749bceb17e854effa041bc315507e86a3e5288a0e7743c55cc2d578d845
zip:            gate5-evidence.zip  SHA-256 371cdacd15abe3e0db629440640ab4320dd3d3d72c8e323c33ed57a1c8dcbe8c
fail-closed:    exit 1; tampered probe got 15ba41dc…d915, expected f39a0302…d146cb
```

- M4 re-hashed every file; the executor summary was not used as the result.
- Raw evidence is not committed to the repo; the record cites filenames + hashes.
- A missing control or contradiction would make the record `NOT VERIFIED`/`FAIL`;
  no such contradiction was found.
- Source limitation: the named source commit `ac96e74` was not fetchable from this
  workspace, but the successor source bytes (`jobwrap_gate5.c`
  `09900e3ae11d8ad2f79faa7c67391a5b00f0f89b9a3f267535b9757ee3287340`), build
  recipe, and guest build environment are inside the verified zip.

## 3. Signature and closure order

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | M4 — same person/operator as Lead (limitation above) | 2026-10-31 | **PASS — Gate 5 Route A**; R1–R8 all PASS |
| Lead approval (Gate 5 Route A) | Lead — same person/operator as M4 (limitation above) | 2026-10-31 | **APPROVED — Gate 5 Route A PASS**; conditional approval `76` converted to final Route A approval |
| M5 (Route B half of Gate 5) | M5 | — | Route B separate; **NOT RUN** |

Gate 5 Route A is now **PASS**. Gate 5 Route B remains **NOT RUN**; fixture stays
**NOT FROZEN**; no final MVP tag is created by this record.
