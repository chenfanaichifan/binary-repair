# 106 — T30 build/trigger accepted with limitations; the CWE416 contract stays unloadable

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `m1/t30-acceptance-ab-2026-11-05`, from
  `origin/integration/live-bridge-2026-11-03` @ `ddd3869`
- Scope: status and decision record. No source, fixture, contract, or gate
  change. No merge to `main`, no tag, no live-success claim.
- Suite on this host: `410 passed / 2 skipped / 0 failed`
  (`--ignore=tests/e2e`; the two skips say `ELF execution requires Linux`).
- **Update (record 107, 2026-11-05):** the 118 evidence is now delivered at
  `delivery/t30-rebuild-2026-11-05/`; the package tabulates 21 fields (20 match,
  1 differs by design), not the 12/13 in the original text. The T30 status is
  unchanged, and M4 is **not** asked to upgrade. The canonical artifact path and
  the `c274893` binding are in record 107 and in the package `PROVENANCE.md`.
- **Update (records 108/109, 2026-11-05):** the Lead selected **option A**.
  M5's v3 schema (`origin/member-5/complete-m5` @ `4c36898`) is now integrated
  by cherry-pick `7c279a1`; M1 adapted the fixture intake and V3 runner in
  records 108/109. The CWE416 contract itself remains absent.

Numbering: `100`–`105` are M1's on this line; this is `106`. M3's `116`–`118`
live on other lines and are cited here, not merged or renumbered.

---

## 0. Status at a glance

| Item | Status | Basis |
|---|---|---|
| T30 **build/trigger** | **PASS WITH LIMITATIONS** | Lead ruling, recorded here; record 118 reported; M4 verified source/package identity only |
| T30 rebuild, independently re-run | **not done** | no VM access in this session; M4 did not re-run it either |
| T30 `V0`–`V5` | **not promoted** | no candidate, no loadable contract; package self-reports V1/V5 only |
| Record 116 | **DIAGNOSTIC / METHOD EVIDENCE** | synthetic source; not a T8.3 fixture |
| `original.variant.elf` | **not in the fixture, never ingested** | absent from `fixtures/public`; the variant is diagnostic only |
| CWE416 contract | **absent / unloadable** | no lawful v2 body exists for a no-input case; no `invalid_*` fabricated |
| A/B decision | **A selected (M5 v3)** | Lead decision; M1 intake adaptation in record 108 |
| `canonical/m1-m5-integration` vs `integration/live-bridge-2026-11-03` | **fork recorded, not merged** | common base `fba137e`; different commits, same CWE416 source bytes |
| T8.3 | **BLOCKED** | one class measured, no second-class gate evidence |
| `main` merged / tag created / live success claimed | **no / no / no** | ancestry and tag checks in §7 |

`PASS WITH LIMITATIONS` is a build/trigger status, not a gate result. It does
not turn any of `V0`–`V5` into `pass`, and it does not relieve T8.3.

---

## 1. What is accepted, and what “with limitations” means

The accepted claim is narrow:

> In the baseline-clean `gate4-harness` window (snapshot uid 11), `sh build.sh`
> on the T30 inputs produced `c9c2632e…23c9`, 25,344 bytes, byte-identical to
> `docs/handoffs/evidence/T30/build/original.elf` at commit `c274893`;
> `./trigger.sh` under `setarch -R` produced one deterministic observation,
> `exit 0`, `stdout 05040a`, 3 bytes. This is recorded as
> **PASS WITH LIMITATIONS**.

Twenty of the twenty-one compared `build.json` fields match the rebuild; the
twenty-first is `window.is_baseline`, and it differs because the rebuild is the
baseline run while `build.json` records the earlier non-baseline window. That
difference is the point of record 118, not a mismatch to paper over. (The first
version of this record said 12/13; the 118 package later expanded its table to
21 fields. Record 107 carries the correction.)

### 1.1 What M4 did verify

M4 verified source and package identity on the delivered bytes:

- `original.c` SHA-256 `fa84a6bb…7f42e` equals the pinned upstream file
  `dsp-testing/samate-c-cpp@01e353d`, path
  `C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c`,
  3,198 bytes.
- `INCLUDEMAIN` is present at `original.c:91`; the gcc line does not define it;
  the harness supplies the only `main`.
