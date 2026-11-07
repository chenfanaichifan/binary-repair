# AI-Assisted Progress Report - 2026-11-06

| Field | Value |
|---|---|
| Project | BinaryRepair - AI-driven binary vulnerability repair and correctness verification |
| Workspace | Local project clone used for the 2026-11-06 delivery |
| Repository | `chenfanaichifan/binary-repair` (private) - https://github.com/chenfanaichifan/binary-repair |
| Snapshot | 2026-11-06 21:36 +08:00 |
| Scope | All AI-assisted work that left a trace in this folder on 2026-11-06: commits, records, probes, packages, verification notes, and the delivery archive |

---

## 0. Scope, method, and limits

This report reconstructs the day from artifacts, not from memory or chat transcripts:

- **44 commits** authored on 2026-11-06; 43 were pushed across six remote branches and one (`2d741d5`) remained local-only.
- **Records 125-136**, the M4 verification series, and the M1/M3/M5 handoff notes.
- **383 files** in the `delivery/t83-2026-11-06` archive, including the T8.3 evidence package.
- The branch and test-count measurements recorded by M1, M3, M4, and M5.

"Progress" here means one of four things:

1. a commit that landed on a branch;
2. a record that changed a decision, status, or assignment;
3. a package or evidence bundle that another role can run or verify;
4. a gate result that was independently checked.

Unlogged chat, private reasoning, and work performed only outside this folder are not counted. The report also does not claim which AI model or agent produced a given line; it treats the commit, record, and verification artifacts as the source of truth.

### How AI was used, and what it was not allowed to do

AI coding and analysis agents were used across the workstreams to draft code, tests, probes, evidence writers, records, and packaging. Those outputs were then constrained by the project's normal controls:

- tests and full-suite runs;
- hash-bound fixtures and `SHA256SUMS`;
- independent M4 verification;
- Lead-owned gate decisions.

No AI output was allowed to write `replay.verified_by="m4"`, promote a gate, merge `main`, create a tag, or claim live success. The day includes several cases where an AI-generated claim was rejected or corrected by those controls; those are listed in section 5.

---

## 1. Executive summary

The day moved the project from "V4 exists only as a hand-run idea" to "V4 has a typed producer, a product schema, a verifier gate, and a frozen second-class sample." It did not move V4 itself to `passed`, and it did not close T8.3.

The main outcomes:

- **M1 built the typed V4 evidence path.** `V4Evidence` became the only product schema; the harness adapter cannot set M4 verification; `property_kind` is required; calibration, solver accounting, empty ranges, and persistence are covered by tests. The 124 bundle was rerun with the 128 product evidence but deliberately kept provisional.
- **M3 produced real V4 evidence and a reproducible environment.** The guest run shows candidate `unsat` / original `sat`, two identical replays, model-scope disclosure, and an empty-disjunction explanation. The environment recipe (Python 3.12.3, angr 10.0.4.post1, z3 5.1.0) passed an 18/18 self-check.
- **M4 verified the gate and refused to write the marker.** The adapter replay passed. The symbolic replay was not performed: M4's host had no angr environment, and the guest was unreachable at the time of the attempt. V4 stayed `not_run`; 124 stayed `inconclusive`.
- **The second defect class was fixed as CWE-416.** Lead record 136 unified the vocabulary: CWE-121 is the first class, CWE-416 no-input is the second, and CWE-122 is out of T8.3. T8.3 is now blocked on acceptance, not on sample selection.
- **Partial usage semantics were merged and verified.** M5's `partial` flag moved into canonical; M4 reviewed the merge at `d1ce352` and the integration line at `6d67140`/`41ff540`, and M1 corrected the test counts.
- **The T30 fixture was rebuilt from the upstream source.** The fixture now carries `original.c` and support files as bytes, with tests and intake updated.
- **M5 added an ELF `e_type` check.** A PIE artefact can no longer pass intake when the contract says non-PIE. CWE122's build recipe was also made reproducible.
- **The delivery archive was published.** `delivery/t83-2026-11-06` contains 383 files, a full `SHA256SUMS`, and the M4 guest public key. `main` was not touched.

### End-of-day status

