# M3 build request: CWE-122 fixture ELF

- Date: 2026-11-05
- From: M1 (host backend)
- Needs: a Linux x86-64 builder (M3)
- Blocks: second defect class in T8.3; T8.3 stays blocked until this returns

## What exists

`fixtures/public/CWE122_c_CWE129_fgets_01/` is committed and passes intake except
for the two artefacts only a Linux build can produce:

```
missing_file  original.elf       required for intake
missing_file  tests/SHA256SUMS   required for intake
```

Everything else is final: `src.c` (verbatim SARD), `support/` (verbatim Juliet
`testcasesupport`), `build.sh`, `build.json`, `defect.json`, `contract.json`,
`trigger.json`, and the `tests/*.json` skeletons.

Provenance is pinned so it can be re-checked:

```
corpus            NIST SARD Test Suite 112 (Juliet C/C++ v1.3)
archive           2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip
archive sha256    ada9d7e1c323d283446df3f55bdee0d00bda1fed786785fe98764d58688f38eb
case path         C/testcases/CWE122_Heap_Based_Buffer_Overflow/s06/
                  CWE122_Heap_Based_Buffer_Overflow__c_CWE129_fgets_01.c
case sha256       082045a2dc9feb41b2feb94e8a2b15bfca4595a8a889cd4e05a19ec3e2aa46a0
```

`src.c` must not be edited. If its hash changes, the fixture no longer matches
SARD and the pin is void.

## Do this

1. Copy the fixture directory to a Linux x86-64 machine with `gcc`.

2. Build:

   ```sh
   cd fixtures/public/CWE122_c_CWE129_fgets_01
   ./build.sh
   ```

   `build.sh` runs:

   ```sh
   gcc -O0 -g -DINCLUDEMAIN -DOMITGOOD -I support src.c support/io.c -o original.elf
   ```

   `-DINCLUDEMAIN` uses Juliet's own `main()`; `-DOMITGOOD` drops `good1()` so the
   binary runs only `bad()`. Do not add `-fstack-protector`, `-D_FORTIFY_SOURCE`
   or sanitizers: the fixture must reproduce the plain build.

3. Confirm it is the expected artefact:

   ```sh
   readelf -h original.elf | grep -E 'Class|Machine|Type'
   # ELF64, Advanced Micro Devices X86-64, EXEC (non-PIE)
   sha256sum original.elf
   ```

4. Measure the six cases and **write what actually happened**. Do not predict.

   | file | id | stdin |
   |---|---|---|
   | `tests/valid.json` | `valid-lowest` | `0\n` |
   | `tests/valid.json` | `valid-middle` | `5\n` |
   | `tests/valid.json` | `valid-highest` | `9\n` |
   | `tests/invalid.json` | `invalid-index-ten` | `10\n` |

   For each: run `printf '0\n' | ./original.elf`, record `return_code`,
   `stdout` (exact bytes, including the `Calling bad()` / `Finished bad()`
   lines Juliet's main prints) and `stderr`.

   Then replace `"expected": null` with:

   ```json
   "expected": {"return_code": 0, "stdout": "...", "stderr": "", "allowed_output_files": []}
   ```

   The invalid case matters most: `buffer[10]` writes into the malloc chunk
   header, so the process may print normally and exit 0, or abort inside
   `free()`. Both are acceptable findings; record whichever happened. If it
   aborts, put the signal in `return_code` as e.g. `-6` and keep stderr empty
   unless glibc wrote something.

5. Set the ELF identity in both manifests:

   ```json
   "original_sha256": "<sha256sum original.elf>"
   ```

   and drop `"measured_by": "M3 (pending build)"`.

6. Generate the sums **last**, after `original.elf` and both JSON files are final:

   ```sh
   cd fixtures/public/CWE122_c_CWE129_fgets_01
   find . -type f ! -name SHA256SUMS | sed 's|^\./||' | sort | xargs sha256sum > tests/SHA256SUMS
   ```

   `tests/SHA256SUMS` must cover `original.elf`, `src.c`, `build.sh`,
   `build.json`, `defect.json`, `contract.json`, `trigger.json`, both files in
   `support/`, and both files in `tests/`.

7. Verify and return the output:

   ```sh
   python tools/fixture_intake.py --check fixtures/public/CWE122_c_CWE129_fgets_01
   # expected: OK  (0 findings)
   ```

   Send back: the `sha256sum original.elf`, the `readelf -h` three lines, the six
   measured `expected` blocks, and the intake output.

## Rules

- Do not edit `src.c`, `support/*`, `defect.json`, `contract.json` or
  `trigger.json`. If something there is wrong, report it; do not patch it here.
- Do not relabel the case as CWE-787. `defect.json` already records
  `cwe: CWE-122`, `cwe_parent: CWE-787`; SARD 112 predates the 787 numbering and
  the fixture must stay byte-identical to what the corpus ships.
- Do not commit to `main`, do not tag, do not claim live success. T8.3 stays
  blocked until M4 verifies.
- If `gcc` is unavailable or the build differs from the flags above, stop and
  report rather than substituting a compiler.