- The T30 package `SHA256SUMS` re-hashes 12/12 OK in this workspace, and
  `original.elf` is `c9c2632e…23c9`, 25,344 bytes.

M1 re-ran those package checks here; they are recorded in
`t30-package.txt` in the delivery directory.

### 1.2 What is not verified

| Limitation | Consequence |
|---|---|
| M4 did not rebuild and did not run the trigger | the rebuild is accepted **as reported**, not independently reproduced |
| ~~The record 118 evidence package is absent~~ — **resolved by record 107** | the 11 files are now at `delivery/t30-rebuild-2026-11-05/`; the top-level zip and both manifests re-hash there. The original absence was the limitation; it is no longer one |
| The guest is not available in this session | no M1 re-run of `build.sh` or `trigger.sh` |
| Scope is gcc 13.3.0 / glibc 2.39 / this guest image | no claim about another compiler, libc, or distribution |
| The trigger is deterministic only under `setarch -R` | with ASLR on, 10 runs produced 10 distinct `stdout` values; `05040a` is the no-ASLR observation, not a universal one |
| `V1`/`V5` are package self-reports | M4 did not promote them; they remain fixture-scoped |
| The T30 ZIP is flat while `README.txt` names `build/…` paths | a rebuild must reconcile the layout before using the documented paths |

What remains to lift the other limitations: have M3/VMer re-run the build and
trigger in a clean window with M4 or another verifier observing. The evidence
delivery half is done in record 107. M1 does **not** ask M4 to upgrade record
118; M4 may verify on its own record now that the bytes are readable. Until
then, the acceptance stands exactly as written: **build/trigger only, with the
gaps named**.

### 1.3 Why accept it anyway

The Lead needs the T30 fixture's build state fixed before deciding what to do
about the CWE416 contract. Keeping the build “unaccepted” would block that
decision on evidence that is already sufficient for the narrow claim — the
bytes, the source identity, and the deterministic trigger — while the missing
package is a delivery/integrity gap, not a contradictory measurement. The
limitations are recorded so the acceptance cannot be quoted later as a V0–V5
pass or as M4 verification.

---

## 2. Record 116 stays a synthetic diagnostic

Record 116 measured a **team-authored** `src.c` plus `harness.c`, not the
upstream case. Its committed recipe did not link: `main` was defined in both
`src.c:90` and `harness.c:20`. The minimal variant it built (`src.c` alone) is
a **variant**, not the fixture artefact: it drops `harness.c` and adds
prefix-map flags, so it differs from `build.json#argv` in two ways.

Disposition, unchanged from record 118 §7:

- Record 116 is **diagnostic / method evidence** — reset-vs-resume proof, the
  linker failure, digest portability, 150-run trigger stability, ASan.
- `original.variant.elf` is **not** part of a fixture. It is not tracked under
  `fixtures/public` here (`git ls-files` shows no `variant` path), it is not
  referenced by any `build.json#output.sha256`, and it must never be ingested.
- The synthetic fixture's `output.sha256` stays `null`. Filling it with the
  variant digest would bind a recipe that was never run.
- Nothing in 116 relieves T8.3, and nothing in 116 is T30 evidence.
- 116 §8's **Fix A** (drop `harness.c`) and **Fix B** (remove `main` from the
  synthetic `src.c`) are fixture-authoring fixes for the retired synthetic
  sample. They are **not** the no-input contract A/B in §4, not a T8.3 decision,
  and not a T30 source change. Record 107 §5 states the separation.

The root cause of the link failure is resolved by record 118 §1: the upstream
case guards its `main` with `#ifdef INCLUDEMAIN` and the T30 gcc line does not
define it, while the synthetic file's `main` was unguarded. That is an authoring
defect in the synthetic fixture, not a toolchain or window defect.

---

## 3. The CWE416 contract is absent, not guessed

### 3.1 Measured state

`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/` contains exactly
three tracked files:

```
PROVENANCE.md
defect.json
src.c
```

`contract.json`, `build.json`, `build.sh`, `original.elf`, `tests/valid.json`,
`tests/invalid.json` and `tests/SHA256SUMS` are all absent.
`python tools/fixture_intake.py --check …` returns:

```
FAILED (7 error(s), 0 warning(s))
missing_file: original.elf, build.sh, build.json, contract.json,
              tests/valid.json, tests/invalid.json, tests/SHA256SUMS
exit 1
```

