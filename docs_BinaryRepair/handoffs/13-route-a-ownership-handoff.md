# 13 — Route A ownership handoff: gate 3 formal evidence moves from M5 to M4

**Recipients:** Member 5 (handing over), Member 4 (new owner), Member 3 (guest/candidate
producer), Lead (approver)
**From:** Lead
**Date:** 2026-10-22
**Status:** **Ownership decision, not a gate result.** Gate 3 stays **CONDITIONALLY
FEASIBLE** (work status, never a pass); Gate 4 stays **NOT RUN**; the fixture stays
**NOT FROZEN**. No oracle, manifest, contract constant, or frozen hash changes in this
handoff.
**Why this exists:** Member 5 is carrying the candidate schema, the DeepSeek provider, the
contract revision, Route B (gate 4) and the distribution kit, and cannot access the team
guest. The verification slice requested to take the Route A evidence layer so gate 3 can
actually be closed. This file records what moves, what stays, and what must be produced
before anyone may say "pass".
**Companion method plan:** `12-m4-acceptance-evidence-plan.md` (Member 4) governs *how* the
verification is performed. This handoff governs *who owns what* and records the Route A
artifacts and review findings that plan must consume. Read both together.

---

## 1. Decision

1. **Member 4 owns the gate 3 formal evidence package** (the six items of
   `11-environment-evidence-confirmations.md` §3), transferred from Member 5 on
   2026-10-22 at the verification slice's request.
2. **Member 4 also owns the Route A half of gate 5** (cave / added-code safe placement).
   Member 5 keeps the Route B half.
3. **Member 5 keeps the Route A code** (`routea/`) and reviews any change to it, keeps the
   contract revision (with M4 confirmation and Lead approval), keeps Gate 4, the candidate
   schema, the provider, and the distribution kit.
4. **Member 3 stays the guest producer** and must supply the isolation evidence and the
   unprivileged-run path the six-case run needs. M4 verifies; M4 does not accept M3's
   conclusions as its own measurement.
5. **No status changes today.** Gate 3 moves from "owned by M5" to "owned by M4" while
   staying `CONDITIONALLY FEASIBLE`. It becomes `passed` only when all six handoff-11 items
   exist with raw evidence and an independent replay.

### 1.1 Why the split is honest

- Member 5's Route A probe ran on **GitHub Actions** (`routea-cave-probe`, run
  `39756078737`). That runner has network during installation, is not the Member 3 guest,
  and has none of the three isolation preconditions. It can support the *design* claim, but
  it cannot satisfy handoff 11 §3 items 4-5 (six-case run + isolation evidence).
- Member 5's own gate 4 checklist (`docs/route-b/11-gate4-formal-checklist.md`) records
  "No member3 VM/snapshot/offline access has been provided". The same access gap applies to
  the gate 3 six-case run.
- Member 4 already owns independent verification, the gate 6 evidence check, and the
  isolation-evidence review (handoff 10 §2). Moving the Route A evidence package keeps the
  producer/verifier separation and removes a slice the Route B owner cannot finish.

---

## 2. Ownership matrix after this handoff

| Work item | Before | After | Notes |
|---|---|---|---|
| Gate 3 formal evidence (six items) | M5 | **M4** | Handoff 11 §3 is the definition; handoff 12 is the method |
| Route A code `routea/` (worker, cave, audit) | M5 | M5 | M4 may propose patches; M5 reviews; tests re-run |
| Route A half of gate 5 (safe placement proof) | M5 + M3 | **M4** (+ M3 guest) | Cave mapping, header extension, edit-manifest audit |
| Route B half of gate 5 | M5 + M3 | M5 | Unchanged |
| Contract revision (`authorized_edits`, `allowed_calls`) | M5 | M5 | M4 confirms, Lead approves; §5.4 below needs a writer amendment |
| Gate 4 Route B unchanged round trip (formal) | M5 | M5 | Blocked on guest access, not on gate 3 |
| Isolation evidence (snapshot, egress, uid 1003, wrapper) | M3 | M3 | Deadline 2026-10-23 18:00; M4 verifies |
| Golden six-case oracle, `valid.json` / `invalid.json` | frozen team value | unchanged | M4 may not edit them; failures are diagnosed |

