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

**Approval status:** **DRAFT — NOT SIGNED.** Items **1, 2, 4, 6 PASS; items 3 and 5 `NOT
VERIFIED`**: the v1 bundle stays the raw evidence (no repack), and the item-6 support package
closes the missing chain/harness manifests. Remaining: G1 LIEF field bugs (item 3) and the
single-operator `revert.log` (item 5), then M5's build/hash replay; signature rows stay blank.
**Overall status:** **CONDITIONALLY FEASIBLE — items 3 and 5 `NOT VERIFIED`; M5 replay pending.**
Gate 3 is **not signed**.
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
| 3 | Structural audit (cave R-X runtime probe, `p_filesz`/`p_memsz`, redirect; NX/RELRO/canary/import diff) | **NOT VERIFIED** | v1 bundle shows the expected `0x8e9→0x1000` extension and cave-probe hits; supplement `lief-diff.json` (`e1e27295…`) still parses `PT_LOAD[1]` `flags="R"`/`align="E"`, imports `"(2)"`, `interp:null`. Pending VMer fix per handoff 26 §2 / 27 |
| 4 | Six-case run (4 valid + 2 invalid = 6/6 byte-exact) | **PASS** | v1 bundle raw evidence accepted (no repack): patched 6/6 (valid rc 0 / stdout 1,2,11,50 B; invalid rc 1 / stdout 0 / exact 42-byte stderr), original V0 4/6 (invalid-first rc 0/51 B, invalid-longer rc 139), candidate `c4a159…aa82` before = after; run from reverted `gate3-harness-v2` |
| 5 | Isolation evidence for that run (snapshot, egress block, uid 1003, wrapper attestation) | **NOT VERIFIED** | v1 isolation fields and snapshot evidence usable, but the `revert.log` still contradicts the single-operator identity; pending corrected log (handoff 26 §5 / 27) |
| 6 | Evidence with hashes (raw outputs + `SHA256SUMS` manifest; **no bundle package required** — handoff 21) | **PASS** | v1 bundle `0ef65546…` raw set 20/20 verified by M4; item-6 support package `3d49625c…` verified: `harness-v2-manifest.txt` `e53253cf…` (3,929 B) + `harness-manifest.json` `3bdbc339…` (1,641 B), inner `SHA256SUMS` verified; no bundle rebuild required |

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
| item-6 support zip | `gate3-item6-support-2026-10-22.zip`, 4,004 B, SHA-256 `3d49625c619c065e7942c8de7d433a58365f4ad616901f2de8b922cf962f72b0` |
| chain manifest | `harness-v2-manifest.txt`, 3,929 B, SHA-256 `e53253cf1c3408d832dd4c30b6e75afc4e8c2d621a2c0a3c0959131255878e7c` |
| harness manifest | `harness-manifest.json`, 1,641 B, SHA-256 `3bdbc3396fd183ed8563e2d7b0648d02be3a3c55c1a52ccc08890614a97ed678` |

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

1. **G1 fix (item 3):** corrected LIEF diff with `PT_LOAD[1]` `flags="R E"`, `align="0x1000"`,
   real import names, `interp` from `INTERP`; one expected difference =
   `p_filesz`/`p_memsz 0x8e9→0x1000`; GNU_STACK RW(NX), GNU_RELRO `0x403df8/0x208/R`,
   imports/relocs 13/13, canary absent (handoff 26 §2 / 27).
2. **G4 fix (item 5):** `revert.log` with one operator identity (VMer = M3 in a separate AI
   window), manual VMware Snapshot Manager revert + post-action observations only (handoff 26
   §5 / 27).
3. G2 is **done**: the item-6 support package `3d49625c…` carries the two manifests
   (`e53253cf…`, `3bdbc339…`) and its inner `SHA256SUMS` verifies; no bundle rebuild required.
4. **M5 replay (handoff 19/21):** reproduce candidate `c4a159…aa82` from the recorded recipe on
   `original.elf` (`aa428157…`), verify contract `24bfe568…4e37`, recompute the
   evidence-manifest/bundle `SHA256SUMS` hash over the delivered evidence set, and report the
   observed hashes. Until that replay exists, this record stays DRAFT and the signature line
   stays blank.


