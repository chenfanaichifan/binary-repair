# 121 — CWE416 no-input fixture closed out

- Date: 2026-11-05
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput` (continues 120), cut from
  `origin/m1/t30-acceptance-ab-2026-11-05` @ `8d54a06`
- Scope: one fixture (`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/`)
  — `defect.json`, `tests/SHA256SUMS`. `contract.json` and `tests/valid.json`
  were already in the shape asked for at 120 and are verified here, not rewritten.
- Not claimed: a repair candidate, any V0–V5 pass, T8.3 relief, a live success.

## 0. Status at a glance

| Item | State |
|---|---|
| `tests/valid.json` in the fixture | **present**, 1 case (`valid-no-input`) |
| `contract.json` | `schema_version: 3`, `input_mode: "none"` |
| `invalid_*` / `max_valid_input_bytes` in the contract | **0 occurrences** (`grep -c` = 0) |
| `defect.json#trigger_case` | `null`, note now reads **`not_applicable`** |
| `tests/SHA256SUMS` | rebuilt, 13 rows / 14 files, one row moved |
| Intake, shared baseline | `OK` with `--allow-same-cwe`; plain run has one `not_a_distinct_class` against the retired directory |
| Candidate | **none produced** — a repair is Route A/B work, not the fixture author's |
| V3 | `not_run`; when a candidate exists, scored **`<k>/1`, invalid `not_applicable`** |
| V4 | `not_run`; not described as binary-level |
| T8.3 | **blocked**; no second defect class |

Two of the four asks were already true before this pass: `tests/valid.json` has
been in the fixture since `6ce16ac`, and the contract has been v3/no-input since
`0936ac6`. This record closes the other two — the `trigger_note` that still read
like a missing case, and the manifest that has to follow it — and re-measures all
four on the shared baseline rather than citing the earlier runs.

## 1. `tests/valid.json` sits in the fixture

`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/tests/valid.json`,
one case:

```
id       valid-no-input
argv     ["./original"]
stdin    null          (no literal, no artifact)
expected return_code 0, stdout 100 bytes ("A"*99 + "\n"), stderr ""
```

It is the whole test surface. `tests/invalid.json` is deliberately absent: with
`input_mode: none` there is no input to reject, so writing an invalid case would
mean inventing an input for a program that reads none.

The file was already committed at `6ce16ac` and survived the v3 move unchanged;
its hash `33be1edf…0b08` appears in both the old and new manifest.

## 2. The contract has no rejection path left

`contract.json` is `schema_version: 3` with `input_mode: "none"`. The five keys
are deleted, not blanked:

```
invalid_input_response
invalid_exit_code
invalid_stdout
invalid_stderr
max_valid_input_bytes
```

```
$ grep -c "invalid_\|max_valid" contract.json
0
SecurityContract.from_dict → schema_version=3 input_mode=none
to_dict() == file          → True
contract_sha256            → c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c
```

`invalid_exit_code: 0` is gone with the rest. Under v3 the model rejects it as an
unknown field, which was measured at 120: absence is the semantic here, and a
literal `0` would have been read as "there is a rejection path and it exits 0".

The file did not change in this pass, so `contract_sha256` is the same value 120
reported. It is re-measured in `evidence/…/09-sums-and-surface.txt` rather than
quoted from that record.

## 3. `defect.json#trigger_case` no longer implies an invalid-first selection

`trigger_case` was already `null`. What was stale was the note beside it, which
opened with "no invalid trigger case exists" — a sentence that reads as a
missing case rather than an inapplicable one, and which a reader can take as
"the invalid case is what we would have selected first".

One line changed (the diff shows each value whole; the JSON stores it as a single
line, nothing here is wrapped inside the string):

```diff
-  "trigger_note": "no invalid trigger case exists: bad() takes no arguments and the use-after-free is unconditional, so there is nothing to reject. The one valid case is the whole test surface."
+  "trigger_note": "not_applicable: input_mode is none. bad() takes no arguments, reads no stdin and opens no file, and the use-after-free is unconditional, so there is no input to reject and none to select first. The single valid case is the whole test surface; invalid is a category this sample does not have."
```

`trigger_case` stays `null` in both versions. No case id was invented to fill it,
and no `invalid.json` was created to give it something to point at.

## 4. The manifest was rebuilt, not hand-edited

```
$ diff -u 06-sums-before.txt 07-sums-after.txt
-aff4afba4b69c20285082ae103c78c725c1580820539c00a5c300e81ffc19d89  defect.json
+1016ffd6c53fc6cbb098c76c495a5c89faa9aa530ca21350e1f097574eac1c70  defect.json
```

One row. `contract.json`, `tests/valid.json`, `original.c`, `original.elf` and
the three support files keep their digests — this pass touched none of them.

There is one manifest, `tests/SHA256SUMS`, because that is the path the intake
reads (`_check_sums` opens `root/"tests"/"SHA256SUMS"`) and the layout the other
fixture uses. A second manifest at the fixture root would be an unlisted file and
would immediately raise `sums_incomplete`.

Verification in place: 13 rows, 14 files (the manifest does not hash itself).

