# cwe416-noinput-close-2026-11-05 — evidence for record 121

The CWE416 no-input fixture closed out: one valid case, a v3 contract with no
rejection path, a `trigger_case` that says `not_applicable` instead of leaving a
stale "no invalid case exists", and a manifest rebuilt over the change. Every
file here answers one question; nothing here is a result-bundle input.

| File | Answers |
|---|---|
| `01-contract.json` | What the contract says now: `schema_version: 3`, `input_mode: none`, zero `invalid_*` / `max_valid_input_bytes` keys. |
| `02-valid.json` | What the one valid case is: argv, no stdin, expected exit and stdout. |
| `03-defect-before.json`, `04-defect-after.json`, `05-defect.diff` | What changed in `defect.json`, in one line: the trigger note. `trigger_case` was already `null` and stays `null`. |
| `06-sums-before.txt`, `07-sums-after.txt` | The fixture manifest either side of the edit. Exactly one row moves, `defect.json`. |
| `08-intake.txt` | The intake rerun on the shared baseline, with the code hashes that identify which intake it was, plus the baseline fixture and the directory listing. |
| `09-sums-and-surface.txt` | The manifest verifying in place (13 rows / 14 files), the test surface (1 valid, no `invalid.json`), and the contract loading. |
| `10-gates.txt` | What V3 and V4 mean on a fixture with an empty input domain, and why `not_applicable` is not `0/0`. |

## Which intake this rerun used

`tools/fixture_intake.py` is `d7bfa04e…d951`, byte-identical to `1430e1e` — the
canonical intake on the M1 line, and the file at M1 tip `8d54a06`.
`app/domain/contracts.py` is `cc976f62…fd6a`, byte-identical to M5 `4c36898`.
Both are recorded in `08-intake.txt` from the machine that ran them, so "shared
baseline" is checkable rather than asserted.

## Which earlier results are void

Superseded, do not cite:

- record 119 §4's `missing_file src.c` and `missing_file tests/invalid.json`,
  and the probe-copy findings `too_few_valid` / `too_few_invalid` /
  `defect_trigger_unknown`. All of those came from the v2-shaped contract and
  the pre-baseline intake; the thresholds and the required-file list they were
  reading no longer describe this fixture.
- record 120 §4's intake numbers as *current* — the run was correct for the
  manifest at that commit, but `defect.json` has since moved. `08-intake.txt`
  re-measures; the verdict happens to be the same (`OK` with
  `--allow-same-cwe`), and that is a measurement, not a carry-over.

Still valid: record 120's contract analysis (§1–§3, §5). `contract.json` did not
change in this pass — `contract_sha256` is still `c1684f15…b4f7c`.

## The one finding in the plain run

`not_a_distinct_class` does not describe this fixture. It fires because
`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01` — the retired
synthetic directory from record 116, seven required files missing, no ELF, no
T8.3 identity — still sits next to it and claims CWE-416. Retiring that
directory is an M1 edit to `docs/fixtures.md` plus a deletion; it is not made
here, because 112/113/116 cite its bytes.
