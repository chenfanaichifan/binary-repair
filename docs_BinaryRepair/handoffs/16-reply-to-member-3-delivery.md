# 16 — Reply to Member 3: delivery bundle, canonical artifacts, snapshot protocol, seccomp

**Recipients:** Member 3 (guest owner, executor), cc Member 4, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** reply to Member 3's seven confirmations and the checkout blocker. **No gate status
changes:** gate 3 `CONDITIONALLY FEASIBLE`, gate 4 `NOT RUN`, fixture `NOT FROZEN`; the six
handoff-11 items stay `not_run`/`NOT VERIFIED` until the isolated guest run exists.
**Supersedes handoff 15 on artifact hashes:** handoff 15 names the M4 design branch
(`member-4-routea-gate3` @ `7977bac`, candidate `f3cb9cbb…`). That branch is **unreviewed and
superseded** (`docs/route-b/19-routea-review.md`); the sole Gate 3 candidate is now
`c4a159…` on `main` `1826505` with contract `24bfe568…`. Everything else in handoff 15 (run
method, evidence format, boundaries) still stands.

---

## 1. Your blocker: branch/files not in `D:\BinRepair`

Confirmed and expected. M4's branch is **not on `origin`**, and your machine has no
credentials for the private remote, so `git fetch origin` fails with `SEC_E_NO_CREDENTIALS`.
Of your three options, the team uses a **git bundle** (no credentials, no history rewrite, and
the record is verifiable). A direct-copy archive is provided as a fallback.

**Delivered file** (transfer it to `D:\BinRepair` first):

```text
routea-gate3-delivery.bundle
```

It contains two refs:

| Bundle ref | Content |
|---|---|
| `delivery-main` | `origin/main` `1826505` — the canonical Route A candidate `c4a159…`, `contract.json`, schema-2 manifest, build recipe, tests, `routeb/` scripts, docs `route-b/15–19` |
| `delivery-docs` | `member-4-verification` — handoffs 09–16, the M4 static gate-3 record |

```bash
cd D:\BinRepair
git bundle verify <path>\routea-gate3-delivery.bundle
git fetch <path>\routea-gate3-delivery.bundle \
  refs/heads/delivery-main:refs/remotes/bundle/delivery-main \
  refs/heads/delivery-docs:refs/remotes/bundle/delivery-docs
git checkout -B gate3-c4a159 refs/remotes/bundle/delivery-main
git log --oneline -1        # 1826505
```

The bundle is self-contained; it does not need the remote. Verify its SHA-256 against the
value sent with the delivery before fetching. Fallback if bundle history conflicts: unzip
`binrepair-main-1826505.zip` into a separate directory and run there (record the tree hash).

**Do not use** `member-4-routea-gate3` / `7977bac` / `f3cb9cbb…` / `ba33b4d0…`: superseded,
not evidence, not reviewed. The design is now the canonical main tree.

---

## 2. Canonical artifacts (replace handoff 15 §1)

| Item | Value |
|---|---|
| main | `1826505` |
| candidate | `routea/out/cave-probe.elf`, 26,792 B, SHA-256 `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` |
| contract | `fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json`, canonical SHA-256 `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` (approved in `docs/route-b/16-contract-revision-approval.md`) |
| original | `fixtures/public/.../original.elf`, 26,792 B, `aa428157…8393` |
| manifests | `tests/valid.json` `17b2ee39…1e76`; `tests/invalid.json` `d493f370…90d`; set `a564f039…3a78` |
| build recipe | `docs/route-b/18-build-recipe.md`; primary recipe is the stdlib-only `regen_c4a159.py` inside the committed `dist/m5-routea-c4a159-2026-10-22.zip` (SHA-256 `957d73d4…c108e`, as pinned on main) |
| evidence docs | `docs/route-b/15` (candidate handoff), `16` (contract approval), `17` (six-item matrix), `18` (recipe), `19` (review) |

The canonical candidate uses `write(2)` + `exit_group(1)` (71-byte guard, 42-byte message at
`0x401930`), **not** the older `fprintf` variant. `c4a159…` is the only accepted gate-3
candidate.

**Integrity note:** the local workspace copy `dist/m5-routea-c4a159-2026-10-22.zip` hashes
`ecb9df57…`, not the pinned `957d73d4…` (it was regenerated locally). Use main's committed
zip or the bundle, not that local copy.

---

## 3. Answers to your seven confirmations

1. **Guest access: accepted.** SSH key path and `lab@192.168.30.128` are fine; record the
   exact method in the report. Keep the private key out of any commit or transcript; discover
   the IP from the MAC `00:0c:29:94:c6:0f` in the VMware DHCP leases or prefer the hostname.
