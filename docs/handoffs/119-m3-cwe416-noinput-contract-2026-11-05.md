# 119 — CWE416 no-input contract: written as decided, and what still rejects it

**Owner:** M3 · **Date:** 2026-11-05 · **Branch:** `m3/cwe122-fixture-build`
(from `origin/integration/live-bridge-2026-11-03` @ `bcb7a30`)

**Status:** the upstream CWE-416 sample now has a fixture of its own with a
**no-input contract** — `input_mode: none`, **1** valid case, **0** invalid
(`N/A`), and the four input-rejection fields deliberately unwritten. The fixture
is complete and builds; **three consumers still reject the contract**, and their
exact objections are recorded below rather than worked around. No candidate is
produced, so **V3 stays `not_run`** with a hard ceiling of **1/1 no-input**;
**V4 stays `not_run`** and is not described as binary-level. **T8.3 stays
blocked.**

---

## 0. Return summary

```
fixture   fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/
build     guest, baseline window (uid 11), sh build.sh
          exit=0  sha256=c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
          size=25344   (byte-identical to T30's artefact)

contract  input_mode: none, 1 valid case, 0 invalid
          SecurityContract.from_dict -> ValueError: unknown contract fields: ['input_mode']
          without input_mode          -> ValueError: missing contract fields:
                                          ['invalid_input_response', 'invalid_stderr',
                                           'invalid_stdout', 'max_valid_input_bytes']
intake    2 findings (missing_file src.c, tests/invalid.json); probe shows the
          next three: too_few_valid, too_few_invalid, defect_trigger_unknown

gates     V3 not_run (ceiling 1/1 when a candidate exists), V4 not_run, V5 not_run
```

---

## 1. The fixture is the upstream sample, not a rewrite

`original.c` is the SARD case, byte-identical to
`dsp-testing/samate-c-cpp@01e353d`
(`fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e`). It is not
edited, not renamed, and no `INCLUDEMAIN` fix was applied — the recipe does not
define it, so the case contributes no `main` and `harness.c` supplies the only
one. `harness.c` calls `CWE416_…_bad()` and nothing else.

The support unit ships with the fixture:

| File | SHA-256 |
|---|---|
| `support/io.c` | `50ace91d…299c` |
| `support/std_testcase.h` | `a78aaf3a…b8d0` |
| `support/std_testcase_io.h` | `6459df50…fb6` |

`std_testcase_io.h` is not optional: the first build attempt failed with
`std_testcase.h:124:10: fatal error: std_testcase_io.h: No such file`. The
16-byte-short support set is a trap worth recording.

**Build, measured in the baseline guest (snapshot uid 11, `gate4-harness`):**

```
$ sh build.sh
c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9  original.elf
sha256=c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
size=25344
original.c:36:5: warning: pointer 'data' used after 'free' [-Wuse-after-free]
original.c:34:5: note: call to 'free' here
```

The fixture's `build.sh` is the T30 recipe with **one** change: `SUPPORT`
resolves to `./support` instead of a Juliet checkout. The gcc line is untouched,
so the digest is the same 25,344 bytes T30 recorded — the fixture does not fork a
second artefact for one sample. That equality was produced by building, not
assumed: this run is the evidence for it.

## 2. Why a second directory instead of rewriting the existing one

`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/` holds the retired
synthetic sample. Records 112, 113 and 116 cite its bytes, and 116 concluded it
must never be ingested. Overwriting it would make those records describe a tree
that no longer exists; leaving it and adding the upstream sample keeps one
honest history. The two are distinguished by directory and `case_id`, so a
candidate still binds to exactly one.

## 3. The contract, in full

```json
{
  "schema_version": 2,
  "input_mode": "none",
  "required_obligations": ["behaviour", "identity", "interface", "reproducibility", "structure", "symbolic"],
  "target_entry": "CWE416_Use_After_Free__malloc_free_char_01_bad",
  "target_signature": "void CWE416_Use_After_Free__malloc_free_char_01_bad(void)",
  "valid_domain": "no input: the entry point takes no arguments, reads no stdin and opens no file; every run takes the same path",
  "valid_behavior": "exit 0 and print the 100-byte block it allocated -- 99 'A' bytes then one LF -- the same 100 bytes on every run",
  "forbidden_behavior": "read a heap block after free() has released it, so stdout carries allocator residue instead of the allocated text",
  "dest_capacity_bytes": 100,
  "capacity_includes_terminator": true,
  "invalid_exit_code": 0,
  "allowed_calls": ["exit", "free", "malloc", "memset", "printLine"],
  "authorized_edits": [
    "Move the read of the block before free(), or drop the free() and accept the leak; no other behaviour may change.",
    "Allow up to 128 bytes of added x86-64 code in a gate-3-verified unused region of a loadable R-X segment; zero bytes alone are not evidence.",
    "Allow no new segment, dynamic import, GOT/PLT/relocation edit or permission broadening."
  ],
  "environment_assumptions": [
    "Linux x86-64 non-PIE guest",
    "glibc tcache writes its next/key words into the freed chunk, so the residue is observable without a sanitizer; this is an allocator behaviour, not a language guarantee",
    "the observation is taken with ASLR disabled (setarch -R) because the tcache key carries a heap address"
  ]
}
```

Three deliberate choices inside that document:

