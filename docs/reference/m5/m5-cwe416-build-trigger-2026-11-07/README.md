# M5 CWE-416 build/trigger log bundle

Source: M3's guest window record 116, copied here as immutable evidence for the
M5 handoff. No file below was re-executed on the M5 host.

## Observation

The defect is a heap use-after-free: the target frees a 50-byte block and then
reads it through `printLine`. The observed invalid path prints 49 `X` bytes
followed by LF, while the correct output is the original allocated text.

Key evidence:

```text
05-matrix.txt:
  valid cases 4/6 MATCH
  invalid cases 2 DIFF, expected on the unrepaired original

06-stability.txt:
  50/50 identical stdout digests for the --uaf path

07-asan.txt:
  AddressSanitizer: heap-use-after-free
  freed by badSink ... free
  read by printLine ... fputs
```

## Reproduce

From the M3 guest:

```bash
gcc -fsanitize=address -g -O0 -o asan.elf src.c
./asan.elf use-after-free --uaf
```

The exact command and environment are in `01-isolation.txt` and
`03-recipes-and-digests.txt`.

## Scope and limitations

```text
This is a diagnostic CWE-416 build/trigger record, not the formal T8.3 fixture.
The formal T8.3 fixture is the no-input CWE-416 sample in records 120/133.
No V0-V5 gate is asserted here.
No verified_by is written here.
```

The log is included to satisfy "reproducible use-after-free observation" evidence;
it does not replace the formal fixture's build/contract/tests.