That is the true state, not a regression.

### 3.2 Why no v2 contract can be written lawfully

`SecurityContract` v2 requires 17 keys and forbids unknown ones. Four of them
describe an **input-rejection path**:

```
invalid_input_response
invalid_exit_code
invalid_stdout
invalid_stderr
```

The T30 program takes no input. `bad()` is called with no arguments and the
use-after-free is unconditional; there is no input to reject. Measured:

| Probe | Result |
|---|---|
| add `input_mode: "none"` | `ValueError: unknown contract fields: ['input_mode']` |
| omit the four rejection fields | `ValueError: missing contract fields: ['invalid_exit_code', 'invalid_input_response', 'invalid_stderr', 'invalid_stdout']` |
| fill them with sentinels (`"not applicable…"`, `0`, `""`, `""`) | **loads**, and produces a contract hash |

The third row is the failure mode, not a solution. It makes the loader green by
inventing a rejection path the program does not have; the contract hash then
binds that invention. `invalid_input_response = "not applicable…"` is prose, not
a behavior; `invalid_exit_code = 0` and empty stdout/stderr are values chosen to
satisfy the schema, not measured facts. That is exactly the fabrication this
record refuses.

Therefore **no `contract.json` is written**, and the CWE416 contract remains
unloadable until the Lead decides A or B. “Unloadable” here is deliberate: the
absence is the honest representation of a no-input case under a schema that
only knows input cases.

### 3.3 A second inconsistency to carry into the decision

`defect.json` still says:

```json
"trigger_case": "invalid-first"
```

That is a CWE121-shaped pointer. `tools/fixture_intake.py` requires
`trigger_case` to name a case in `tests/invalid.json`; CWE416 has no such file.
Adding one would be the same fabrication in a different field. The pointer is
left unchanged here because the A/B decision determines whether it becomes
optional (A) or is replaced by a real invalid case (B). It is not evidence of a
CWE416 invalid path.

---

## 4. The A/B decision — A selected

**Update:** the Lead selected **option A** on 2026-11-05. M5's v3 schema is at
`origin/member-5/complete-m5` @ `4c36898`; M1's intake/test adaptation is record
108. The decision context below is kept for the record. The schema is not merged
into this branch yet, so the CWE416 contract is still absent here.

### 4.1 Option A — extend `SecurityContract` with `input_mode=none`

**What it means.** Add an explicit input-mode discriminator. For
`input_mode = "none"`:

- the program is invoked with no argv and no stdin;
- `valid_domain` is `no program input`;
- `valid_behavior` is the exact post-repair process outcome (exit code,
  stdout bytes, stderr bytes);
- `forbidden_behavior` is the defect property (for T30: read or write through a
  pointer after its object is freed);
- the four `invalid_*` fields are **absent and prohibited**, not set to
  sentinel values. “Invalid” is not applicable; the contract says so
  structurally, not in prose;
- `max_valid_input_bytes` is **absent** too; M5 v3 treats it as invalid-only, like the four rejection fields;
- the V3 behaviour set is **one no-input case, zero invalid cases**; there is no
  six-case matrix to claim.

A mode-aware representation is needed so absence cannot be confused with a
malformed input contract. The clean form is a tagged union
(`input_mode` + a mode-specific rejection object), not four optional strings.

**No-input valid/invalid semantics, stated explicitly.** For
`input_mode = "none"`:

- the **valid** set is exactly one case: no argv beyond `argv[0]`, no stdin;
  the expected exit code, stdout bytes and stderr bytes are frozen in the
  contract and the case manifest;
- the **invalid** set is **not applicable**, not empty-with-invented-cases.
  There is no input that can be rejected, so no `invalid_*` behavior may be
  defined. An invocation with unexpected argv or stdin is outside the
  contract's domain; it is not a tested invalid case and must not be counted as
  one;
- a validator must reject a no-input body that carries any `invalid_*` key or a
  non-null rejection object. Absence is the semantic, so it has to be validated
  as absence rather than tolerated as “empty”;
- V3 evidence for this mode is `1/1 no-input`, never `6/6` or `4+2`. The result
  bundle and the export must carry the mode so a reader cannot mistake it for
  the input-case matrix.