- **`invalid_exit_code: 0`** stays because the v2 model requires it, and 0 is the
  truthful value: there is no separate invalid path, so it cannot differ from the
  valid exit status. It is not a claim that an invalid path exists.
- **`dest_capacity_bytes: 100`** is the allocated block, not an input limit. It
  remains meaningful to structure and interface obligations.
- **`required_obligations` stays at six.** Dropping `symbolic` would have been the
  convenient way to make V4 disappear; that is a policy change for the contract
  owner, not a fixture author's edit. §5 states the consequence instead.

## 4. What rejects it — measured, not predicted

**The domain model, in two layers:**

```
$ python -c "SecurityContract.from_dict(json.load(open('contract.json')))"
ValueError: unknown contract fields: ['input_mode']
$ (same, with input_mode removed)
ValueError: missing contract fields: ['invalid_input_response', 'invalid_stderr',
                                     'invalid_stdout', 'max_valid_input_bytes']
```

So a consumer must change in two places, not one: accept the new field *and* stop
requiring the four. Accepting `input_mode` alone still fails.

**The intake checker, as shipped:**

```
$ python tools/fixture_intake.py --check fixtures/public/CWE416_…_noinput
missing_file  src.c                required for intake
missing_file  tests/invalid.json   required for intake
FAILED (2 finding(s))
```

`REQUIRED_FILES` short-circuits, so those two hide everything else. A throwaway
copy (not shipped) with a `src.c` duplicate and a placeholder `invalid.json`
shows the next layer:

```
too_few_valid         tests/valid.json      1 cases, need at least 4
too_few_invalid       tests/invalid.json    1 cases, need at least 2
defect_trigger_unknown defect.json#trigger_case  None is not an invalid case in tests/invalid.json
sums_incomplete       tests/SHA256SUMS      (stub-induced; the real manifest covers every file)
```

`defect.trigger_case` is `null` on purpose. The checker requires it to name an id
in `tests/invalid.json`; there is no such file and no such case, and inventing an
id to satisfy a checker is exactly the fabrication this record exists to avoid.

**One incidental finding:** `--check` on a directory whose *siblings* do not look
like fixtures raises `OSError: [WinError 1920]` from `_siblings()` instead of
reporting a finding — the probe hit it under `%TEMP%`. That is a robustness bug
in the tool, not in this fixture.

### The delta, in one place

| # | Consumer | Needs | Owner |
|---|---|---|---|
| 1 | `app/domain/contracts.py` | accept `input_mode`, and make the four invalid-path keys conditional on it | contract owner (M5/M1) |
| 2 | `tools/fixture_intake.py` | `src.c` → the case filename, or accept `original.c` | M5 |
| 3 | `tools/fixture_intake.py` | `tests/invalid.json` optional when the contract says `input_mode: none` | M5 |
| 4 | `tools/fixture_intake.py` | `MIN_VALID_CASES` / `MIN_INVALID_CASES` scoped by input mode | M5 |
| 5 | `tools/fixture_intake.py` | `trigger_case` may be null for an unconditional defect | M5 |
| 6 | `tools/fixture_intake.py` | `_siblings()` must not raise on non-fixture neighbours | M5 |

Until 1–5 land, this fixture is **correct by decision and rejected by tooling**.
That is a different state from "incomplete", and the difference matters: nothing
in the fixture is missing that the decision says should be there.

## 5. What the gates can say, and what they cannot

**V3 — behaviour — ceiling 1/1.** The sample has exactly one observation: no
arguments, no stdin, one unconditional path. Measured in the build window, five
consecutive runs under `setarch -R`:

```
exit 0, stdout 05 04 0a (3 bytes), stderr empty      5/5 identical
ASLR on: 0402010a / 45fc020a / 576d010a              3/3 different
```

A candidate can therefore earn **one** behavioural case, not four. Writing four
valid cases would mean inventing inputs for a program that reads none.

**V4 — symbolic — `not_run`, and not "binary-level".** There is no input domain
to reason over; a symbolic pass over a no-input program would be a restatement of
V1/V3, not independent evidence. It is recorded as `not_run`. Calling it
"binary-level symbolic" would be a category error dressed as coverage.

**The acceptance consequence, stated rather than hidden:** with `symbolic` still
in `required_obligations`, a `not_run` V4 makes `decide_attempt_outcome` return
`inconclusive` by design (`REQUIRED_CHECK_NOT_RUN`). That is the honest verdict
for this fixture as the contract stands — not a bug to be papered over, and not
something a fixture author should fix by editing the obligation list.

**No candidate was produced in this step.** A candidate is a repair, and repairs
belong to Route A/B; this record is fixture authoring plus measurement. So V3 is
`not_run` today, not 1/1 today: 1/1 is the ceiling that applies once someone
produces a candidate under this contract, and no lower number is available
because there is only one case to run.

## 6. Not claimed

- **No T8.3 relief.** T8.3 stays blocked. One defect class (CWE-416) with one
  observation is not a second class, and this record does not create one.
- **No V0–V5 gate is passed.** V3 not_run, V4 not_run, V5 not_run.
- **No candidate, no repair, no verdict.** Nothing here is a `binary-level`
  symbolic result or a behaviour pass.
- **No contract revision was merged.** The file is written to the decision; the
  model that must consume it still rejects it, and that is reported, not bypassed.
- **The synthetic CWE416 fixture is untouched.** Its bytes are what records
  112/113/116 describe, and 116 already retired it.