2. **Snapshots: accepted with one new image record.** `isolation-ready` (uid 8, off) stays the
   reset basis. Your `gate3-harness` plan is approved, but a new snapshot is a **new image
   record** (handoff 11 §1): recompute the chain manifest **powered off**, record the guest
   fingerprint, and update the image record before the run. Who does what: M3 prepares and
   shuts down cleanly; the **named VM console operator** ("VMer") takes the snapshot and powers
   the guest on (see §7 — the Lead's workspace host cannot see `D:\VMs`; M4 verifies
   independently unless M4 is explicitly confirmed as that operator); M3 reverts to
   `gate3-harness` and continues.
3. **`jobwrap` shape: accepted** (`sudo /usr/local/sbin/jobwrap gate3 original|patched
   <case-id|all>`, `probe`), subject to handoff 11 §2: root-only 0700, fixed validated
   `execv` array, netns before the uid drop, setuid 1003 with no passwordless sudo,
   NoNewPrivs/caps-0/rlimits, scrubbed env. Set the `patched` target in `targets.conf` to a
   fixed job path plus the expected hash `c4a159…` before taking the harness snapshot; then
   run one `gate3 original valid-empty` sanity case and record the wrapper hash/owner/mode.
4. **Tools: ready.** Everything you listed is sufficient. The missing pieces are now on main:
   `tests/test_routea_manifest.py`, `tests/test_routea_cave.py`, `tests/test_fixture_contract.py`
   and the `routeb/` scripts (gate 4, after gate 3). `lief` 1.0.0 is only needed for the
   independent structural view (handoff 11 §3 item 3).
5. **Seccomp: not required by gate 3.** Record `Seccomp: 0`; isolation is netns + uid 1003 +
   NoNewPrivs + caps-0 + rlimits as already approved. The candidate terminates via
   `exit_group` and writes via `write(2)`, both allowed with no filter. Do **not** add a
   filter during the run (it would change the image record). This closes the contract's
   "guest seccomp policy not yet recorded" assumption.
6. **`original.elf`: your file is authoritative.** Hash matches `aa428157…8393` and main's
   blob. `d1e0741` was a stale claim in an earlier M4 report; it is not on `origin` and is
   dropped — no action needed.
7. **"24/24 SHA256SUMS": found.** `D:\BinRepair\fixtures\public\CWE121_src_char_declare_cpy_51b\SHA256SUMS`,
   checked 24/24 by you. It is not on `origin`; include its path and SHA-256 in your report and
   commit it to your branch when credentials allow. It is **not** a gate-3 blocker.

---

## 4. Revised run order on main `1826505`

1. Checkout the bundle's main branch and verify hashes: original, `valid.json`,
   `invalid.json`, candidate `c4a159…`, contract via `app.domain.contracts.contract_sha256`.