| Item | State |
|---|---|
| 118 (T30 rebuild evidence) | **VERIFIED**, independent of 124 and T8.3 |
| 124 (CWE-416 candidate) | **inconclusive / required_check_not_run / symbolic** |
| V2 interface | producer measurement **5/5**; executor still writes `not_run` |
| V4 symbolic | **not_run** |
| `replay.verified_by="m4"` | **not written** |
| T8.3 | **BLOCKED** - blocked on M4 replay and Lead acceptance |
| CWE-122 | **out of T8.3**; build recipe fixed |
| M5 code | declared code-complete at `a63f80d`; branch frozen at `4c36898` |
| M2 console | no M2 commit landed; evidence-endpoint sample cleared |
| `main` | still `472aa94` (2026-11-03) |
| Merge / tag / live success | none |

---

## 2. Timeline of the day

| Time (+08:00) | Workstream | What moved |
|---|---|---|
| 10:33-12:34 | M3 + M1 | V4 producer evidence written through a typed writer; M1 wired `V2/V4 not_run`, typed V4 evidence, V2 scoring, and the `V4Evidence` schema. |
| 13:20-14:00 | M1 + M3 | Property-kind enforcement, 124 rerun with the 128 evidence, and the test proving the adapter cannot set M4 verification. |
| 14:36-14:49 | M1 | T30 fixture rebuilt from upstream `original.c`; support source stored as bytes; CRLF preserved. |
| 15:10-16:21 | M1 + M3 | Ordered evidence API; M3 handoff to M4; six-item merge; live-bridge fast-forward; obligation rows ordered V0..V5. |
| 16:26-17:18 | M1 + M3 + Lead | Pin and count correction; T8.3 sample frozen; CWE122 recipe fixed; ELF-type check; records 133 and 136. |
| 17:39-17:40 | M5 / delivery | 383-file curated archive, full hashing, M4 guest key published. |

---

## 3. Workstream progress

### 3.1 M1 - Host backend and acceptance plumbing

#### 3.1.1 Typed V4 evidence pipeline

The starting problem was structural: `"V4": "not_run"` was a literal in both the Route B writer and the controller-side writer, and the producer stub hardcoded the same state. A hand-run harness had no field to land in, and the acceptance engine therefore could not see a V4 result.

M1 changed that end to end:

- `3e31ee6` wired `V2/V4 not_run` through the bundle, writer, and acceptance path.
- `f57a051` required typed V4 evidence and locked V2/V4 as required obligations.
- `287aebd` made `V4Evidence` the only product schema and added a harness converter.
- `e24a569` required `property_kind` for empty V4 ranges and forced disclosure.
- `c41de41` required an explicit `property_kind` from the harness.
- `fa41102` wired typed `v4-symbolic` through bundle and persistence.
- `fdaaa7b` hardened typed V4 calibration and solver accounting.
- `3f21d31` added the regression test proving the adapter cannot write `replay.verified_by`.

Result: the product path can now carry a typed V4 result, but it still cannot promote V4 without M4's independent replay. That is the intended behavior.

#### 3.1.2 V2 interface scoring

`67b3458` scored no-input V2 from the binary pair. The producer measurement compares five `readelf` facts: target symbol present and unchanged, dynamic symbol table, `DT_NEEDED` plus dynamic flags, entry point, and no new dynamic import. All five hold for the frozen sample, so the bundle records **5/5**.

Important limit: Route B's `attempt_writer` still hardcodes `"V2": "not_run"`. An attempt assembled from the bundle therefore reports `required_check_not_run` even though the producer measured 5/5. Record 133 documents this productization gap rather than papering over it.

#### 3.1.3 124 rerun and provisional lock

`4ef3f03` reran 124 with the 128 product V4 evidence. The rerun bundle declares V4 `passed`, but the product evidence has no `replay.verified_by` marker. `73e1911` therefore kept 124 provisional, and `3f21d31` proved the adapter drops a forged marker.

End state: 124 remains **inconclusive / required_check_not_run / symbolic**. The rerun is evidence that the pipeline works, not evidence that V4 is accepted.

#### 3.1.4 Evidence API and obligation ordering

`fdc083d` added the ordered gates array and the V3 valid/invalid summary to `GET /api/attempts/{id}/evidence`. `0233d34` ordered obligation rows V0..V5 in both evidence and route summary. `7817a20` pinned the obligation evidence field contract with a real response.

M4 later used this endpoint as the M2 sample and cleared it: the top-level `gates` is a list, the V3 row is identified by `gate == "V3"`, and for `input_mode="none"` the invalid column is N/A rather than 0/0 passed.

