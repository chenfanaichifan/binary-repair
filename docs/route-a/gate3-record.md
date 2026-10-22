# Gate 3 acceptance record — Route A

**Verifier:** Member 4 (verification slice)
**Date:** 2026-10-22
**Candidate:** `routea/out/cave-probe.elf`, SHA-256 `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`
**Original:** `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf`,
SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`
**Contract:** canonical SHA-256 `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`
(M5 canonical v2; M4 proposal `ba33b4d0...` superseded — see §6)
**Basis:** handoff 11 §3 (six required items), handoff 12 (M4 plan), handoff 16/17/18/19
(M5 canonical contract, six-item matrix, build recipe, routea review), verification-design §4.4

**Approval status:** **DRAFT — NOT SIGNED.** Items **1–2 PASS; 3–6 `NOT VERIFIED`** again: the
v1 Phase A bundle is **superseded** and the supplement is not a v2 delivery (handoff 26). Items
3–6 will be re-assessed only after a v2 bundle with the fixed LIEF fields, merged
chain/harness manifests, remapped summary and single-operator revert log is independently
re-verified. M5's build/hash replay is still required; signature rows stay blank.
**Overall status:** **CONDITIONALLY FEASIBLE — items 3–6 `NOT VERIFIED`; v2 pending; M5 replay
pending.** Gate 3 is **not signed**.
**Identity:** VMer is **M3 operating in a separate AI window** — one person, not two.

---

## 1. Frozen identity (re-measured by M4)

| Value | Frozen / claimed | M4 independent measurement | Match |
|---|---|---|---|
| original ELF SHA-256 | `aa428157...8393` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` | PASS |
| candidate SHA-256 | `c4a159...aa82` | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` | PASS |
| contract canonical SHA-256 | `24bfe568...4e37` | independently recomputed from `contract.json` (17 fields, 4 lists sorted, compact JSON) = `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` | PASS |
| contract file SHA-256 | not claimed | `15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df` (1,998 B) | recorded |
| original size | 26,792 B | 26,792 B | PASS |
| candidate size | 26,792 B | 26,792 B | PASS |
| `valid.json` / `invalid.json` / manifest-set hashes | `17b2ee...` / `d493f3...` / `a564f0...` | recomputed from the `origin/main` `4107836` blobs: `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` / `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` / set `a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78` | PASS (static blob identity; guest re-measure still required) |

> **Revision 2026-10-22 19:30:** evidence-file hashes in §5 were recomputed from `origin/main`
> `4107836`; the earlier `1b1c7321…` audit/manifest citation was wrong (not a repository object).
> Item statuses and signing order are unchanged. This revision changes the record hash; the
> previous `bddccbfe…` / `b6fedd2b…` hashes are superseded.

## 2. M4 independent structural measurements

Measured with a struct-only ELF parser; no candidate byte executed, no producer module imported.

**Program headers:** only `PT_LOAD[3]` changed — `p_filesz`/`p_memsz` `0x8e9 -> 0x1000`, offset
`0x1000`, vaddr `0x401000`, flags `R E`, other three segments unchanged, loadable count 4.

**Redirect at vaddr `0x401304` (file offset `0x1304`):** `e8 c7 fd ff ff` -> `e8 e0 05 00 00`
(rel32 `+0x5e0` -> `0x4018e9`), matching the manifest.

**Changed file intervals (13):** `0x108-0x109`, `0x110-0x111` (header fields), `0x1305-0x1308`
(redirect tail), `0x18e9-0x1959` (added cave code + message), as itemised in the earlier run.

## 3. Schema-2 manifest claims re-measured against candidate bytes

M5's schema-2 manifest was checked by reading the candidate bytes directly:

| Claim | M4 measurement | Match |
|---|---|---|
| added code 71 B @ file `0x18e9` sha256 `cd032694...` | recomputed = `cd0326946d931b2566d888e7244a917ef90f97e62be60c87805d4d03bbd7203e` | PASS |
| added data 42 B @ file `0x1930` sha256 `083d3bfb...` | recomputed = `083d3bfb2d9e1fa4978aabdd2318d60c67bd54f2a34d0086b0a9d11f6f84f69b` | PASS |
| added data is the frozen message | bytes equal `ERROR: input exceeds destination capacity\n` | PASS |
| writer = `write(2)` syscall | `syscall` (`0f 05`) at code offsets 52 and 64; `mov eax,1` at offset 30; `mov eax,231` at offset 54 | PASS |
| termination = `exit_group(1)` | `mov eax,231` present | PASS |
| no `fprintf@plt` call | no `e8` call target lands in the PLT range `0x4011xx` | PASS |

**Consequence:** the candidate writes the message with a raw `write` syscall and terminates with
`exit_group(1)`. It needs **no new import, no PLT/GOT edit** — the cleanest possible writer for
this contract. This differs from handoff 12 §2.2, which described a `fprintf@plt` + `stderr`
COPY-relocation writer based on the earlier `f3cb9cbb...` candidate. The contract's
`authorized_edits` item 4 allows writing to fd 2, so the syscall path is authorised; the
`allowed_calls` list allows `fprintf` but the code does not use it.

## 4. Six required items (handoff 11 §3)

| # | Item | Status | Evidence / reason |
|---|---|---|---|
| 1 | Separate candidate copy; original untouched | **PASS** | original hash still the frozen value; candidate is a separate file |
| 2 | Candidate identity and reproducibility | **PASS** | candidate hash matches; schema-2 manifest complete (displaced/added/intervals/header/writer/termination/tool_versions); build recipe `18-build-recipe.md` with `regen_c4a159.py` (stdlib-only, fail-closed) |
| 3 | Structural audit (cave R-X runtime probe, `p_filesz`/`p_memsz`, redirect; NX/RELRO/canary/import diff) | **NOT VERIFIED** | v1 bundle showed the expected `0x8e9→0x1000` extension and cave-probe hits, but its LIEF diff is unusable (empty arrays in v1; supplement `e1e27295…` still parses `PT_LOAD[1]` `flags="R"`/`align="E"`, imports `"(2)"`, `interp:null`). Re-verify after v2 fixes the field-level LIEF bugs (handoff 26 §2) |
| 4 | Six-case run (4 valid + 2 invalid = 6/6 byte-exact) | **NOT VERIFIED** | v1 reported 6/6 and original V0 4/6, but v1 is superseded; re-run/re-hash results must be carried into v2 and re-verified on the v2 artifact |
| 5 | Isolation evidence for that run (snapshot, egress block, uid 1003, wrapper attestation) | **NOT VERIFIED** | v1 isolation fields looked right, but the revert log contradicts the single-operator identity and v2 must carry the corrected `revert.log` (handoff 26 §5) |
| 6 | Evidence with hashes (raw outputs + `SHA256SUMS` manifest; **no bundle package required** — handoff 21) | **NOT VERIFIED** | v1 bundle `0ef65546…` is superseded; v2 must merge `harness-v2-manifest.txt` (`e53253cf…`) and `harness-manifest.json` (`3bdbc339…`), rebuild `SHA256SUMS`, and publish the new zip SHA-256 |

**Gate 3 verdict: NOT signed — CONDITIONALLY FEASIBLE.** Only `PASS` / `FAIL` / `NOT VERIFIED`
are valid item labels; "partial" is not a gate label. Items 3–6 are hard requirements; a CI
`6/6` does not substitute for them (handoff 13 §5.6).

## 5. Producer inputs used (read-only, not M4 evidence)

Hashes below were recomputed from `origin/main` `4107836` blobs (the paths resolve from the
main tree / the `1826505` archive, not from the docs branch):

| File | SHA-256 (size) |
|---|---|
| `routea/out/edit-manifest.json` (schema 2) | `710657bf9d21068444c4a2d85e05c1e57557625604c589d8f8268edfa1a10fc0` (2,658 B) |
| `routea/out/audit.json` | `e915cb8bb211ed4305400ec02d0cb80847fe98bb1d27b264ac1032ade5165821` (305 B) |
| `routea/out/readelf-audit.txt` | `086ce7c87f535fbc5ed583da529a05ddfae0c75846c6a543bd4aaab1d02825c5` (7,829 B) |
| `fixtures/.../contract.json` (file hash) | `15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df` (1,998 B) |
| M5 contract revision approval | `docs/route-b/16-contract-revision-approval.md` |
| M5 six-item matrix | `docs/route-b/17-gate3-six-item-matrix.md` |
| M5 build recipe | `docs/route-b/18-build-recipe.md` |
| M5 routea review | `docs/route-b/19-routea-review.md` |

## 6. Deviations and open items

1. **Contract hash changed.** M4's proposal `ba33b4d0...` is superseded by M5's canonical v2
   `24bfe568...`. The changes are explicit (same six `authorized_edits`, `entry 1 = 0x401309`,
   `allowed_calls = ("fprintf","printLine","strcpy")`, environment assumptions narrowed to
   "CET compile-time only", "guest seccomp not yet recorded"). M4 re-measured the new canonical
   hash and it matches. **Approval must cite `24bfe568...`, not `ba33b4d0...`.**
2. **Writer mechanism differs from handoff 12 §2.2.** Actual candidate uses raw `write` +
   `exit_group` syscalls, no `fprintf@plt`. handoff 12's writer description is stale (based on
   `f3cb9cbb...`). The contract authorises fd-2 write, so the implementation is in scope; the
   record must state the syscall path, not the stale PLT description.
3. **Candidate hash history.** handoff 12 records `f3cb9cbb...`; the delivered candidate is
   `c4a159...`. handoff 12's value is superseded; `c4a159` is the single gate-3 subject.
4. **M4 audit branch resubmitted (handoff 18).** `origin/member-4-routea-gate3` @ `2ac0f66`
   (base `ad1a1f8`) retargets the tooling to `c4a159…`/`24bfe568…` and fixes M5's B1–B6; patch
   `docs/route-a/m4-patches/0002-member-4-routea-gate3-canonical-audit.patch`
   (`b68aabcd…cab8`). M5 re-review is pending; the old `7977bac` / patch `0001` is superseded.
5. **M4's earlier `f3cb9cbb` cross-check is void** and must not be cited.

## 7. What must happen before this record can be signed

1. **v2 bundle must exist** (handoff 26): fixed LIEF fields (`PT_LOAD[1] flags "R E"`,
   `align "0x1000"`, real import names, `interp` from `INTERP`; one expected difference =
   `p_filesz`/`p_memsz 0x8e9→0x1000`), merged `harness-v2-manifest.txt` (`e53253cf…`) and
   `harness-manifest.json` (`3bdbc339…`), rebuilt `SHA256SUMS`, new zip SHA-256; v1
   `0ef65546…` marked superseded.
2. **v2 summary mapping** to handoff 11 §3 (six item names as in handoff 26 §4), each item with
   its evidence files; no "static tests" as item 2.
3. **v2 `revert.log`** with one operator identity: VMer = M3 operating in a separate AI window;
   manual VMware Snapshot Manager revert + post-action observations only; target
   `gate3-harness-v2`, boot/fingerprint checks, candidate `c4a159…`.
4. **M4 re-verification** of items 1–6 against the v2 artifact; only then items 3–6 become
   `PASS`/`FAIL`/`NOT VERIFIED` and the record is re-hashed and re-notified.
5. **M5 replay (handoff 19/21):** reproduce candidate `c4a159…aa82` from the recorded recipe on
   `original.elf` (`aa428157…`), verify contract `24bfe568…4e37`, recompute the
   evidence-manifest/bundle `SHA256SUMS` hash over the delivered v2 evidence set, and report the
   observed hashes. Until that replay exists, this record stays DRAFT and the signature line
   stays blank.


## 8. M5 review status: RE-REVIEW PENDING

M5 reviewed the first patch (`docs/route-b/20-m4-patch-review.md`) and requested changes
B1–B6. M4 resubmitted on base `ad1a1f8` (handoff 18): branch
`origin/member-4-routea-gate3` @ `2ac0f66`, patch
`docs/route-a/m4-patches/0002-member-4-routea-gate3-canonical-audit.patch`
(`b68aabcd…cab8`), additive tooling only. Until M5 records a new review, the M4 implementation
is **not accepted** and is not gate-3 evidence either way. M5's build/hash replay (handoff 19)
is also still pending.

## 9. Signature — BLANK (DRAFT)

**Signing order (handoff 19 §5):**

1. **M4 verifier row** — filled only after items 3–6 are independently verified as `PASS`
   (runtime cave probe, six cases, isolation evidence, bundle). M4's signature covers the
   verifier row; it is **not** an approval and **not** a gate pass.
2. **M5 build/hash replay row** — M5 records the observed replay values (candidate
   `c4a159…aa82`, contract `24bfe568…4e37`, recomputed bundle `SHA256SUMS`/bundle hash). A
   mismatch voids the record and returns it to `NOT VERIFIED`; it does not edit the candidate.
3. **Lead approval row** — filled last, after 1 and 2, as the gate decision.

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | — | — | **blank until items 3–6 are PASS** |
| M5 build/hash replay | — | — | pending (handoff 19) |
| Lead approval | — | — | pending |

Do not fill these fields from a CI run, a static audit, or a verbal approval. A blank row is not
a silent pass: it keeps the record DRAFT and the gate `CONDITIONALLY FEASIBLE`.