Shape sketch only — **not a fixture contract, not written anywhere**:
`input_mode: "none"`, an `input_rejection: null` member, and no `invalid_*`
keys. The exact `valid_behavior` bytes for T30 are the contract owner's to freeze
before a candidate is built; this record does not invent them.

**Measured touch points.**

| Area | What changes | Why |
|---|---|---|
| `app/domain/contracts.py` | `_REQUIRED_KEYS`, dataclass fields, validation, `to_dict`, `canonical_payload` | the discriminator and the conditional rejection block must be hashed |
| contract hash | every v2 contract's canonical payload gains a field, or a new schema version is introduced | adding `input_mode` to the payload changes `sha256()`; CWE121's reviewed hash must be re-reviewed |
| `tools/fixture_intake.py` | `REQUIRED_FILES`, `MIN_VALID_CASES=4`, `MIN_INVALID_CASES=2`, `trigger_case` check | a no-input fixture cannot have 2 invalid cases or an `invalid-first` pointer |
| `app/services/jobs.py`, `tests/integration/test_controller_api.py` | seed/default contract bodies | they currently supply 17-key v2 bodies; a v3 discriminator must either be optional-with-default or migrated |
| `tests/test_contracts.py`, `tests/test_fixture_intake.py`, `tests/test_fixture_contract.py`, `tests/test_fixture_v3_manifest.py` | new mode cases; the existing 4+2 assertions stay for input modes | none of these tests covers a no-input contract today |
| V3 bridge/result-bundle evidence | mode-dependent case count (1+0) | a no-input run must not be presented as 4 valid + 2 invalid |

**Cost / risk.**

- It is a contract revision, not a one-line addition. The canonical hash and
  every stored `reviewed_scope_sha256` are affected unless the new field is
  versioned or conditionally excluded from the hash.
- It weakens the V3 behaviour matrix from six cases to one. The loss must be
  compensated explicitly: exact stdout/exit bytes, a lifetime obligation that
  is actually checked, V5 reproducibility, and an explicit statement that the
  one case is one case.
- Behaviour alone does not prove the absence of a use-after-free. A candidate
  could print the expected 100 bytes through a different path while still
  reading freed memory elsewhere. The `forbidden_behavior` text is not a
  mechanical check; the lifetime obligation needs static/dynamic evidence (ASan
  is a diagnostic, not the artefact).
- It keeps T30, whose source and build are already accepted, as the CWE416
  sample. No new guest build is needed for the source half.

**Benefit.** It preserves the verified public CWE416 case and avoids a new
corpus, new build recipe, and new guest window. The cost is in the schema and
the evidence standard, not in the sample.

### 4.2 Option B — reselect a public CWE416 case that takes input

**Measured obstacle.** The pinned Juliet CWE416 directory at
`dsp-testing/samate-c-cpp@01e353d` contains **150 `.c` files and 372 `.cpp`
files** (522 source files). Of the `.c` files, 138 declare
`int main(int argc, char * argv[])`. **No individual case source** references
`argv[n]` or reads input through
`scanf/fgets/getchar/fread/read/getenv/atoi/strtol/std::cin/istream/getline`.
The only non-declaration `argc`/`argv` uses are in the aggregator drivers
`main.cpp` and `main_linux.cpp`, which assign them to globals and do not parse
input. The family is no-input by construction; T30 is not an exception, it is
typical.

So B cannot be satisfied by picking a different file from the same corpus.
It requires a different public corpus or a public CVE/PoC sample with a real
input path. That means:

- a new provenance pin (repo, commit, path, SHA-256, size);
- a new build recipe and a guest build;
- a new contract with a real 4 valid + 2 invalid matrix;
- a new candidate and a full V0–V5 ladder;
- M4 verification of the new sample.

**B’s four-tuple cannot be given yet.** Giving one now would mean naming a
sample M1 has not pinned, built, or measured. The only four-tuple in this
record is T30's, and it is not a B tuple: `dsp-testing/samate-c-cpp@01e353d`,
`C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c`,
`fa84a6bb…7f42e`, 3,198 bytes.

**Cost / risk.** B is a restart of the sample/build/contract/candidate chain.
It preserves the schema and the 4+2 matrix, and it gives input-dependent
behaviour evidence, but it does not by itself prove the lifetime property
either. The main risk is finding a public sample that is small enough to build,
licensed, and still a genuine CWE416 with a controllable input path.