#### 3.1.5 Partial usage integration and pin correction

`dc3bcd3` merged M5's partial aggregate semantics into canonical, and `d1ce352` merged the v3 no-input baseline on top. The semantics are:

- real rows plus a NULL sibling: sum the real rows and set `partial=True`;
- all rows real: sum and set `partial=False`;
- no real rows or no calls: `None`;
- plan fallback: `partial=False`.

M4 reviewed the canonical point and the integration line and passed the behavior. M1 then corrected the published counts:

- canonical `d1ce352`: **449 passed / 9 skipped / 0 failed**;
- integration `6d67140` and `41ff540`: **513 passed / 9 skipped / 0 failed**;
- the earlier `449 / 2 / 0` excluded e2e skips and is superseded;
- the `506 / 9 / 0` line in `MEMORY.md` was not reproducible and is withdrawn.

This was documentation-only work; no code, contract, fixture, ref, or tag changed in the correction.

#### 3.1.6 T30 fixture rebuild

`d82ac7f` rebuilt the T30 fixture from the upstream SARD `original.c` rather than a reconstructed source. `c217046` stored the source files as bytes and preserved CRLF. The fixture now carries the upstream tree, support headers, build recipe, contract, and tests; `.gitattributes` protects byte stability.

This is a fixture-provenance improvement. It does not promote a gate, and 118's VERIFIED status remains a separate rebuild evidence record.

#### 3.1.7 CWE122 ELF-type check and branch hygiene

`3a107ab` recorded the CWE122 ELF-type check. M5 implemented the actual check in `a63f80d`/`3d6ea88`: intake now reads `e_type` and rejects a `DYN` artefact when the contract says non-PIE.

M1 also mapped the branch topology: canonical `d1ce352` and later `3a107ab`; integration `7817a20`; the six-item merge is `41ff540`, and `6d67140` is a docs-only child of that merge, not a merge commit.

### 3.2 M3 - Guest execution and evidence

#### 3.2.1 V4 producer evidence

`caf122c` produced V4 evidence through a typed writer rather than hand-written JSON. `7d0665d` added `property_kind` and wrote V4 through M1's adapter only.

The guest run shows:

```text
known_good  candidate 46d16e99...  holds      eval=1 sat=0 unsat=1  11/64 steps
known_bad   original  c9c2632e...  violated   eval=1 sat=1 unsat=0  14/64 steps
replay 2 runs identical, digest cb2137a2...cb14
property_kind pointer-flow, claimed_scope model, unknown=0, timeouts=0
harness-output.json sha256 9c6eeda7...8ca8c, twice
```

The writer rejected the first two drafts because replay digests differed due to wall-clock noise. M3 fixed the producer, not the validation.

The candidate's `unsat` is the **empty-disjunction** case: the repair replaces `free@plt` with five `nop`s, so nothing is freed on that path. That is a real answer to "is a freed pointer printed here?", but it is not a deep solver proof. The record says so twice, in the case notes and in `not_claimed`.

#### 3.2.2 V4 environment and self-check

`f4c9dd3` shipped the guest interpreter as a recipe plus a self-check, not as a claim. The measured environment is:

- Ubuntu 24.04.5, kernel 6.8.0, glibc 2.39, x86-64;
- CPython 3.12.3 at `/usr/bin/python3.12`;
- `/opt/angr-venv` with angr 10.0.4.post1, archinfo/cle/pyvex 10.0.4, z3 5.1.0;
- 54 pinned packages, `pip check` clean, 650 MB.

The self-check runs 18 checks and exits 0 only when every check passes. The evidence directory has 15 files with a `SHA256SUMS` and a pin list. This is the environment M4 needs; delivering it did not itself move V4.

#### 3.2.3 M4 handoff and account

`86b6e36` handed M4 a runnable package and an account with no privilege. `42d0018` packaged the handoff with the archive hash outside the archive.

The package includes `verify_all.sh` (hash check, self-check, e2e rerun), `run_selfcheck.sh`, `run_e2e.sh`, `scripts/selfcheck.py`, inputs, and expected outputs. M4 later measured **12/12 SHA256SUMS OK**. The account is `m4verify`: password-locked, no sudo, key-only access. `guest/add-m4-key.sh` installs a public key idempotently and rejects a private key.

#### 3.2.4 T8.3 second sample

`ea5cc9e` froze the T8.3 sample: `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/`.