## 8. M5 review status: RE-REVIEW PENDING

M5 reviewed the first patch (`docs/route-b/20-m4-patch-review.md`) and requested changes
B1–B6. M4 resubmitted on base `ad1a1f8` (handoff 18): branch
`origin/member-4-routea-gate3` @ `2ac0f66`, patch
`docs/route-a/m4-patches/0002-member-4-routea-gate3-canonical-audit.patch`
(`b68aabcd…cab8`), additive tooling only. Until M5 records a new review, the M4 implementation
is **not accepted** and is not gate-3 evidence either way. M5's build/hash replay is recorded in §8.1 (handoff) and §8.2 (formal v2, NOT VERIFIED).

### 8.1 M5 build/hash replay — recorded, not a gate pass

**Scope:** M5 replayed the delivered handoff bundle, not the formal VM evidence
bundle. The formal VM bundle (items 3–6) remains `NOT VERIFIED`.

```text
bundle_zip:   dist/m5-routea-c4a159-2026-10-22.zip
bundle_zip_sha256:         957d73d4284a4e5ced27de451bacdfe8956751232bd4a1fa5aa6454dccdc108e
original:     aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393
candidate:    c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
contract file:15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df
contract canon:24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
regen script: 56331eedb4d72c55eec4e0f105fb20207576e6e6860b79ca4cedb175ed54e843
sha256sums_file_sha256:   640b448228ea8e16d15930c5c81a1478a11a82a1feddb122f6262157a87788dd
```

Commands used:

```bash
unzip -q dist/m5-routea-c4a159-2026-10-22.zip -d /tmp/m5replay
cd /tmp/m5replay
python3 regen_c4a159.py original.elf replayed.elf
sha256sum replayed.elf
sha256sum -c SHA256SUMS
sha256sum SHA256SUMS
```

Result: `replayed.elf` is byte-identical to `candidate.elf`; all `SHA256SUMS`
entries `OK`; `contract_sha256()` reproduces `24bfe568…4e37`; candidate and
contract match the record. **M5 replay = PASS for the handoff bundle.**

This row does not fill the M4 verifier row and does not approve Gate 3. The formal
VM bundle and items 3–6 are still required before M4 signs.

### 8.2 Formal v2 bundle replay — NOT VERIFIED (inputs missing)

**Bundle:** `gate3-bundle-v2-2026-10-22.zip`, 18,318 B,
SHA-256 `6151a80633fdde0d9b1ce87c126b01994a730625557d17297828468799710a65`.

```text
SHA256SUMS file sha256: 4ba6ebad30a4035c6a16c62c1fbab53dda67bce60db2b87510b83aa97f876934
sha256sum -c:           22/22 OK
candidate-before:       c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
candidate-after:        c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
contract canonical:     24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
contract file:          15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df
```

**Missing inputs:** the formal v2 bundle is a raw-evidence set; it does **not**
contain `candidate.elf`, `original.elf`, or `regen_c4a159.py`. Therefore these
required replay steps cannot be run against the formal bundle:

```text
python3 regen_c4a159.py original.elf replayed.elf
sha256sum replayed.elf
cmp candidate.elf replayed.elf
```

The handoff bundle replay in §8.1 reproduces `c4a159…` from the recorded
`original.elf` + `regen_c4a159.py`, but that is **not** formal-bundle evidence.
The formal bundle does bind the candidate hash via `candidate-before/after` and
`gate3-summary.json`, and its 22/22 `SHA256SUMS` verify.

**Formal v2 replay verdict: NOT VERIFIED** — no candidate change, no pass claim.
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
| M5 build/hash replay | Member 5 | 2026-10-22 | NOT VERIFIED — formal v2 bundle `6151…`; `SHA256SUMS 4ba6…` / 22/22; missing candidate.elf/original.elf/regen; handoff-only regen c4a159 |
| Lead approval | — | — | pending |

Do not fill these fields from a CI run, a static audit, or a verbal approval. A blank row is not
a silent pass: it keeps the record DRAFT and the gate `CONDITIONALLY FEASIBLE`.