### 4.3 Comparison

| Question | A: `input_mode=none` | B: input-bearing case |
|---|---|---|
| Keeps T30 source/build acceptance | yes | no; new sample, new build |
| Changes `SecurityContract` | yes — new mode, hash/schema impact | no |
| Changes intake / V3 matrix | yes — 1 valid + 0 invalid | no — stays 4 + 2 |
| Behaviour evidence strength | thinner (one observation) | stronger (input-dependent) |
| Proves lifetime safety by itself | no | no |
| New guest build needed | no for T30 source | yes |
| Can be satisfied inside the pinned Juliet CWE416 corpus | yes (T30) | **no** — 522/522 C and C++ files have no input read |
| Main cost | schema revision + evidence standard | new corpus + full rebuild + full ladder |

### 4.4 M1's non-binding recommendation

**A, implemented as a real schema revision, not as sentinel values.** The
decisive measurement is that the pinned corpus has no input-bearing CWE416
case; B is therefore a corpus change and a full restart, not a reselection.
A keeps the one public CWE416 sample whose source and build are already
accepted, and the schema can say “no input” honestly.

That recommendation has two conditions, and they are not optional:

1. The A change is owned by the contract owner (M5) and approved by the Lead;
   M1 does not edit `SecurityContract` unilaterally. M1’s part is the fixture
   intake, the no-input test shape, and the integration-side consumption.
2. The no-input contract must carry an explicit lifetime obligation and a
   deliberately reduced V3 claim (1 case, not 6). It must not be sold as a
   six-case pass.

If the Lead requires the 4+2 behaviour matrix to stay intact, B is the only
route, and the Lead must name the corpus before M1 pins a tuple. M1 will not
invent a B tuple from the Juliet corpus.

---

## 5. The `canonical` / `live-bridge` fork

Two M1 lines share the base `fba137e` and have not been merged:

| Ref | Head | Commits since `fba137e` |
|---|---|---|
| `origin/canonical/m1-m5-integration` | `1938c31` | `ba65aed` (V0 content binding + CWE416 pin), `1938c31` (mirror URL) |
| `origin/integration/live-bridge-2026-11-03` | `ddd3869` | `3b8a81e`, `af01baf` (M5, merged at `c0c0580`), `c0c0580`, `de4c63d`, `4292da0`, `ddd3869` |

### 5.1 What actually diverges

- **CWE416 `src.c` is identical on both refs**:
  `262dee1d39243c944a55b4b967ab6a56524977dc88a684ff0b7150cacf0b5a61`
  (LF-normalised; the served upstream CRLF file is `fa84a6bb…7f42e`).
- **`PROVENANCE.md` differs, and only one side is right.** Canonical records
  `dsp-testing/samate-c-cpp@01e353d` and the verified `fa84a6bb…` hash.
  Live-bridge still records the `arichardson/juliet-test-suite-c` mirror at
  `f88433e…` and says the Lead's `01e353d` “does not resolve in this mirror”.
  The second statement is true of the arichardson mirror, not of the pinned
  source. Canonical is authoritative for T30 because it matches M4's verified
  four-tuple.
- **`tools/route_bundle_ingest.py` differs only in structure.** Canonical moves
  the V0 branch into an `if/else`; both implementations bind V0 by content and
  reject a missing candidate. `tests/integration/test_route_bundle_ingest.py`
  passes 14/14 on both refs.
- **Live-bridge carries work canonical does not**: the M5 `af01baf` merge and
  its rejected narrower aggregate, the result-bundle test isolation, record 105,
  and the ignore rules. Canonical carries the corrected CWE416 provenance and
  the V0 comment/refactor. Neither is a superset.

### 5.2 What this record does about it

- **Nothing is merged, rebased, or cherry-picked.** The fork is recorded so a
  later merge does not silently take the stale live-bridge provenance or drop
  the M5/record-105 work.
- T30 acceptance binds to the **canonical** four-tuple, not to live-bridge's
  mirror text. The identical `src.c` bytes mean this is a provenance/document
  correction, not a source change.
- If the branches are reconciled later, the merge should take canonical's
  `PROVENANCE.md` and keep live-bridge's M5/record-105 commits. That is a separate
  decision and is not performed here.
