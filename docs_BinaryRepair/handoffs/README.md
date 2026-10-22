# Handoffs: interface confirmation files for teammates

These are "ready to send" confirmation requests derived from the interface contracts in `docs_BinaryRepair/verification-design.md` (§4.1, §4.3) and the fixture/VM requirements in `TechDesign-BinaryRepair-MVP.md` (§5, §14). Goal: the slices develop in parallel against the same interface instead of guessing.

| File | Recipient | Confirm | Status | Unblocks after confirmation |
|---|---|---|---|---|
| `01-member-1-obligation-interface.md` | Member 1 | §4.1 Obligation / Verdict call interface + owner of `reviewed_scope_sha256` | Confirmed 2026-10-18; delivered on `member1/jobs-minimal` (`7f967bb`: approval, idempotent start, cancel, restart recovery, controller API, orchestration) and `member1/controller-only` (`f4c7fa9`: no GUI, shared-schema migrations, canonical routes). `main` moved to `1596b4f` | M4 re-ran `controller-only`: **15 passed / 0 skipped** (8 identity + 7 controller API). Open: branch is based on old `453fe95` and still uses the retired `001_init.sql` schema; `main` itself is red (5 failures) |
| `02-member-5-candidate-provider.md` | Member 5 | §4.3 candidate schema, data boundary, provider failure type | Confirmed 2026-10-18; contract in `verification-design.md` §4.3. Merge deferred: `main` layout is being reorganized by the owner | Implemented on `member-5-deepseek-schema` `ea29e56`: `app/domain/candidates.py`, `app/services/provider.py`, `tests/test_ai_boundary_contract.py` (22 tests) |
| `03-member-3-fixture-vm.md` | Member 3 | §5 fixture profile, frozen test manifest, VM or explicit blocker | To send | A real ELF and frozen input manifest unlock V1–V4 checks; a recorded blocker also unblocks planning |
| `04-member-3-oracle-freeze.md` | Member 3 | §4.4 behavioural oracle: `DEST_CAPACITY`, measured original behaviour, exact `ERROR_STDERR`, harness call shape | To send (blocking the fixture freeze) | Freezing the oracle lets Route A and Route B implement one shared V3 assertion set |
| `05-integration-decision.md` | Team (author: Member 1) | Root integration order and `agent/` archive rules | Decided 2026-10-20; binding for merges | Tells every slice what merges where, in which order, and what not to touch |
| `06-member-3-oracle-confirmation.md` | Member 3 | Oracle confirmation + gate 6 definition + V4/isolation escalation | Sent 2026-10-20; concrete gate 6 crash evidence received and verified 2026-10-20 (files + `SHA256SUMS` in `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/`) | Tells member 3 exactly what V3 will assert and what gate 6 evidence is accepted. Gate 6 stays **partial**: concrete counterexample PASS (5/5, exit 139, `ret` @ `0x401317`), symbolic detection pending V4 |
| `07-v4-isolation-decision.md` | Lead and team | Install the V4 toolchain (A) or record `unsupported` (B); fix guest isolation before any candidate run | **Decided 2026-10-22 — see `10-v4-isolation-decision-record.md`**: Decision 1 = A, time-boxed to 2026-10-23 18:00; Decision 2 = isolation confirmed as a hard precondition for candidate execution | Unblocks gate 4 environment work and V4 once M3 installs the tools and M4 verifies the evidence |
| `08-manifest-freeze-answer.md` | Member 3 / team | Full value and rule behind `MANIFEST_SET_SHA256 = a564f039…`; per-file hashes and paths it covers; why local reproduction failed | Written 2026-10-20 (reply) | Lets member 3 finalize the freeze record with the correct rule; also flags that `main` lacks `.gitattributes`, so Windows checkouts break the frozen hashes |
| `09-route-a-added-code-ruling.md` | Member 3, Member 5 | Route A scope: may a patch add data, call an existing libc writer, and place code in a cave/new region (strategy C)? | Decided 2026-10-22: **Option A**, strategy C is in Route A's range. The invalid-input oracle is unchanged; a contract revision (`authorized_edits`, `allowed_calls`) is required before a candidate freezes, not before gate 3. Follow-up 2026-10-22: gate 3 = **CONDITIONALLY FEASIBLE** (work status, not pass; cave runtime probe + six-case run pending), formal gate 3 evidence ownership moved to M4 (handoff 13, ratified), the `p_filesz`/`p_memsz` tail extension to 0x401fff and the measured `fprintf@plt` + `stderr` writer are authorized, and gate 4 is blocked on M5's `routeb/` scripts plus team-guest access (M5 target 2026-10-23 12:00) | Unblocks gate 3. Gate 3 then reports `FEASIBLE` with writer/placement recorded, or `UNSUPPORTED` with the concrete limiting fact; gate 4 does not depend on gate 3 |
| `10-v4-isolation-decision-record.md` | Team | Record the decision on handoff 07: toolchain install, guest isolation preconditions | Written 2026-10-22: Decision 1 = Option A, time-boxed to 2026-10-23 18:00 (owner M3, verifier M4); Decision 2 = clean snapshot + job-time egress block + unprivileged user are hard preconditions for any candidate execution; fixture stays NOT FROZEN | Unblocks the gate 4 environment work and V4 once the evidence is verified |
| `11-environment-evidence-confirmations.md` | M3, M4, M5 | Is the chained image hash acceptable, does root-wrapper + setuid count as the unprivileged user, and what exactly is the gate 3 pass criterion? | Confirmed 2026-10-22: chain manifest accepted with canonical format + guest fingerprint; root wrapper + setuid 1003 accepted under the listed conditions; gate 3 pass = **six required items**, not just 6/6 + audit. V4 smoke stays `inconclusive` | M3's 2026-10-23 18:00 evidence delivery; gate 3/gate 4 evidence handling |
| `12-m4-acceptance-evidence-plan.md` | M4 (method plan) | How M4 independently verifies the gate-3 evidence: cave loading, register liveness, six-case oracle, isolation controls | Written 2026-10-22 by M4; **plan only, all items `not_run`** | Consumed by handoff 13; the plan's "no candidate ELF" note is superseded by `origin/main` `33235f5` (see handoff 13 §3) |
| `13-route-a-ownership-handoff.md` | M5, M4, M3, Lead | Who owns the gate 3 formal evidence after 2026-10-22, and which Route A artifacts/findings the evidence package must consume | Decided 2026-10-22: **gate 3 formal evidence and the Route A half of gate 5 move from M5 to M4**; M5 keeps `routea/`, the contract revision, gate 4 and the kit; M3 keeps the guest and isolation evidence. Identity hashes verified in this checkout; seven review findings recorded. Gate 3 stays `CONDITIONALLY FEASIBLE`, gate 4 `NOT RUN`, fixture `NOT FROZEN` | Lead **ratified** 2026-10-22 and independently re-verified the artifact identity/structure from git blobs (13 program headers; only PT_LOAD[3] `p_filesz`/`p_memsz` `0x8e9`→`0x1000`, page-congruent, next LOAD at `0x402000`; redirect `e8 c7 fd ff ff`→`e8 e0 05 00 00` target `0x4018e9`; cave head and 42-byte message confirmed; CI 6/6 is supplementary only). Gives M4 the ownership, artifact inventory and review findings needed to close gate 3; composes with `12-m4-acceptance-evidence-plan.md` |
| `14-next-actions-by-owner.md` | Team | What each member still owes after the Route A ruling and the gate-3 design branch | Written 2026-10-22 18:00: per-owner actions, deliverables, deadlines; the contract proposal `ba33b4d0…` is Lead-checked; critical path is M3 isolation + guest access → M4 evidence → M5 contract + manifest → Lead approval → fixture-freeze decision | One-page coordination for 2026-10-23 |
| `15-member-3-route-a-vm-run.md` | Member 3 (executor), cc M4/M5/Lead | Run the Route A design's guest-side checks and deliver the guest evidence: static half, runtime cave probe, six frozen cases, original V0 shape, isolation evidence | Requested 2026-10-22 by the Lead at M4's request; **artifact hashes superseded by handoff 16** — use main `1826505` / candidate `c4a159…` / contract `24bfe568…`, not the M4 design branch. Run method and boundaries still apply | Unblocks the runtime half of gate 3 once the isolation preconditions hold; M4 verifies, M5 replays, Lead approves |
| `16-reply-to-member-3-delivery.md` | Member 3, cc M4/M5/Lead | Resolve M3's checkout blocker and answer the seven confirmations: git-bundle delivery, canonical artifacts, snapshot protocol, `jobwrap`, seccomp ruling, `original.elf` source, 24/24 SHA256SUMS | Answered 2026-10-22, then updated after M3's replies (§7 bundle paths/hashes + VMer split; §8 archive acceptance): **GitHub archive of `1826505` accepted as the main content source** (`D:\BinRepair\.tmp\binrepair-main-1826505.zip`, 471,658 B, `b0f4a18414e3887581769dd010063e7860abc62c8359f4051c4367573c03f61f`; codeload URL `…/zip/1826505`, downloaded 2026-10-22 18:30:24 +08; content hashes `aa428157…`/`c4a159…`/`24bfe568…` verified) — packaging-hash requirement dropped, bundle `fd35ae84…f52bf5` and `delivery-docs` optional; **VMer is a separate window of the same operator (not M4, not a fourth person); M4 verifies only**; M3 prepares/verifies/collects evidence, then notifies VMer for the `gate3-harness` snapshot; seccomp `0` with no filter; `original.elf` authoritative; 24/24 local list only | M3's guest run on the archive tree; M4 verifies, M5 replays, Lead approves |
| `17-gate3-m4-verification-runbook.md` | M4 (verifier), cc M3/M5/Lead | The six-item verification commands and evidence format M4 runs after M3's isolated run: identity hashes, reproducibility + schema-2 manifest, static+LIEF+runtime cave probe, six cases + original V0, isolation evidence, bundle/record; plus the V4 calibration plan for gate 6 support | Written 2026-10-22 after the canonical sync (main `1826505`, candidate `c4a159…`, contract `24bfe568…`); runbook only, nothing executed; every missing item stays `NOT VERIFIED`. Archive provenance pinned (handoff 16 §8/§9, full SHA-256 `b0f4a184…f61f`); actual test counts, six-case rows, candidate before/after and isolation/chain evidence are **pending from the VMer window** (record actual values only) | M4's signed gate-3 record after M3's run; V4 calibration after gate 3 |
| `18-m4-audit-resubmission.md` | M5 (reviewer), cc M4/M3/Lead | Re-submission of the retargeted M4 independent audit after review findings B1–B6 | Written 2026-10-22: base `ad1a1f8`, branch `origin/member-4-routea-gate3` @ `2ac0f66`, patch `docs/route-a/m4-patches/0002-…patch` (79,800 B, `b68aabcd…cab8`); B1–B6 disposition table; additive tooling only (no canonical file modified, no second candidate/contract); pure tests run on M4 host, ELF tests pending review host/VM | M5 re-review; merge as independent verification helper or keep on branch for handoff 17 |
| `19-replay-waiver-ruling.md` | M5, M4, M3, Lead | Written ruling on the replay conflict: is M5's replay waived for Gate 3? | Decided 2026-10-22: **only the full independent rerun is waived; M5's build/hash replay is required** — reproduce `c4a159…`, verify contract `24bfe568…`, recompute bundle `SHA256SUMS`/bundle hash, report observed values; missing/mismatched replay = `NOT VERIFIED`, signature blank. Canonical gate-3 draft pinned: `docs/route-a/gate3-record.md` on `member-4-verification`, SHA-256 `01ecabd5…83d6`, DRAFT unsigned with items 1–2 PASS / 3–6 NOT VERIFIED | Unblocks the DRAFT record wording; M4 signs only after items 3–6 PASS and M5 replay |
| `20-m4-draft-confirmation.md` | M4, M3, M5, Lead | Confirmation that M4 adopted the canonical gate-3 draft; verification-scope honesty; VMer snapshot name `gate3-harness-v2` | Written 2026-10-22: canonical draft `bddccbfe…e081` adopted (superseded by handoff 21 to `01ecabd5…83d6`), old `3dcdc862…` void, single copy; M3-side only verified the downloaded file hash, Lead-side checks are separate and neither is gate evidence; `gate3-harness-v2` recorded with the same image-record/attestation requirements; signing order unchanged | Keeps one draft/one snapshot name; unblocks VMer's v2 run and M4's later verifier signature |
| `21-bundle-not-required.md` | M3/VMer, M4, M5, Lead | VMer declines the packaged evidence bundle; how Gate 3 item 6 and M5's replay hash are defined without one | Written 2026-10-22: **item 6 = raw outputs + sorted `SHA256SUMS` + `evidence-manifest-sha256`; bundle packaging/tooling waived, nothing else**; manifest rules (LC_ALL=C sort, relative paths, self-excluded, two separate manifests, same-session binding); M5 replay = candidate `c4a159…` + contract `24bfe568…` + manifest hash; canonical gate-3 record re-pinned to `01ecabd5…83d6` | Unblocks VMer's no-bundle evidence delivery without weakening items 1–6 |
| `22-m4-no-guest-progress.md` | M5, M3/VMer, Lead | What M4 finished without the guest run, and the corrected citations | Written 2026-10-22: fixed false `audit.json`/`edit-manifest` hashes in the record and manifest (real `e915cb8b…` / `710657bf…` from main `4107836`); re-measured valid/invalid/set from main blobs; rebuilt `SHA256SUMS` (no BOM, LC_ALL=C, 11 entries); Gate 4 kit pins verified but formal NOT RUN; Gate 6 doc cites a non-object hash (`cffa8b95…`, should be `a398821e…`); V0 wording corrected (first invalid exits 0 silently, longer SIGSEGVs); Gate 5 Route A static placement proof written, runtime pending. Record hash now `01ecabd5…83d6`; statuses unchanged | Removes false evidence/citations before M5 replay; lets M4 sign only after VMer evidence |
| `23-phase-a-received.md` | M4, M3/VMer, M5, Lead | Phase A evidence received: M4 verification checklist, evidence transfer needed, and one `p_filesz`/`p_memsz` discrepancy | Written 2026-10-22: records VMer's Phase A values (snapshot `gate3-harness-v2`, chain manifest `e53253cf…`, six cases 6/6, original V0 4/6, isolation uid 1003/CapEff 0/NoNewPrivs 1/Seccomp 0, bundle `0ef65546…8d5`, honest UI-revert limitation); **items 3–6 stay NOT VERIFIED** until M4 verifies the transferred raw evidence and M5 replays; flags the `p_filesz`/`p_memsz` "same" claim as contradicting the authorized `0x8e9→0x1000` extension and asks for exact readelf/LIEF lines, chain-manifest file, and mapping wording | Unblocks M4's verification once the bundle is copied to an accessible path; prevents signing inconsistent evidence |
| `24-phase-a-verification-gaps.md` | M3/VMer (fixes), M5, Lead | M4's independent verification of the Phase A bundle: identity accepted, four blocking gaps before items 3–6 can be PASS | Written 2026-10-22: bundle SHA `0ef65546…` matches and inner `SHA256SUMS` 20/20; six-case/V0/candidate/isolation fields accepted as usable inputs. **Still NOT VERIFIED** because (G1) `lief-diff.json` load/GNU_STACK arrays are empty and `nx:null` while readelf shows `p_filesz/memsz 0x8e9→0x1000`; (G2) chain/harness manifest files missing from the bundle; (G3) gate3-summary's six items are not handoff 11 §3's six; (G4) `revert.log` contradicts the single-operator VMer definition. Fixes + re-verify + M5 replay required before PASS; no signature | Gives M3/VMer a precise fix list; keeps the record DRAFT and items 3–6 NOT VERIFIED (later superseded by handoff 25: items 3–5 PASS, item 6 still blocked) |
| `25-phase-a-ruling.md` | M4, M3/VMer, M5, Lead | Lead ruling on the Phase A verification gaps: which findings block and which are closed | Written 2026-10-22: **items 1–5 PASS, item 6 NOT VERIFIED**; G3 (summary label mapping) closed as cosmetic; G1 resolved by substituting **readelf + checksec** for the broken LIEF view, with exact `p_filesz/memsz 0x8e9→0x1000` and safety attributes recorded; G4 operator wording closed; G2 remains the only blocker — deliver `harness-v2-manifest.txt` (`e53253cf…`) and harness manifest (`3bdbc339…`) or a hashed supplementary set (no bundle rebuild). Record re-pinned to `01ecabd5…83d6`; M5 replay + signature still pending | Unblocks items 3–5; item 6 files are the last evidence gap before M5 replay/signing |