**Prohibited on both sides:** M4 must not write a gate-3 "pass" from M5's CI output or from
M3's probe logs; M5 must not mark gate 3 passed from the CI run. A missing item is
`not_run` / `NOT VERIFIED`, never a pass (`AGENTS.md`, handoff 11 §3).

---

## 3. Route A artifacts that already exist on `origin/main` (fetched 2026-10-22)

The local `member-4-verification` branch does not contain these; they live on
`origin/main` at `33235f5`. The M4 method plan `12-...md` §9 says "no candidate ELF, no
`original.elf` in this workspace" — that was true for the old checkout but is **stale after
the fetch**: both files are committed on `origin/main`. Do not rebuild a different
candidate; the committed one is the cross-check for reproducibility.

| Artifact | Path on `origin/main` | Fact |
|---|---|---|
| Original ELF | `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf` | 26,792 B, SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Frozen manifests | `.../tests/valid.json`, `.../tests/invalid.json`, `.../tests/SHA256SUMS` | 1,951 B / 1,460 B; hashes in §4 |
| Probe contract (not frozen) | `fixtures/public/.../contract.cave-probe.json` | `dest=50`, `max=49`, exit 1, 42-byte stderr, `allowed_calls=[fprintf, printLine, strcpy]`, 3 probe edits |
| Candidate (CI-built) | `routea/out/cave-probe.elf` | 26,792 B, SHA-256 `f3cb9cbb503fb0d47ebebab7053fa2ed37b7876ffe5122157d31fefc783f9fa7` |
| Edit manifest | `routea/out/edit-manifest.json` | incomplete for gate 3, see §5.2 |
| Static audit | `routea/out/audit.json` | 8 checks `true`; coverage gaps, see §5.3 |
| `readelf` audit | `routea/out/readelf-audit.txt` | CI runner readelf 2.42, Ubuntu 24.04, Python 3.12.15 |
| Six-case CI result | `routea/out/manifest-repaired.json`, `routea/out/runtime.log` | 6/6, candidate hash `f3cb9cbb...` |
| CI workflow | `.github/workflows/routea-probe.yml` | network during install; not the guest |
| Route A docs | `docs/route-b/{07,10,12,13}-*.md` | trampoline plan, worker, strategy C, cave probe |

