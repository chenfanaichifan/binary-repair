# Gate 3 acceptance record — Route A

**Verifier:** Member 4 (verification slice)
**Date:** 2026-10-22
**Candidate:** `routea/out/cave-probe.elf`, SHA-256 `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`
**Original:** `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf`,
SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`
**Basis:** handoff 11 §3 (six required items), handoff 12 (M4 plan), verification-design §4.4
**Approval status:** **NOT self-approved.** Requires Member 5 replay and Lead approval.
**Overall status:** **CONDITIONALLY FEASIBLE — runtime items `not_run`.** Static identity and
structure were re-measured by M4; the six-case run, isolation evidence, and runtime cave probe
were not executed in this environment and are recorded as `NOT VERIFIED`, never as passed.

---

## 1. Frozen identity (re-measured by M4)

| Value | Frozen | M4 measurement | Match |
|---|---|---|---|
| original ELF SHA-256 | `aa428157...8393` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` | PASS |
| candidate SHA-256 | `c4a159...aa82` (manifest) | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` | PASS |
| original size | 26,792 B | 26,792 B | PASS |
| candidate size | 26,792 B | 26,792 B | PASS |
| `valid.json` SHA-256 | `17b2ee39...1e76` | not re-measured here (input delivered separately) | NOT VERIFIED |
| `invalid.json` SHA-256 | `d493f370...f90d` | not re-measured here | NOT VERIFIED |
| manifest set SHA-256 | `a564f039...3a78` | not re-measured here | NOT VERIFIED |

> The manifest files were not present in this workspace; their hashes are taken from handoff 12
> and must be re-measured before item 3/4 are signed. **Do not promote them on this record.**

## 2. M4 independent static measurements

Measured with a struct-only ELF parser (`python .gate3/verify_static.py`); no candidate byte was
executed and no producer module was imported.

**Program headers (loadable segments):**

| Segment | original | candidate | Change |
|---|---|---|---|
| `PT_LOAD[3]` | off `0x1000`, vaddr `0x401000`, filesz/memsz `0x8e9`, flags `R E` | off `0x1000`, vaddr `0x401000`, filesz/memsz `0x1000`, flags `R E` | filesz/memsz `0x8e9 -> 0x1000` |
| other three | unchanged | unchanged | none |

**Redirect at vaddr `0x401304` (file offset `0x1304`):**

- original: `e8 c7 fd ff ff` (call `strcpy@plt`)
- candidate: `e8 e0 05 00 00` (rel32 `+0x5e0` -> `0x4018e9`)

**Changed file intervals (13, measured from the two files):**

```
0x108-0x109 (2)   0x110-0x111 (2)   0x1305-0x1308 (4)
0x18e9-0x18f1 (9) 0x18f3-0x18fd (11) 0x1901-0x1903 (3)
0x1907-0x1908 (2) 0x190c-0x190d (2) 0x1911-0x1914 (4)
0x1918-0x1919 (2) 0x191d-0x1920 (4) 0x1924-0x1925 (2)
0x1929-0x1959 (49)
```

The `0x108/0x110` pair are the `p_filesz`/`p_memsz` header fields; `0x1305-0x1308` is the
redirect tail (`0x1304` byte is `e8` in both files, so it does not appear as a difference);
`0x18e9-0x1959` is the added code and message (113 bytes).

## 3. Six required items (handoff 11 §3)

| # | Item | Status | Evidence / reason |
|---|---|---|---|
| 1 | Separate candidate copy; original untouched | **PARTIAL — static PASS** | original hash still the frozen value; candidate is a separate file. Runtime check of the original after the run not done. |
| 2 | Candidate identity and reproducibility (re-apply recipe) | **PARTIAL — identity PASS, reproducibility `NOT VERIFIED`** | candidate hash matches the manifest; the re-apply recipe (I5) was not executed in this environment. |
| 3 | Structural audit (cave R-X runtime probe, `p_filesz`/`p_memsz`, redirect) | **PARTIAL — static PASS, runtime probe `NOT VERIFIED`** | headers and redirect re-measured (above). The R-X runtime probe (`0x401000-0x401fff`, cave bytes == memory, instruction executes at cave entry) was not executed. |
| 4 | Six-case run (4 valid + 2 invalid = 6/6 byte-exact) | **`NOT VERIFIED`** | requires guest execution; not run here. |
| 5 | Isolation evidence for that run (snapshot, egress block, uid 1003) | **`NOT VERIFIED`** | no guest available to this workspace. |
| 6 | Evidence bundle (raw outputs + hashes) | **PARTIAL** | this record + `docs/route-a/SHA256SUMS`; raw guest logs, probe output, and isolation attestation are missing. |

**Gate 3 verdict: NOT signed.** Items 4 and 5 are hard requirements; while they are missing the
gate stays **CONDITIONALLY FEASIBLE**, not passed.

## 4. Producer inputs used (read-only, not M4 evidence)

| File | SHA-256 | Note |
|---|---|---|
| `routea/out/edit-manifest.json` | `ff383caf7199c1ee7451c38f249ae64b9d493b67bd67aecbe4052f0584ba5d14` | producer manifest; read only |
| `routea/out/audit.json` | `1b1c73211f4953126f4e989cba4d5dcb68757d1b190ac4c8010776890cdb0af2` | producer audit; read only |
| `routea/out/readelf-audit.txt` | `086ce7c87f535fbc5ed583da529a05ddfae0c75846c6a543bd4aaab1d02825c5` | producer readelf output; read only |

## 5. Deviations and open items found during this check

1. **Candidate hash differs from handoff 12.** handoff 12 records a CI-built candidate
   `f3cb9cbb...`; the delivered and measured candidate is `c4a159...`. Both are 26,792 B and the
   edit manifest names `c4a159...`. Record which candidate is the gate-3 subject before signing;
   do not mix the two.
2. **Cave size is two numbers, not one.** The edit manifest says 113 bytes (guard + message);
   handoff 12 describes the cave span `0x4018e9-0x401fff` = 1,815 bytes (the mapped space).
   M4 measured 113 changed bytes inside that span. Both are consistent; the record must state
   both explicitly.
3. **Contract status.** `contract.route-a-v1.json` is a **proposal**, not an approved contract
   revision (handoff 12 §2.2). The gate-3 record must cite the approved revision and its hash;
   `routea_vm_check.sh` currently points at the proposal file, so its contract-hash line is not
   evidence of an approved contract.
4. **Manifest completeness.** The committed `edit-manifest.json` still lacks several fields M4
   requires (displaced 5 bytes, before/after header values with segment index, complete
   changed/added intervals as file offsets, exact added bytes, writer/termination mechanism, tool
   versions). Handoff 12 §2.1 already flags this; the gate-3 record must cite an extended
   manifest or M4's supplementary one.

## 6. What must happen before this record can be signed

1. Run items 4 and 5 in the disposable guest (six cases, isolation evidence).
2. Re-measure `valid.json` / `invalid.json` / manifest-set hashes in the guest.
3. Record the runtime cave probe.
4. Member 5 replays the build/hash commands; Lead approves. **M4 never approves its own evidence.**