**Read `05-integration-decision.md` before merging anything into `main`:** `agent/` is a read-only archive; merge order is ① member 5 → ② member 4 → ③ member 1 (controller slice only) → ④ member 2; archives are frozen snapshots.

## Confirmation log

- 2026-10-22 — **Route A added-code scope ruling (Option A)**, reviewed by Member 4:
  strategy C (added data + call to an existing libc writer + added code in a cave or a new
  RX region) is inside Route A's allowed range, per PRD F2 ("may use another suitable
  location … records added code, necessary redirection") and Tech Design §8 "Added-code
  policy". The invalid-input oracle is **unchanged**; option B (relaxing `stderr`) is
  rejected because it would weaken a frozen gate and break the F5 cross-route comparison.
  The frozen contract instance on `main` currently has `authorized_edits = ()` and
  `allowed_calls = ("strcpy", "printLine")`, so a contract revision is required **before a
  strategy-C candidate freezes**, not before gate 3; `valid.json` / `invalid.json` and the
  manifest set hash do not change. Gate 3 reports `FEASIBLE` (with writer and placement
  recorded) or `UNSUPPORTED` (with the concrete limiting fact) — never an oracle edit.
- 2026-10-20 — Member 1 added `app/services/orchestration.py` on
  `member1/jobs-minimal` (`7f967bb`): it builds V0–V5 obligations (missing gate =
  `not_run`, never dropped), calls `decide_attempt_outcome` once per route,
  persists the `Verdict` fields, and uses `decide_run_outcome` for the run. It
  imports the engine and adds no second success rule; 5 orchestration tests.
  Full-suite run at `7f967bb` (temporary worktree): **31 passed, 0 skipped**
  (8 identity + 7 controller API + 11 GUI + 5 orchestration). Still open: no
  `member1/controller-only` branch on `origin`; canonical `/runs` and
  `/attempts/{id}/evidence` routes absent; `app/db/schema.sql` not replaced by
  member 5's migrations; the copied member-4 domain files differ only by a UTF-8
  BOM (our slice owns those files at step ②).