**Measured layout facts from the committed `readelf` audit** (to be re-measured independently
in the guest — these are inputs, not M4's evidence):

- patched RX `PT_LOAD`: vaddr `0x401000`, offset `0x1000`, `p_filesz = p_memsz = 0x1000`,
  flags `R E`; next `PT_LOAD` starts at vaddr/offset `0x402000` — no overlap, page-congruent,
  file size `0x68a8 > 0x2000`;
- the extension changes only `p_filesz`/`p_memsz`; the probe record reports `0x8e9` ->
  `0x1000`, but the committed `readelf` audit shows only the **patched** value, so M4 must
  record the original's `p_filesz`/`p_memsz` (and every other program-header field) before and
  after itself; no new segment, same program-header count (13);
- the cave `0x4018e9-0x401fff` (1,815 B) starts immediately after `.fini`; no section covers
  it; `.text` ends at `0x4018dc`;
- patch: 5-byte `call` at `0x401304` redirected to `0x4018e9`
  (`e8 c7 fd ff ff` -> `e8 e0 05 00 00`); 72-byte guard + 42-byte message at the cave;
  valid path reuses the original `strcpy` return to `0x401309`;
- writer path: `fprintf@plt` `0x401120` and the `stderr` COPY relocation at `0x404080` already
  exist; no new import, no new relocation, no GOT/PLT edit;
- imports in the ELF (from the same audit): `strcpy`, `puts`, `iswxdigit`, `printf`,
  `__isoc99_swscanf`, `fprintf`, `wprintf`, `__isoc99_sscanf`, `rand`, `__ctype_b_loc`.
  There is **no** `write`, `fputs`, `fwrite`, `exit`, or `strlen`/`strncpy` import.

---

## 4. Identity and contract checks performed in this checkout (2026-10-22)

Method: read the committed git blobs and hash them. **No ELF parsing, no disassembly, no
execution on the host** — the project red line stays intact. These checks seed handoff 12
§8 item 1; they are not gate-3 evidence by themselves (the original's "untouched" status in
the guest still needs the guest-side hash).

| Check | Result |
|---|---|
| `original.elf` size / SHA-256 | 26,792 B / `aa428157...8393` — matches verification-design §4.4 |
| `valid.json` size / SHA-256 / line endings | 1,951 B / `17b2ee39...1e76` / LF only (0 CRLF) |
| `invalid.json` size / SHA-256 / line endings | 1,460 B / `d493f370...190d` / LF only (0 CRLF) |
| `tests/SHA256SUMS` | 2/2 entries match the committed bytes |
| Manifest set SHA-256 (canonical JSON rule) | `a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78` — matches handoff 08 |
| `contract.cave-probe.json` | `dest_capacity_bytes=50`, `max_valid_input_bytes=49`, `invalid_exit_code=1`, `invalid_stdout=""`, `invalid_stderr` = 42 B `4552524f523a...6374696f6e2063617061636974790a`; `allowed_calls=[fprintf,printLine,strcpy]` |
| Candidate `routea/out/cave-probe.elf` | 26,792 B / `f3cb9cbb...f9fa7` — matches `manifest-repaired.json` and `runtime.log` |
| `evidence/SHA256SUMS` (gate 6 crash evidence) | 3/3 entries match |

**Not reproducible in this checkout:**

- The claimed "SHA256SUMS 24/24" does not exist on `origin`: the only `SHA256SUMS` files are
  `tests/SHA256SUMS` (2 entries) and `evidence/SHA256SUMS` (3 entries). Provide the path,
  branch, or file; do not cite 24/24 until it is committed and verified.
- Commit `d1e0741` (reported as `member-3-route-a` containing the ELF) is **not on
  `origin`**; `origin/member-3-route-a` is `222f7e30` and has no `fixtures/` tree. The ELF is
  present on `origin/main` as blob `3e95f951...` with the expected hash. M3 should confirm the
  canonical source or push the branch.
- The guest at `D:\VMs\binrepair-u2404-x64-01` is not visible from this workspace host (no
  `D:\VMs`, no VM process). Guest execution must happen on the machine that holds the guest;
  this handoff records only what the repository can prove.

---

## 5. Review findings the gate-3 evidence package must resolve

These are Lead review notes on the committed Route A evidence. Each one is a concrete reason
the current CI probe is not yet gate 3.

### 5.1 Off-by-one in the documented valid-path return address

`09-route-a-added-code-ruling.md` §4.1 entry 1 says the redirect branches back to
`0x401308`, and `12-m4-acceptance-evidence-plan.md` §5.1/§5.2 use `0x401308` as the
after-copy breakpoint. That is wrong: the 5-byte instruction occupies
`0x401304-0x401308` inclusive, so the instruction after it is **`0x401309`**. The cave
implementation is correct (it consumes the original return address, which is `0x401309`),
but the contract text and any gdb script that breaks at `0x401308` would break mid-instruction
and could never hit. Fix: contract entry 1 and every script/record must say **`0x401309`**.
This is a documentation/contract-text correction, not an oracle change.

### 5.2 Edit manifest is incomplete for handoff 11 §3 item 2

`routea/out/edit-manifest.json` records only: original/patched hashes, function, one
`call_redirect` edit (`vaddr`, `size`, `new_hex`), one cave mapping (`vaddr`, `perm`, `size`),
empty `relocations_added`, and file sizes. It is missing the fields the gate-3 record needs:

- the displaced original 5 bytes at `0x401304` (`e8 c7 fd ff ff`);
- the header change with before/after values (`p_offset`, `p_vaddr`, `p_filesz` `0x8e9` ->
  `0x1000`, `p_memsz`, `p_flags`, `p_align`) and the program-header index;
- every changed/added file interval (inclusive file offsets): `0x1304-0x1308` and
  `0x18e9-0x195a`, plus the header field bytes;
- the exact 114 added bytes (72 code + 42 message) as hex, not only a size;
- the writer/termination mechanism (`fprintf@plt` + `stderr`, then `exit_group` syscall);
- tool/backend versions used to build it (LIEF, pyelftools, Capstone, Python).

Fix options: extend `routea/cave.py`/`worker.py` manifest emission with tests (M5 owner,
preferred), or have M4 emit a supplementary manifest in the guest from the recorded recipe.
Either way the gate-3 record hashes the file it cites.

### 5.3 Static audit coverage gaps

`audit_cave_layout()` checks 8 booleans. It does **not** check the following, all required
by handoff 11 §3 item 3 and the M4 plan §4.1:

- `p_offset % 0x1000 == p_vaddr % 0x1000` for the changed segment (page congruence);
- no overlap with the next `PT_LOAD` and `p_memsz >= p_filesz`;
- `e_entry` unchanged and every other program header field unchanged;
- section-to-segment mapping unchanged, section header table unchanged;
- `GNU_STACK` still non-executable (NX), `GNU_RELRO` unchanged, no permission broadening;
- dynamic section, `dynsym`, `.dynstr`, `.rela.*`, `.got`, `.got.plt`, `.plt` byte-identical;
- the cave-unused proof (no section, symbol, relocation, unwind FDE, or branch target in the
  original references `0x4018e9-0x401fff`).

The independent `readelf` + LIEF audit in M4's plan already covers these; this list tells M5
which gaps are known so they are not re-discovered as surprises.

### 5.4 Writer authorization is not yet in the contract

The probe writes with `fprintf@plt` + `stderr`, but `09-route-a-added-code-ruling.md` §4.1
enumerates the allowed writer as exactly `write`, `fputs`, or `fwrite` (plus `exit` if used).
`fprintf` is imported and `stderr` exists (measured); `fputs`/`fwrite`/`write`/`exit` are
not imported, and the only syscall option is a raw `write`/`exit_group` pair whose guest
seccomp policy is still unmeasured (handoff 09 §5 item 6).

The first persisted contract revision must therefore either:

- (a) explicitly authorize `fprintf` and reading `stderr` as an existing import/object (the
  minimal, measured choice), or
- (b) switch the repair to raw `write(2, msg, 42)` + `exit_group(1)` and record the guest
  seccomp result.

M5 owns the revision; M4 confirms; Lead approves. Do not freeze a candidate against the
unamended text — the probe contract's `allowed_calls=[fprintf,...]` is a probe value, not an
approved contract.

### 5.5 Reproducibility and runtime probe are claims, not yet evidence

- The candidate hash `f3cb9cbb...` comes from the CI build. A guest rebuild from
  `original.elf` + the recorded recipe must reproduce it byte-for-byte (or record the
  deviation) before handoff 11 §3 item 2 is satisfied.
- `13-routea-cave-probe.md` says the cave is "measured yes" file-loaded, but the committed
  `runtime.log` contains only the 6/6 summary; there is no committed mapping/permission/
  byte-comparison probe. M4's own probe (plan §4.2) is the required evidence.

### 5.6 CI run cannot serve as gate 3

`routea-cave-probe` installed dependencies with network available, ran on a GitHub-hosted
runner, and has no snapshot revert, no egress block, no uid-1003 wrapper. It is useful as a
cross-check and as the design proof; it is not handoff 11 §3 items 4-5. The formal six-case
run happens only in the team guest under the three isolation preconditions.

### 5.7 Review note on `routea/cave.py`

`_file_offset_ext()` selects the first `PT_LOAD` with `p_vaddr <= addr`. For this ELF that is
correct because every loadable segment has `p_vaddr == p_offset`, but it is not a general
mapping rule and should not be copied to another fixture without the explicit segment lookup.
No change requested now; flagged so the guest rebuild uses a segment-exact mapping check.

---

## 6. Gate-3 status after this handoff (no upgrade)

| Handoff 11 §3 item | State now | Who produces the missing evidence |
|---|---|---|
| 1. Separate candidate copy; original untouched; manifest hashes unchanged | **partial** — hashes verified in git (§4); candidate is a separate file; guest-side "untouched" hash still needed | M4 (guest) |
| 2. Candidate identity + reproducibility + complete edit manifest | **not_run** — hash recorded; no guest rebuild; manifest incomplete (§5.2) | M4 + M5 manifest fix |
| 3. Structural audit (cave R-X probe, header extension, no overlap, flags/NX/RELRO/canary/W^X, readelf + LIEF, no reloc/import edit) | **partial** — CI readelf + 8 static checks; independent audit not run | M4 (guest) |
| 4. Six-case run 6/6 on hashed final bytes from a reverted snapshot | **not_run** — CI 6/6 is supplementary only | M4 + M3 guest |
| 5. Isolation evidence for that run | **not_run** — M3 deadline 2026-10-23 18:00 | M3 |
| 6. Evidence bundle with hashes | **not_run** | M4 |

**Gate 3 label stays `CONDITIONALLY FEASIBLE`** (work status, never a pass). Gate 4 stays
`NOT RUN`. The fixture stays `NOT FROZEN`.

---

## 7. Handoff protocol

1. **M5 to M4 (this week):** hand over the Route A artifact list and hashes from §3, the
   build recipe (`python -m routea.cave build ... --cave 0x4018e9 --cave-size 1815
   --scope-authorized`), the known deviations (§5), and confirmation that no competing
   gate-3 evidence will be pushed. M5 keeps reviewing `routea/` changes.
2. **M4 produces:** the gate-3 record with per-item `PASS` / `FAIL` / `NOT VERIFIED`, the
   evidence bundle and its `SHA256SUMS`, and its own copies of the original, tests, and
   candidate. Raw evidence stays under `var/jobs/` and the committed record cites hashes.
3. **Independent replay:** M5 replays the build + hash commands from the record on a clean
   checkout/guest session and reports the observed hashes. A replay that does not match is
   `NOT VERIFIED`, not a cosmetic difference.
4. **Lead approves** the final gate-3 record and the contract revision. Gate 3 may only be
   labelled `passed` after 1-3; `FAIL` and `NOT VERIFIED` are reported as such.
5. **No self-approval:** the owner of the evidence (M4) does not approve it; M5 reviews, the
   Lead approves. M4's confirmation is evidence, not a second success rule (handoff 11 §6).

---

## 8. Immediate actions

| Owner | Action | Target |
|---|---|---|
| M4 | Accept this handoff; fetch `origin/main`; run the handoff-12 plan against the committed candidate and the guest; rebuild + audit + six cases under isolation; report per-item | 2026-10-23 |
| M5 | Draft the contract revision with the six `authorized_edits` plus the writer amendment (§5.4); complete the edit manifest (§5.2) or approve M4's supplementary manifest; keep gate 4 moving | 2026-10-23 12:00 |
| M3 | Isolation evidence (snapshot revert, egress block, uid-1003 wrapper) per handoff 11 §5; guest access for M4; confirm the canonical `original.elf` source (main blob vs `d1e0741`) | 2026-10-23 18:00 |
| Lead | Approve the contract revision after M5/M4 review; review the gate-3 record; resolve the "24/24 SHA256SUMS" and `d1e0741` discrepancies | after the above |

---

## 9. Confirmation log

- 2026-10-22 — Lead: gate 3 formal evidence and the Route A half of gate 5 reassigned from
  M5 to M4 at the verification slice's request; M5 keeps `routea/` code, the contract
  revision, gate 4, and the distribution kit; M3 keeps the guest and the isolation evidence;
  gate 3 stays `CONDITIONALLY FEASIBLE`, gate 4 `NOT RUN`, fixture `NOT FROZEN`; identity
  hashes of the original, both manifests, the manifest set, the probe contract, and the
  CI-built candidate verified in this checkout; review findings §5.1-§5.7 recorded for the
  evidence package. No oracle, manifest, contract constant, or frozen hash changed.

---

## 10. Lead ratification (2026-10-22)

The Lead reviewed this handoff and **ratifies it** as the team record: gate 3 formal evidence
and the Route A half of gate 5 move from M5 to M4; M5 keeps `routea/`, the contract revision,
gate 4 and the distribution kit; M3 keeps the guest and the isolation evidence; no
self-approval (M5 replays, the Lead approves).

**Independent read-only check of the artifact inventory in §3** (Lead: `git cat-file` blobs
plus a struct-only ELF parser; no execution, no network):

| Check | Observed |
|---|---|
| `original.elf` | 26,792 B, SHA-256 `aa428157...8393` |
| `valid.json` / `invalid.json` | `17b2ee39...1e76` / `d493f370...190d` |
| CI candidate `routea/out/cave-probe.elf` | 26,792 B, SHA-256 `f3cb9cbb...f9fa7` |
| ELF headers | 13 program headers each; `e_entry` `0x401170` unchanged; file size `0x68a8` both |
| RX `PT_LOAD` (index 3) | `p_offset` `0x1000`, `p_vaddr` `0x401000`, `p_align` `0x1000`, flags `0x5` (R E); `p_filesz`/`p_memsz` `0x8e9` -> `0x1000`; page congruence `0x0`/`0x0`; next `PT_LOAD` at `0x402000` (adjacent, no overlap) |
| redirect | file offset `0x1304`: `e8 c7 fd ff ff` -> `e8 e0 05 00 00`, rel32 `+0x5e0` -> target `0x4018e9` |
| cave | head at file offset `0x18e9` is the inline length loop; message at `0x1931` is exactly the 42 frozen bytes; the original bytes in the range are zero |
| byte diffs | only `0x108-0x109` / `0x110-0x111` (PT_LOAD[3] `p_filesz`/`p_memsz`), `0x1305-0x1308` (redirect), `0x18e9-0x195a` (added code/data); file size unchanged |
| committed audit/evidence | the 8-boolean `audit.json` and the incomplete `edit-manifest.json` described in §5.2-§5.3; CI `runtime.log` 6/6 with the same candidate hash; `readelf-audit.txt` from a GitHub-hosted runner, not the guest |

These checks establish artifact identity and structure only. They are **not** gate-3 evidence:
the runtime cave probe, the liveness traces, the guest rebuild/reproducibility, the six-case
run under the three isolation preconditions, and the evidence bundle remain M4's to produce
in the guest (handoff 12). The CI 6/6 is supplementary only (§5.6).

**Corrections the Lead applied to `09-route-a-added-code-ruling.md` on 2026-10-22:** the
valid-path return is `0x401309`; the writer amendment now authorizes the measured
`fprintf@plt` + existing `stderr` COPY relocation, with
`allowed_calls = ("strcpy", "printLine", "fprintf")` and no new import; gate 3 ownership and
the reply section point to M4. The M4 plan's after-copy breakpoint already uses `0x401309`,
so the earlier note that it "still needs fixing" is stale.

**Confirmation log (ratification).** 2026-10-22 — Lead ratifies the ownership transfer and
records the independent identity/structure verification above; no gate status changed
(gate 3 `CONDITIONALLY FEASIBLE`, gate 4 `NOT RUN`, fixture `NOT FROZEN`).
