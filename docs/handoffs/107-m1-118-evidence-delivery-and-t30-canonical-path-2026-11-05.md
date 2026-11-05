# 107 — 118 evidence delivered; T30 canonical path fixed; c274893 bound

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `m1/t30-acceptance-ab-2026-11-05`
- Scope: evidence delivery and provenance. No fixture, source, contract, or gate
  change. No merge to `main`, no tag, no live-success claim.
- Suite: `410 passed / 2 skipped / 0 failed` before this delivery; the delivery
  adds a tracked package and `delivery/SHA256SUMS`, and the suite is re-run in
  §7.

Numbering: `106` is the T30 acceptance/A-B record; this is `107`, the delivery
and canonical-path follow-up.

---

## 0. Status at a glance

| Item | Status | Basis |
|---|---|---|
| Record 118 evidence | **DELIVERED, readable** | 11 files + transport zip at `delivery/t30-rebuild-2026-11-05/`; source `origin/m3/cwe122-fixture-build` @ `87f6350` |
| Top-level zip SHA-256 | `968fb8d9…0fcbd5` | sibling `.sha256` matches the zip |
| Directory manifest | **10/10 OK** | `t30-rebuild-2026-11-05/SHA256SUMS` |
| Guest transport manifest | **5/5 OK** | `06-SHA256SUMS` |
| 118 conformance | **21 fields: 20 match, 1 differs by design** | `07-rebuild.json`; the difference is `window.is_baseline` |
| M4 upgrade of 118 | **not requested** | M4 may verify now that the bytes are readable; M1 does not ask |
| T30 build/trigger | **PASS WITH LIMITATIONS** (unchanged) | record 106; no V0–V5 promotion |
| T30 canonical path | **fixed** | `docs/handoffs/evidence/T30/build/original.elf` @ `c274893` |
| `c274893` | **bound** | remote `origin`, branch `member-3/t62-host-safe`, head `472b26e` |
| 116 §8 Fix A/B | **not the contract A/B, not T8.3** | see §5 |
| No-input contract A/B | **A selected (M5 v3)** | Lead decision; M5 `4c36898`; M1 intake/test adaptation in record 108 |
| T8.3 | **BLOCKED** | no contract/tests/candidate/V0–V5 |
| main / tag / live success | **no / no / no** | §6 |

---

## 1. What was delivered

Record 118's evidence was absent from the local M1 workspace and local clone
when record 106 was written. It already existed on the M3 branch at `origin`, so
it was fetched, verified and placed at a path M4/M5 can read:

```
delivery/t30-rebuild-2026-11-05/
  M3-t30-rebuild-evidence-2026-11-05.zip          (11 members)
  M3-t30-rebuild-evidence-2026-11-05.zip.sha256   (top-level digest)
  PROVENANCE.md                                   (canonical path + c274893)
  README.md                                       (verification/upgrade boundary)
```

The zip members are the required set:

```
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
```

The workspace copy at `M1-T30-118-evidence-2026-11-05/` additionally carries the
extracted directory and `VERIFICATION.txt`; the tracked repo package is the zip
plus its top-level hash and the two provenance/readme files.

### 1.1 Source and transport hashes

| Item | Value |
|---|---|
| source branch | `origin/m3/cwe122-fixture-build` |
| source commit | `87f63502d0fc5679f9dd797b7adc20c2069a5d39` |
| source directory | `docs/handoffs/evidence/t30-rebuild-2026-11-05/` |
| transport zip | `dist/M3-t30-rebuild-evidence-2026-11-05.zip` on that branch |
| zip SHA-256 | `968fb8d9a80f991567c0cdd1e082a844556ef6405ee366786e2b3b7a010fcbd5` |

Verification run by M1:

- top-level `.sha256` matches the zip;
- directory `SHA256SUMS` 10/10 (covers `00`–`07`, `README.md`, `collect.sh`);
- guest `06-SHA256SUMS` 5/5 (covers `01`–`05`);
- zip contains exactly the 11 files above, under `t30-rebuild-2026-11-05/`;
- extracted files are byte-identical to the directory.

The package's own `07-rebuild.json` tabulates **21** fields: **20 match**, one
differs by design (`window.is_baseline`: T30 recorded uid 14 / false, the rebuild
measured uid 11 / true). This supersedes record 106's earlier "12 of 13" line,
which came from the older 118 record before M3 expanded the table to 21.

---

## 2. Upgrade boundary: do not ask M4 to upgrade

Record 106 said the missing package was why M4 could not verify the rebuild. The
package is now readable, so that specific blocker is gone. It does **not**
follow that M4 must or should upgrade record 118, and M1 does not ask for it.

- M4 can now re-hash the 11 files and the top-level zip, and decide whether to
  verify the rebuild. That decision is M4's record to write.
- M1 does not promote `V1`/`V5`, does not call the rebuild M4-verified, and does
  not change T30's status. `PASS WITH LIMITATIONS` remains the M1-side status.
- The remaining limitations from record 106 still stand: M4 has not re-run the
  build/trigger, the guest was not available to M1, and the acceptance is scoped
  to gcc 13.3.0 / glibc 2.39 / the `gate4-harness` image.
- If M4 verifies, the upgrade is M4's; if M4 does not, the evidence is still
  delivered and the status is still reported. Neither path is a T8.3 credit.

---

## 3. T30 canonical artifact path

### 3.1 The one canonical path

```
docs/handoffs/evidence/T30/build/original.elf
```

at commit `c274893d3cc495fd8c1cbc9e28847b565b341f7e`, with SHA-256
`c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9` and size
25,344 bytes.

### 3.2 The three non-canonical spellings