- The live-bridge provenance text is left unchanged. Editing it would change a
  fixture file in a status record and would not resolve which branch is
  canonical. The defect is recorded, not hidden.

---

## 6. CWE122 is not an input to this record

Record 118's branch is named `m3/cwe122-fixture-build`, but its content is
CWE416/T30. The name is a label collision, not evidence that CWE122 and CWE416
are interchangeable.

- CWE122 is a separate case and recipe. Its build defines
  `-DINCLUDEMAIN -DOMITGOOD` because the case's own `main` is the intended
  entry point and there is no harness. T30's build does **not** define
  `INCLUDEMAIN` because `harness.c` supplies the entry point and the case's
  `main` must be excluded. Applying one recipe to the other breaks it.
- No CWE122 build, trigger, contract, or test result is used here as CWE416
  evidence. No CWE416 result is offered as CWE122 evidence.
- T30 is CWE416. The CWE122 line stays on its own record and is not promoted by
  this acceptance.

---

## 7. T8.3 and the constraints held

**T8.3 remains blocked.** What exists is one public CWE416 sample (T30) whose
source and build/trigger are accepted with limitations. What does not exist:

- a loadable CWE416 contract;
- frozen valid/invalid tests for it;
- a repair candidate;
- V0–V5 evidence;
- M4 verification of a candidate.

A second defect class needs the full chain, not just a second source file. The
T30 acceptance is one class measured once, not a second-class gate pass.

Constraints held in this record:

- no merge to `main` (neither `1938c31` nor `ddd3869` is an ancestor of `main`);
- no tag (0 tags point at either head);
- no live-success claim;
- no candidate and no V0–V5 promotion;
- no fixture byte changed;
- no `contract.json` written;
- no `original.variant.elf` added.

Suite on this host, for the record:

```
pytest --ignore=tests/e2e -o addopts=""
410 passed, 2 skipped, 1 warning in 7.76s
```

The two skips are `tests/test_fixture_v3_manifest.py:141` and `:163`,
both `ELF execution requires Linux`. A skip is not a pass.

---

## 8. Evidence in the delivery directory

| File | Content |
|---|---|
| `t30-package.txt` | T30 package `SHA256SUMS` 12/12 and field-by-field checks against `build.json` / `readelf.txt` |
| `cwe416-fixture.txt` | tracked fixture files, intake 7 errors, absence of contract/build/tests, `defect.json` |
| `contract-probe.txt` | `input_mode` rejected, omitted rejection fields rejected, sentinel-filled body loads (the forbidden path) |
| `fork.txt` | refs, merge base, per-side commits, diffstat, `src.c` hash on both refs, provenance lines, ingest diff |
| `cwe416-corpus.txt` | 150 `.c` + 372 `.cpp` CWE416 files, 0 case sources reading input |
| `constraints.txt` | main ancestry, tags, worktree state |
| `suite.txt` | full and targeted suite results |
| `118-evidence-absence.txt` | historical note: where the package was absent when 106 was written (superseded by record 107) |

The delivery `SHA256SUMS` covers every file in that directory except itself.

---

## 9. Not claimed

- **Not** a V0–V5 pass; **not** a verified rebuild; **not** an M4 signature on
  the rebuild.
- **Not** a T8.3 fixture or T8.3 credit. Record 116 is not one either.
- **Not** a claim that the CWE416 contract is valid or that a no-input contract
  has been approved. It is absent by design.
- **Not** a claim that CWE122 and CWE416 are interchangeable.
- **Not** a claim about another compiler, libc, or guest image.
- **Not** a merge, tag, or live success.

## 10. Open items

1. **A selected:** no further Lead choice on the route. If B had been chosen,
   the corpus would have been named here.
2. **Contract owner (M5):** land the v3 schema on the integration line; M1 has
   already adapted the intake/tests in record 108.
3. **M4:** the 118 evidence is delivered at
   `delivery/t30-rebuild-2026-11-05/`; M4 may re-hash and verify on its own
   record. A clean-window re-run remains the remaining verification if M4
   chooses it. M1 does not ask for an upgrade.
4. **M1/M5:** reconcile the two provenance texts when the fork is merged; do
   not take live-bridge's stale mirror text over canonical's verified pin.