- class: CWE-416, mechanism `lifetime`, bug site `heap`, `input_mode: none`;
- original `c9c2632e...123c9`;
- candidate `46d16e99...fcd0`;
- contract file `8a2b408c...e3c3b`, canonical `c1684f15...b4f7c`;
- source: `dsp-testing/samate-c-cpp @ 01e353d`, `original.c fa84a6bb...7f42e`.

The package verifies itself from the shipped archive:

- outer `45/45`;
- T8.3 bundle `29/29`;
- payload `12/12`;
- host and guest runs both pass.

Gate state in the bundle: V0/V1 pass, V2 5/5, V3 1/1 with control 0/1, V4 `not_run`, V5 pass. No `verified_by` is written. T8.3 remains blocked.

#### 3.2.5 CWE122 build recipe

CWE122 is not part of T8.3, but its build recipe was fixed so a rebuild does not silently produce a PIE binary instead of the pinned non-PIE artefact.

The first rebuild differed from the pinned `c9ddb9c2...c4915`. Section comparison showed only debug-path bytes and a different build-id; the cause was `DW_AT_comp_dir` recording the build directory. The second rebuild matched in two ways:

- building in `/var/tmp/cwe122`;
- building anywhere with `-ffile-prefix-map=$PWD=/var/tmp/cwe122`.

`build.sh` gained `-fno-pie -no-pie` and the prefix map. Because the bytes did not change, `build.json#output.sha256`, both test manifests, and the pin stayed the same. Intake passes with `--baseline-cwe CWE-121`, so the sample is a distinct class.

#### 3.2.6 Guest and key state

M5's public key was installed for collaboration. M4's public key was still outstanding at 17:15. At 17:40 the M4 guest public key was published at the repository root:

```text
ssh-ed25519 ... m4-guest-replay-2026-11-06
SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q
```

The private half stayed local to M4 and was never packaged. M4's earlier guest tests timed out; after the key was published, the install and replay were still pending at the end of the day.

### 3.3 M4 - Independent verification

M4 is the same operator as the Lead. Every M4 record states the limitation: this is role-separated verification, not a two-person signature.

#### 3.3.1 V4 gate verification

M4 verified the gate behavior:

- the adapter replay passed;
- `require_independent=True` rejects a V4 claim without `replay.verified_by="m4"`;
- a forged `"verified_by": "m4"` in harness input is dropped by the adapter;
- a bundle that declares V4 `passed` is downgraded by product ingest;
- the gate tests pass.

M4 also stated the trust boundary precisely: the marker is an operator statement, not a cryptographic signature. A human could hand-edit the JSON. The defense is process, not code: M4 must cite the replay command, both digests, and the engine versions.

#### 3.3.2 124 and 118

124 remains `inconclusive / required_check_not_run / symbolic`. V2 and V4 stay `not_run` in its gate index. 118 remains **VERIFIED** as a rebuild evidence package, independent of 124 and T8.3.

#### 3.3.3 Partial usage and merge review

M4 reviewed:

- canonical `d1ce352`: partial usage code unchanged from `dc3bcd3`, behavior pass, 19 tests;
- integration `6d67140`: docs-only child of merge `41ff540`, not a merge commit;
- six-item merge `41ff540`: V4 gate, 124/120 records, CWE416 source, withdrawn verbatim experiment, byte stability, test alignment;
- canonical relationship: `6d67140` is not canonical; the merge-base is `1938c31`.

M4 also caught the stale `506/9/0` count and confirmed the local `513/9/0` result.

#### 3.3.4 Evidence endpoint sample for M2

M4 cleared the actual `/api/attempts/{id}/evidence` response as an M2 sample. The checks:

- top-level `gates` is an array;
- the V3 row has `gate == "V3"`;
- `invalid.total == 0`;
- `invalid.passed == 0`;
- `invalid_applicable == false`.

This is a shape sample, not a repair result. It tells M2 to render gates as an ordered array and to render the invalid column as N/A for `input_mode="none"`.

#### 3.3.5 Guest replay block and keypair

M4 generated an ed25519 keypair, kept the private key at mode 600, and handed only the public half to M3. The handoff package verified 12/12.

At the time of the recorded attempts, the replay could not run:

- `/opt/angr-venv` was absent on M4's host;
- `python3.12` was absent;
- `import angr` failed;
- the guest `192.168.30.128:22` timed out.