## 5. Intake rerun on the shared baseline

The intake is `d7bfa04e…d951` = `1430e1e` = the file at M1 tip `8d54a06`; the
model is `cc976f62…fd6a` = M5 `4c36898`. Both hashed in
`evidence/…/08-intake.txt` on the machine that ran them.

```
$ python tools/fixture_intake.py --check <fixture>
error  not_a_distinct_class  defect.json#cwe  CWE-416 is already used by
       fixtures\public\CWE416_Use_After_Free__malloc_free_char_01 …
FAILED (1 error(s), 0 warning(s))                       exit 1

$ python tools/fixture_intake.py --check <fixture> --allow-same-cwe
OK                                                      exit 0
```

The single plain-run finding names the **retired synthetic directory** from
record 116 — seven required files missing, no ELF, no T8.3 identity — which still
sits beside this one claiming CWE-416. It is not a finding about this fixture's
contents. Retiring it means deleting that directory and editing
`docs/fixtures.md`; that is an M1 change and is not made here, because
112/113/116 cite its bytes.

Baseline untouched: `CWE121_src_char_declare_cpy_51b` → `OK (1 warning)`, the
warning being its own long-standing `reproduction_unverified`.

### 5.1 Earlier intake results are void

`missing_file src.c`, `missing_file tests/invalid.json`, `too_few_valid`,
`too_few_invalid` and `defect_trigger_unknown` (record 119 §4) all came from the
v2-shaped contract and the pre-baseline intake. They do not describe this
fixture and must not be cited as current. Record 120 §4's numbers were correct
for the manifest at that commit; `defect.json` has moved since, so they are
re-measured above rather than restated — the verdict is the same, and that is a
measurement, not a carry-over.

## 6. Gates

### 6.1 V3 when a candidate exists

One case, so one countable observation:

| component | denominator | state |
|---|---|---|
| valid | 1 | the only countable observation |
| invalid | n/a | **`not_applicable`** — `input_mode: none` |

V3 is scored `<k>/1` with invalid `not_applicable`. That word is chosen against
four alternatives that would each say something false:

- `0/0` reads as "two components ran and found nothing";
- `0/2` or a failure says a check was owed and missed;
- `skipped` says someone chose not to run it, when there is nothing to run;
- an absent field says the fixture forgot to declare it.

Nothing may report this fixture as `4/4` or `6/6`: those denominators count cases
that do not exist.

**Right now V3 is `not_run`, not `0/1`.** No candidate exists, so nothing has
been scored; the fixture has not failed, it has not been tried.

### 6.2 V4

`not_run`. There is no input domain — no argv parsing, no stdin read, no file
open in `bad()` or in the harness — so there is nothing for symbolic reasoning
to range over. Describing it as binary-level would name a category this fixture
does not have.

One consequence, stated once: the contract still lists `symbolic` in
`required_obligations`, while V4 cannot run. A candidate produced against this
contract will therefore be judged **inconclusive** on `REQUIRED_CHECK_NOT_RUN`.
That is the honest verdict under the current obligation set; removing `symbolic`
is a contract-owner decision, and quietly dropping it to make a green cell
appear is exactly what this record is trying not to do.

### 6.3 T8.3

**Blocked.** This is CWE-416 / lifetime, one defect class, measured again. It is
not a second class and relieves nothing. No synthetic sample is promoted to stand
in for one.

## 7. Open, and deliberately not closed here

1. **Candidate.** Not produced. Repairing `original.elf` is Route A/B work with
   its own gates; a fixture author who ships the candidate also picks the
   acceptance bar for it.
2. **The retired synthetic directory.** Still in the tree, still making the
   directory-level listing `FAILED`. Two edits would clear it: delete
   `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/`, and strike its
   row from `docs/fixtures.md`. Both belong to M1.
3. **`symbolic` in `required_obligations`.** Stays until a contract owner says
   otherwise, with the inconclusive verdict documented above as the price.
4. **Package.** Record 120's bundle carries the fixture bytes as they were at
   `0936ac6`. `defect.json` has changed since, so anyone reading that bundle
   should read its fixture as a snapshot of 120, not as the current tree. This
   record travels with its own evidence directory
   (`docs/handoffs/evidence/cwe416-noinput-close-2026-11-05/`, 11 files,
   `SHA256SUMS` 11/11).

## 8. Evidence

`docs/handoffs/evidence/cwe416-noinput-close-2026-11-05/` — 11 files:

| File | Shows |
|---|---|
| `01-contract.json`, `02-valid.json` | the contract and the one case, as they stand |
| `03`/`04`/`05` | `defect.json` before and after, and the one-line diff |
| `06`/`07` | the manifest either side of the edit |
| `08-intake.txt` | the rerun, with the code hashes that identify the intake |
| `09-sums-and-surface.txt` | 13/13 in place, 1 valid case, no `invalid.json`, contract loads |
| `10-gates.txt` | V3 `<k>/1` with invalid `not_applicable`, V4 `not_run`, T8.3 blocked |
| `README.md` | which question each file answers, and which earlier results are void |