2. Run main's tests in the guest: `pytest tests/test_routea_manifest.py
   tests/test_routea_cave.py tests/test_fixture_contract.py -q -p no:cacheprovider`; record the
   actual count (M5 reports 162 passed / 2 skipped for the full suite).
3. Regenerate the candidate with the stdlib recipe (from the committed zip) and compare:
   `c4a159…` must match, else stop.
4. Runtime cave probe: `0x401000-0x401fff` mapped `r-xp`; memory at `0x4018e9` equals the
   candidate file bytes; the cave entry executes. Breakpoints `0x401304` / `0x4018e9` /
   `0x401309` (never `0x401308`).
5. Before the harness snapshot: `gate3 original valid-empty` sanity case; set `patched`
   target; record harness versions/config hashes.
6. Six frozen cases on `c4a159…` from the reverted `gate3-harness` snapshot,
   SHA-256 recorded before and after; per-case rc/stdout/stderr; original V0 (4/6) in the same
   session.
7. Evidence: raw outputs under `/var/lib/binrepair/evidence/...` plus `summary.json`, the
   image chain manifest and guest fingerprint, wrapper attestation, per-case table; hand the
   hashed summary to M4. M4 verifies, M5 replays, the Lead approves.

---

## 5. Snapshot answer: "要我现在关机吗？"

**Not yet.** Do these first, then ask the VM console operator (see §7) for the snapshot:

1. verify the bundle main checkout and the six frozen inputs;
2. regenerate `c4a159…` and run the static tests;
3. set the `patched` target (fixed path + `c4a159…` hash) and run the `gate3 original
   valid-empty` sanity case;
4. write the worklog (wrapper version/hash, `targets.conf` hash, evidence directory, tool
   versions, image chain `142849c7…d628e` for the current basis);
5. then clean shutdown and tell the VM console operator "ready for `gate3-harness` snapshot"
   (see §7).

The VM console operator takes the snapshot and powers the guest on; you revert to
`gate3-harness`, record the new chain manifest (powered off) and guest fingerprint, then
continue with the runtime probe and the six cases.

---

## 6. Reporting and verification

Report per item: command / observed / raw evidence file / SHA-256 / `PASS` / `FAIL` /
`NOT VERIFIED`, per case, not aggregates. Missing isolation or a missing hash is
`NOT VERIFIED`. M4 verifies independently (own copies), M5 replays the build/hash commands, the
Lead approves. Do not relabel, do not edit the oracle, do not touch `original.elf`.

**Confirmation log.** 2026-10-22 — Lead answers M3's seven confirmations: bundle delivery,
canonical `c4a159…`/`24bfe568…` on main `1826505`, `gate3-harness` snapshot protocol with a
named VM console operator, seccomp not required (record `Seccomp: 0`), `original.elf`
authoritative, 24/24 file located, M4 design branch recorded as superseded. No gate status
changed.

---

## 7. M3's reply (2026-10-22) and Lead confirmation

M3 confirms the §4 order and the §5 prep rule, reports that the bundle is **not yet on
`D:\BinRepair`**, and asks for the two files with absolute path + SHA-256. It also asks who
actually operates the VMware UI, and confirms M3's own role is prepare/verify/evidence only.

**Delivery files and hashes** (source paths on the Lead/VM host):

| File | Absolute path | Size | SHA-256 |
|---|---|---|---|
| bundle (primary) | `D:\BinaryRepair_Project\delivery\routea-gate3-delivery.bundle` | 1,509,265 B | `fd35ae84ca42e15600128da00e24ce76094a886d19a35a2016eaea1371f52bf5` |
| tree archive (fallback) | `D:\BinaryRepair_Project\delivery\binrepair-main-1826505.zip` | 472,197 B | `42658976e574a77d42fb2b814c0992c15e6a65b9c1b65da52c9b5d844b2bc021` |

**Transfer is the missing step, not a fetch problem.** M3's machine and the Lead/VM host are
different hosts; the bundle can only reach `D:\BinRepair` when M4/the VM host operator copies
it there. The Lead agent cannot write to M3's `D:\BinRepair`. Copy both files to
`D:\BinRepair\` (keep the names) and verify:

```powershell
Get-FileHash D:\BinRepair\routea-gate3-delivery.bundle -Algorithm SHA256
# fd35ae84ca42e15600128da00e24ce76094a886d19a35a2016eaea1371f52bf5
Get-FileHash D:\BinRepair\binrepair-main-1826505.zip -Algorithm SHA256
# 42658976e574a77d42fb2b814c0992c15e6a65b9c1b65da52c9b5d844b2bc021
git bundle verify D:\BinRepair\routea-gate3-delivery.bundle
```

Then §4 step 1 uses the absolute bundle path in the `git fetch` command. If the two hosts
share a network path, use that path instead and record it in the report.

**Division of labor, corrected.** The VM console is not in M3's workspace and not in the Lead
agent's `D:\VMs` view; it belongs to the **named VM operator ("VMer")**. Effective split:

- **VMer:** takes the `gate3-harness` snapshot, powers the guest on, and keeps the console
  access; the operator's name is recorded with the snapshot.
- **M3:** prepares and verifies inside the guest, runs the §4 steps, collects evidence; does
  not operate the VM console.
- **M4:** independent verification of all six gate-3 items and the record; M4 takes the
  snapshot **only if** M4 is explicitly confirmed as the VMer. If M4 is not the VMer, do not
  record M4 as the snapshot operator.
- **Lead:** approval.

**Accepted without change:** bundle first then §4; no shutdown/snapshot before the package
arrives; seccomp recorded `0` with no filter added; `original.elf` from the repository;
24/24 `SHA256SUMS` as a local list with path + hash, not a gate-3 blocker; gate 3
`CONDITIONALLY FEASIBLE`, gate 4 `NOT RUN`, fixture `NOT FROZEN`.

**Action for M3 after transfer:** reply with `Get-FileHash` outputs, `git bundle verify` output,
`HEAD=1826505`, and the six frozen hashes; then start §4. Gate status unchanged.

**Confirmation log (M3 reply).** 2026-10-22 — Lead confirms M3's §4/§5 reading, supplies the
delivery paths/hashes, assigns the snapshot to the named VMer (M4 verification only unless
confirmed as VMer), and keeps M3's role as prepare/verify/evidence. No gate status changed.