Consequently: `verify_all.sh` not run, 18/18 not checked, harness x2 not run, five criteria not checked, `replay.verified_by` not written. M4's position was that writing the marker without the run would be a false verifier statement. Later in the day M3 delivered a readable environment under `/opt/binrepair-handoff` and M5's key was installed; M4's public key was published at 17:40, but the key install and the replay itself were still pending at the end of the day.

#### 3.3.6 T8.3 wording hold

M4 initially held T8.3 because the bundle's own `gate-index.json` still listed "a second sample" under `not_done_by_M3`, while the README said no second class existed. Record 136 later unified the wording: CWE-416 is the second class, CWE-122 is out, and T8.3 is blocked on acceptance rather than selection.

### 3.4 M5 - Data contracts and AI layer

#### 3.4.1 ELF `e_type` check

`a63f80d` and `3d6ea88` added an ELF-type check to `tools/fixture_intake.py` and tests. The check reads `e_type` and rejects a `DYN` artefact when the contract's environment says non-PIE. This closes the CWE122 provenance hole at the intake layer: a PIE build can no longer pass silently.

#### 3.4.2 Partial usage merge

M5's partial aggregate semantics moved into canonical through `dc3bcd3` and `d1ce352`. M4 verified the behavior and the controller pass-through. The key point is that a NULL token count never becomes zero and never erases a sibling's real usage; it only marks the sum partial.

#### 3.4.3 T8.3 delivery archive

M5 prepared the curated archive on `delivery/t83-2026-11-06`:

- `9da1d11` adds the archive;
- `bbcac63` preserves evidence bytes and drops ignored cache files;
- `f46c626` hashes every archived file;
- `df99853` publishes the M4 guest public key at the repository root.

The archive has 383 files: docs, data, packages, patches, inputs, reference, historical, checksums, and the archive-level `README.md`/`SHA256SUMS`.

#### 3.4.4 Code-complete and frozen branch

The delivery README records M5 as code-complete on `a63f80d`, with `member-5/complete-m5` frozen at `4c36898`. "Code complete" is M5's declaration, not a gate promotion. T8.3 remains blocked.

T8.1 (assistant seam) and T8.2 (LLM planner) did not receive a new gate record today. The code-complete line is branch-level; it is not an assistant/LLM acceptance result.

### 3.5 M2 console and VMer

No M2 commit landed in this repository on 2026-11-06. The M2-facing progress was indirect:

- Lead records 126, 131, and 132 kept M2 on its assistant/LLM surface work with the approved `gates/v3` rendering shape;
- M4 cleared the evidence-endpoint sample so M2 can render the ordered gates array and the V3 N/A semantics.

No VMer commit or new staging note landed in this repository. Guest reachability remained the operational bottleneck: M4's key install and replay depended on it.

### 3.6 Lead decisions

The Lead produced four binding decisions:

- **126:** V4 is a data-model gap, not a missing engine. Hand-running a harness is rejected as evidence. The only admissible path is an independent Route B change with all six parts landed together.
- **131:** The `verified_by` gate is valid and sufficient for its purpose. The single blocker is M4's missing replay environment. Producer-only acceptance (`require_independent=False`) is not authorized.
- **132:** No marker without a replay. CWE122 stays non-PIE, and its recipe must say so. T8.3 is blocked on the environment and the CWE122 provenance issue at that point.
- **136:** CWE122 is out of T8.3; the second class is CWE-416 no-input. T8.3 is blocked on M4's V4 replay and the Lead's acceptance. No merge to `main`, no tag, no live-success claim.

### 3.7 Delivery and repository state

Six branches carried the day's work:

- `canonical/m1-m5-integration` at `3a107ab`;
- `delivery/t83-2026-11-06` at `df99853`;
- `m1/t30-acceptance-ab-2026-11-05` at `252ffb0`;
- `m5/elf-type-check` at `a63f80d`;
- `m3/cwe416-v3-noinput` at `ea5cc9e`;
- `integration/live-bridge` at `7817a20`.

`main` stayed at `472aa94` (2026-11-03). No merge, no tag.

---

## 4. Task status matrix