| Alias | Where it appears | Why it is not the identity |
|---|---|---|
| `build/original.elf` | `T30/build.json#output.file`, `T30/SHA256SUMS` | package-relative; only valid after checkout/extraction of `docs/handoffs/evidence/T30/` |
| `T30/build/original.elf` | record 118 shorthand | shorthand; resolves only relative to `docs/handoffs/evidence/` |
| `/var/tmp/cwe416/original.elf` | `02-build.txt` | ephemeral guest build output; not a repository path |

`original.elf` / `./original.elf` in `trigger.sh` is the flat ZIP member and the
process invocation basename; it is not counted as an artifact path.

### 3.3 What “eliminate” means here

The three aliases cannot be erased from the historical 118 evidence or from
`T30/build.json` without changing bytes those files' `SHA256SUMS` bind. Rewriting
them would invalidate the very evidence this delivery is meant to make
verifiable. So this record:

- fixes the canonical path above;
- declares the three spellings aliases, not identities;
- requires new records and verifiers to use the canonical path;
- places the mapping in `delivery/t30-rebuild-2026-11-05/PROVENANCE.md`.

That is the honest form of “elimination”: one identity, aliases named, history
not rewritten.

---

## 4. The `c274893` git binding

Record 118's evidence README tells a reviewer to run
`git cat-file -p c274893:docs/handoffs/evidence/T30/build/original.elf`. That
command is unusable unless the reviewer knows which remote/branch contains
`c274893`; M4 reported the object as not resolvable in the local clone. The
binding is:

| Field | Value |
|---|---|
| remote | `git@github.com:chenfanaichifan/binary-repair.git` |
| branch | `member-3/t62-host-safe` |
| branch head | `472b26ea95f8bfbc63ccaba4ef4b4233e3816d75` |
| commit | `c274893d3cc495fd8c1cbc9e28847b565b341f7e` |
| ancestor of branch | **yes** |
| commit subject | `feat(t30): CWE416 fixture built in the guest, with a deterministic trigger` |
| blob SHA-256 | `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9` |
| blob size | 25,344 bytes |

Reproduce:

```sh
git fetch origin member-3/t62-host-safe
git cat-file -p c274893:docs/handoffs/evidence/T30/build/original.elf | sha256sum
# c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
git cat-file -s c274893:docs/handoffs/evidence/T30/build/original.elf
# 25344
```

This binding is written into `delivery/t30-rebuild-2026-11-05/PROVENANCE.md`, so
the provenance travels with the evidence rather than living only in a record.

---

## 5. 116 §8 Fix A/B is not the no-input contract A/B

Record 116 §8 proposes two fixes for the **synthetic** `src.c`:

- **Fix A** — drop `harness.c` from that synthetic recipe;
- **Fix B** — remove `main` from the synthetic `src.c` and let `harness.c` own
  the entry point.

Those are fixture-authoring repairs for a retired synthetic sample. They are
**not**:

- the no-input contract A/B from record 106 (extend `SecurityContract` with
  `input_mode=none` vs reselect an input-bearing public CWE416 case);
- a T8.3 decision;
- a change to T30's upstream `original.c` or its build.

Record 118 §1 already records that no Fix A/B was applied to the T30 upstream:
the case is compiled unmodified and its `main` is excluded by `INCLUDEMAIN`.
The Lead decides the no-input contract A/B; M1 does not substitute 116's fixes
for that decision, and 116 remains a diagnostic only.

---

## 6. T8.3 and constraints

**T8.3 remains blocked.** The delivery fixes an evidence-access gap; it does not
create a loadable CWE416 contract, frozen tests, a candidate, V0–V5 evidence, or
M4 verification. One public sample measured once is still one class.

Constraints held:

- no merge to `main`;
- no tag;
- no live-success claim;
- no candidate and no V0–V5 promotion;
- no fixture byte changed;
- no `contract.json` written;
- no `original.variant.elf` added.

Suite after the delivery is recorded in §7. The two skips are
`ELF execution requires Linux`; a skip is not a pass.

---

## 7. Checks run

```
pytest --ignore=tests/e2e -o addopts=""
410 passed, 2 skipped, 0 failed
```

Delivery checks:

```
cd delivery && shasum -a 256 -c SHA256SUMS              # 4/4
cd delivery/t30-rebuild-2026-11-05 && unzip -l M3-t30-rebuild-evidence-2026-11-05.zip   # 11 members
```

The 118 package's own checks are in `VERIFICATION.txt` in the workspace copy and
in the package `README.md`.

---

## 8. Evidence

| Path | Content |
|---|---|
| `delivery/t30-rebuild-2026-11-05/` | the tracked 118 delivery: zip, top-level `.sha256`, `PROVENANCE.md`, `README.md` |
| `delivery/SHA256SUMS` | hashes for the delivery files |
| `delivery/MANIFEST.md` | the three new rows (zip, provenance, readme) |
| `M1-T30-118-evidence-2026-11-05/` (workspace) | extracted 11 files, transport zip, `PROVENANCE.md`, `README-M1.md`, `VERIFICATION.txt`, wrapper `SHA256SUMS` |

---

## 9. Not claimed

- **Not** an M4 verification of 118; **not** a V0–V5 pass.
- **Not** a T8.3 fixture or T8.3 credit.
- **Not** a no-input contract approval; the contract remains absent/unloadable.
- **Not** a substitution of 116's Fix A/B for the contract A/B.
- **Not** a merge, tag, or live success.

## 10. Open items

1. **M4:** the evidence is readable; verify or decline on M4's own record. M1
   does not ask for an upgrade.
2. **A is selected:** M5 owns the v3 schema/hash revision; M1 adapted the intake
   and tests in record 108. No B corpus is needed.
3. **M1/M5:** when the canonical/live-bridge fork is reconciled, keep the
   canonical path and the `c274893` binding; do not replace them with the
   live-bridge mirror text.
