# 80 — Gate 5 Route B final approval (candidate 208574ab)

**From:** Lead / M4 (same operator; role-separated, not human-independent)
**To:** M3, M5, M1, M4
**Date:** 2026-10-31 23:05 (Asia/Hong_Kong)
**Re:** `gate5b-evidence(1).zip`
**Status:** **Gate 5 Route B: PASS.** Gate 5 Route A is already PASS
(`docs/handoffs/51`, `77`). No final tag is created by this record.

## 1. Evidence verified

| Item | Value |
|---|---|
| zip | 381,915 B, SHA-256 `2f5fa9f8b1e5dd586c36ccf9adf80cdf08b4f7f7905264b2a4c7cb2651d38821` |
| root `SHA256SUMS` | 43/43 valid, hash `0eafc14b…7d19` |
| `routeb-evidence/SHA256SUMS` | 30/30 valid, hash `db75a782…ad9` |
| probe | `05d9a2cd417880c9be51e1a4cd4608158d94b50da233b223c2f4a589850edb82` |
| successor | `0066973d5304e06024b56fbc1e9d969d5007eac290314935129517f931209eee` |
| candidate | `208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717` |
| original | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| six cases | 6/6, raw rc/stdout/stderr present |
| runtime mapping | `0x401000–0x402000 r-xp`; independent ELF parse: 13 phdrs / 4 PT_LOAD / no W+X |
| entry/redirect | `0x4012b0 -> 0x4018ec` in tail; gdb markers present |
| memory=file | `1815/1815`, hash `e16ba161…25f3` |
| isolation | uid/gid 1003, CapEff 0, NoNewPrivs 1, Seccomp 2, no egress, netns isolated |
| fail-closed | tampered probe exit 1, expected/probe hash mismatch log |

## 2. R1–R8

| ID | Verdict | Note |
|---|---|---|
| R1 identity/binding | **PASS** | candidate in zip; original verified against the frozen fixture (original bytes were not re-included in the zip; probe summary records the same hash) |
| R2 mapping / no W+X | **PASS** | runtime maps `r-xp`; independent ELF parse 4 PT_LOAD, no W+X; no separate fresh readelf file included |
| R3 memory=file | **PASS** | `tail-memory.bin` = `tail-file.bin`, 1815/1815 |
| R4 entry/redirect | **PASS** | `0x4012b0 -> 0x4018ec`; gdb `BADSINK_ENTRY` and mapping log |
| R5 six cases | **PASS** | 6/6 raw `rc/stdout/stderr` files |
| R6 isolation | **PASS** | successor fixed-entry run; uid/caps/NNP/seccomp/no-egress/netns |
| R7 candidate stable | **PASS** | `208574ab…6717` stable |
| R8 manifest | **PASS** | root 43/43, evidence 30/30; no stale independent readelf |

## 3. Decision

**Gate 5 Route B: PASS.** Gate 5 Route A and B are both PASS. This record does
not itself create a final acceptance tag; M1/Lead may proceed with the final
submission record and tag.

Residual notes (not blockers):
- original.elf is verified from the frozen fixture rather than duplicated in the
  Gate5B zip;
- R2 uses runtime maps + independent ELF parse rather than a fresh readelf dump;
- the same-person M4/Lead limitation remains.

## 4. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | M4 | 2026-10-31 | **PASS — Gate 5 Route B**; R1–R8 |
| Lead approval | Lead | 2026-10-31 | **APPROVED — Gate 5 Route B PASS**; same-person limitation |