| Task | Owner | Progress on 2026-11-06 | Status | Evidence |
|---|---|---|---|---|
| T6.1 ingest hardening | M5 | ELF `e_type` check rejects PIE against a non-PIE contract; tests added | Increment landed | `a63f80d`, `3d6ea88`, record 132 section 3.2 |
| T6.3 / T7.1 evidence API | M1 | Ordered gates array; V3 valid/invalid summary; obligation rows V0..V5; contract pinned | Landed; M4 sample cleared | `fdc083d`, `0233d34`, `7817a20` |
| T6.2a / V4 pipeline | M1 | Typed `V4Evidence`; adapter; `property_kind`; calibration/accounting; 124 rerun | Landed; 124 still inconclusive | `3e31ee6` to `3f21d31` |
| T7.3 V4 producer | M3 | Candidate `unsat` / original `sat`; writer validation; deterministic replay | Producer delivered; V4 not_run | `caf122c`, `7d0665d`, record 127 |
| T7.3 V4 environment | M3 | Python 3.12.3 / angr 10.0.4.post1 / z3 5.1.0; 18/18 self-check; 15-file evidence | Delivered | `f4c9dd3`, record 129 |
| T8.3 guest half | M3 | CWE-416 no-input sample frozen; hashes; 45/45, 29/29, 12/12 | Blocked on V4 replay and acceptance | `ea5cc9e`, record 133 |
| T8.3 plan half | M5 / Lead | Second class fixed as CWE-416; CWE-122 out; archive published | Blocked; class-specific plan artifact still missing | Records 132, 136; delivery branch |
| T8.3 verification | M4 | Gate verified; guest replay blocked; marker not written | Blocked | M4 status docs |
| T6.7 / T7.7 verification | M4 | Partial usage pass; six-item merge; pin review; 118 verified | Reviewed / verified | M4 records |
| T8.4 console | M2 | No M2 commit; evidence-endpoint sample cleared | Dependency ready | `M4-evidence-endpoint-sample` |
| T8.5 LLM verification | M4 | No injection corpus, key-leak check, or deterministic replay yet | Not started | task table, record 87 |
| CWE-122 fixture | M3 / M5 | Recipe fixed; ELF check; intake passes; out of T8.3 | Recipe fixed; out of T8.3 | Record 136; `a63f80d` |
| T30 fixture | M1 | Upstream `original.c`; bytes and CRLF; tests updated | Fixture rebuilt; no gate change | `d82ac7f`, `c217046` |
| Delivery | M5 | 383-file archive; full `SHA256SUMS`; M4 key published | Published; no merge | `9da1d11` to `df99853` |

---

## 5. Corrections and rejected AI output

The day is not only a list of additions. Several AI-generated or AI-assisted claims were rejected by tests, hashes, or role review:

1. **V4 harness drafts rejected by the writer.** The first two producer runs differed in replay digests because wall-clock timing leaked into the digest. M3 fixed the producer; the validation was not relaxed.
2. **Test count corrected.** `449 / 2 / 0` excluded seven e2e skips; the full count is `449 / 9 / 0`. The `506 / 9 / 0` line in `MEMORY.md` could not be reproduced and was withdrawn.
3. **CWE122 PIE mismatch caught.** `build.sh` produced PIE while the committed artefact was non-PIE. The recipe was fixed with `-fno-pie -no-pie` and a prefix map; the digest matched and the pin did not move.
4. **CWE416 verbatim-source experiment withdrawn.** The six-item merge records that the verbatim `original.c` experiment was withdrawn for the CWE416 fixture; that fixture keeps the shipped source and the existing ELF/SHA256SUMS binding. The separate T30 fixture rebuild is described in section 3.1.6.
5. **T8.3 wording conflict resolved.** M4 held the sample because the bundle's gate index and README disagreed about whether a second class existed. Record 136 unified the vocabulary.
6. **No forged verifier marker.** M4 explicitly refused to write `replay.verified_by="m4"` without a run. The adapter test proves a forged marker is dropped; the remaining trust boundary is human process, not code.

---

## 6. Blockers and next actions

| Blocker | Owner | What unblocks it | Exit criterion |
|---|---|---|---|
| M4 replay not completed | M3 / M4 | Install M4's public key on the guest and use the delivered recipe/self-check (or an equivalent Python 3.12.3 + angr 10.0.4.post1 + z3 5.1.0 environment) | `verify_all.sh` 3/3; 18/18; harness x2 identical; five criteria checked |
| V2 is measured but not carried by the executor | M1 / M5 | Decide whether T8.3 is accepted at bundle level or wire V2 into the Route B writer | V2 is either explicitly bundle-level or removed from the `not_run` literal |
| "Plan differs by class" has no separate acceptance record | M5 / Lead | Produce and review a class-specific plan artifact for CWE-416 | A record that names the plan and shows it differs from the CWE-121 plan |
| M2 has no landed code today | M2 | Use the cleared evidence sample and continue the console work | M2 commits and a UI acceptance record |
| Merge and tag are gated | Lead | Close T8.3 acceptance first | No merge before T8.3; no tag; no live-success claim |