- 2026-10-20 — Member 1's full controller is on `member1/jobs-minimal`, not
  `main`: `f41558a` adds approval binding, idempotent start, `cancel_job`, and
  restart recovery; `d7813d0` adds the controller HTTP API. A full-suite run at
  `d7813d0` (temporary worktree) gives **26 passed, 0 skipped** (8 identity +
  7 controller API + 11 GUI smoke/language). Two new integration decisions are
  recorded in `05-integration-decision.md`: member 5's
  `migrations/001_init.sql` + `SecurityContract` are the single schema/contract
  authority (member 1's two-table `app/db/schema.sql` is retired), and Tech
  Design §7 API paths are canonical with member 2's paths kept as aliases.
  `main` is still `453fe95` with the old minimal jobs snapshot; member 1's
  description of `main` as README + `agent/` only (`29f2a6a`) is not the current
  `origin/main`.
- 2026-10-20 — Member 1's minimal job controller landed: `app/services/jobs.py`
  on `member1/jobs-minimal` (`6e8ce4b`), merged to `main` via PR #5. `create_job`
  and `get_job` exist; `approve_contract`, `start_run`, and restart recovery are
  explicitly pending. Running `tests/integration/test_identity_state.py` gives
  **5 passed, 3 skipped** (the skips name the missing entry points); `main`'s
  file is byte-identical to that commit, and the full `main` suite measures
  **16 passed, 3 skipped**.
- 2026-10-20 — Duplicate AI-boundary tests are settled as **deleted, not
  restored from git history**. Member 5 migrated the four boundary assertions
  that were unique to the member-4 suite (512 accepted / 513 rejected, 33-entry
  list rejected, 20,001-char `replacement_c` rejected, `allowed_targets`
  override) into `tests/test_ai_boundary_contract.py`; it now has 22 tests and
  the full branch suite reports 107 passed on `ea29e56`. Drift is prevented by
  the generated schema (`schemas/generated/candidate.v1.json`) plus
  `python schemas/generate.py --check`, not by keeping a second assertion copy.
  `main` is being reorganized by the owner (only `agent/`, `run.bat`,
  `start.ps1` remained at the time of writing), so the acceptance engine is not
  merged there until the layout is confirmed.
- 2026-10-18 — Member 5 accepted §4.3 with these details:
  `validate_candidate(payload, allowed_targets=None)`; Route A is 12 top-level
  fields and Route B adds `recovered_function_sha256` and `replacement_c`
  (14 total); the default target allowlist includes `copy_input` and
  `copy_name`; limits are 512 characters per free-text string, 32 entries per
  list, and 20,000 characters for `replacement_c`, with pydantic
  `extra="forbid"`; `validate_candidate_for_context` carries the hash-ownership
  and evidence-signing checks; provider failures are
  `app.services.provider.ProviderFailure(reason: FailureReason)` with
  `TIMEOUT`, `QUOTA`, `BUDGET`, `EMPTY`, `MALFORMED_JSON`, `SCHEMA`.
  Tests for the limits, the Route B shape, the allowlist override, and the
  provider reason enum now live in `tests/test_ai_boundary_contract.py`; provider
  failures are covered by `tests/test_provider.py`. The member-4 skeleton
  `tests/integration/test_ai_boundary.py` was removed on 2026-10-20 as
  superseded.
- 2026-10-18 — Member 5's branch moved everything to the shared root in commit
  `e175436` (`app/domain/candidates.py`, `app/services/provider.py`,
  `binaryrepair_ai/`, `schemas/`). Running the contract suite in an isolated
  worktree of that branch gives **17 passed, 0 skipped, 0 failed**. The
  member-4 branch still skips until the branch is merged. Earlier the code was
  under `route-b/`, which the tests in this repository could not import.
- 2026-10-18 — Member 1 confirmed §4.1 as-is:
  - 4.1.1: four fields are enough; gate id / evidence id / timestamps stay in
    the database row or `detail`.
  - 4.1.2: direct keyword-only call; a thin adapter may only map a job record
    to arguments.
  - 4.1.3: both rows store the scope hash; the **run row is authoritative** and
    the decision reads only it. Contract row is the source at freeze time; run
    creation copies it in the same transaction.
  - 4.1.4: V0–V5 kind names accepted.
  - Member 1 asked whether the hash must come from a canonical serialization.
    Answer: no — the engine treats `reviewed_scope_sha256` as opaque and only
    checks presence, so verification imposes no format. The contract/approval
    layer owns correctness; the engine would not detect a wrong non-empty hash.

## Measured state (2026-10-20)

- `python -m pytest tests -q -p no:cacheprovider` on the member-4 branch -> **40 passed, 1 skipped** (the skip is the identity/state suite without `app.services.jobs`; skip is not a pass)
- `origin/main` at `453fe95` (temporary worktree) -> **16 passed, 3 skipped** (the identity skips are the unimplemented `approve_contract` / `start_run` entry points in the old snapshot)
- `member1/jobs-minimal` at `7f967bb` (temporary worktree) -> **31 passed, 0 skipped** (8 identity + 7 controller API + 11 GUI smoke/language + 5 orchestration)
- Member 5's branch `ea29e56` -> `tests/test_ai_boundary_contract.py` has **22 tests**; the full branch suite is reported at **107 passed** (reported by member 5, not independently re-run here: remote fetch from this sandbox fails on a TLS CA-bundle path error)
- The stale `var/wt-member5` worktree from 2026-10-18 was removed on 2026-10-20 so it no longer breaks pytest collection

## After a reply arrives

1. Apply the agreed changes to §4.1 / §4.3 of `verification-design.md` and to the corresponding implementation under `app/domain/`.
2. Update the "Status" column above to "confirmed (date)" and record any decision that deviates from the default answer in `MEMORY.md`.
3. Re-run the integration tests once the owning member lands the module and confirm skip becomes run; skip never counts as a pass.