Recommended order:

1. Install M4's public key and run the replay sequence; write the marker only if all five criteria pass.
2. Decide the V2 productization question so the acceptance path is unambiguous.
3. Record the class-specific plan evidence for T8.3.
4. Let the Lead accept or reject the sample.
5. Only then decide the `main` merge and tag.

---

## 7. Evidence index

### Key commits

| Commit | Area | Message |
|---|---|---|
| `3e31ee6` | M1 V4 | wire V2/V4 `not_run` through bundle, writer and acceptance |
| `f57a051` | M1 V4 | require typed V4 evidence and lock V2/V4 required |
| `67b3458` | M1 V2 | score no-input V2 from the binary pair |
| `287aebd` | M1 V4 | make `V4Evidence` the only product schema and add harness converter |
| `c41de41` | M1 V4 | require explicit `property_kind` from the V4 harness |
| `4ef3f03` | M1 124 | rerun 124 with the 128 product V4 evidence |
| `73e1911` | M1 124 | keep 124 V4 provisional until M4 replay |
| `3f21d31` | M1 gate | prove the V4 adapter cannot set M4 verification |
| `fdc083d` | M1 API | expose ordered gates and V3 valid/invalid summary |
| `0233d34` | M1 API | order obligation rows V0..V5 |
| `7817a20` | M1 API | pin the obligation evidence field contract |
| `caf122c` | M3 V4 | produce V4 evidence through a typed writer |
| `7d0665d` | M3 V4 | emit `property_kind` and write V4 through M1's adapter |
| `f4c9dd3` | M3 env | ship the guest interpreter as a recipe plus self-check |
| `86b6e36` | M3 handoff | hand M4 a runnable package and an unprivileged account |
| `ea5cc9e` | M3 T8.3 | freeze the T8.3 sample and leave V4 `not_run` |
| `a63f80d` | M5 intake | reject PIE fixtures with an ELF `e_type` check |
| `d82ac7f` | M1 T30 | build the fixture from the upstream `original.c` |
| `c217046` | M1 T30 | store the SARD source as bytes |
| `9da1d11` | delivery | add the curated T8.3 evidence archive |
| `f46c626` | delivery | hash every archived file |
| `df99853` | delivery | publish the M4 guest public key |

### Key records

| Record | Subject |
|---|---|
| 125 | V4 stays `not_run`; what a real V4 would require |
| 126 | Lead: V4 is a data-model gap, not a missing engine |
| 127 | M3: V4 producer delivered; candidate `unsat`, original `sat` |
| 128 | M3: V4 product evidence |
| 129 | M3: rebuildable `/opt/angr-venv` and 18-check self-check |
| 131 | Lead: `verified_by` gate holds; M4 replay is the only blocker |
| 132 | Lead: no marker without a replay; CWE122 stays non-PIE |
| 133 | M3: T8.3 second sample frozen; V4 still `not_run` |
| 134 | M1: live-bridge partial audit |
| 135 | M1: pin and count correction |
| 136 | M3: M5 key install, environment delivery, CWE122 recipe, unified T8.3 wording |

### Delivery archive

`delivery/t83-2026-11-06` at `df99853`: 383 files, 4 commits, full `SHA256SUMS`, M4 guest public key at the repository root. The archive is evidence organization, not a replacement source tree.

---

## 8. Boundaries

- This report does not promote 124, V4, or T8.3. It records what was built and what remains blocked.
- No merge to `main`, no tag, and no live-success claim was made.
- The M4 verifier is the same operator as the Lead. The records disclose this; "independent" means independent provenance and a separate replay process, not a second human.
- The repository is private. Commit and branch references require repository access.
- The report is reconstructed from artifacts in this folder at 2026-11-06 21:36 +08:00. It does not include unlogged chat or external VM work.
- AI assisted the code, tests, probes, and records. Human-owned gates decided what was accepted. No AI output wrote a verifier marker or a final verdict.
