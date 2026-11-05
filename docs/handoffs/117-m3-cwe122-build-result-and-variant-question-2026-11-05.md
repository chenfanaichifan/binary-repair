# 117 — CWE122 fixture: built, measured, intake OK — one blocking question

**Owner:** M3 · **Date:** 2026-11-05 · **Branch:** `m3/cwe122-fixture-build`
(from `origin/integration/live-bridge-2026-11-03` @ `bcb7a30`)

**Status:** the fixture now passes intake (`OK`, 0 findings) and the six case
expectations are measured, not predicted. **One decision is outstanding** (§1):
the prescribed build command produces a PIE binary, but the contract and the
task book both require non-PIE. I pinned the non-PIE build and flagged it; if
that is the wrong call, §1.4 lists exactly what to redo.

---

## 0. Return summary

```
sha256sum original.elf
  c9ddb9c257a81d97a32e3026eacfd2e3453b41bebbaab36e53505e47421c4915   (26344 bytes)

readelf -h original.elf
  Class:     ELF64
  Type:      EXEC (Executable file)
  Machine:   Advanced Micro Devices X86-64

python tools/fixture_intake.py --check fixtures/public/CWE122_c_CWE129_fgets_01
  OK
```

---

## 1. The blocking question: PIE or non-PIE

### 1.1 Measured

The command in the task book (§Do this, step 2) is:

```sh
gcc -O0 -g -DINCLUDEMAIN -DOMITGOOD -I support src.c support/io.c -o original.elf
```

Run verbatim in the guest, it produces:

```
Class:    ELF64
Type:     DYN (Position-Independent Executable file)
Machine:  Advanced Micro Devices X86-64
sha256    d50641cb6c87e22350fc78952c70bbf295bd79d991edbd24c09fa06a3e62bb8a
size      26304
```

Root cause, measured on the same toolchain:

```
$ gcc -v 2>&1 | grep enable-default-pie
--enable-default-pie
```

Ubuntu 24.04's gcc 13.3.0 defaults to PIE. The task book's own step 3 says the
artefact should be `EXEC (non-PIE)`, so **the prescribed command cannot produce
the prescribed artefact**. This is not a build error; the two requirements are
incompatible as written.

With the two flags the sibling fixtures already use:

```sh
gcc -O0 -g -fno-pie -no-pie -DINCLUDEMAIN -DOMITGOOD -I support src.c support/io.c -o original.elf
```

```
Class:    ELF64
Type:     EXEC (Executable file)
Machine:  Advanced Micro Devices X86-64
sha256    c9ddb9c257a81d97a32e3026eacfd2e3453b41bebbaab36e53505e47421c4915
size      26344
```

### 1.2 Why this is not a cosmetic difference

`contract.json` (which I must not edit) says under `environment_assumptions`:

```
"Linux x86-64 non-PIE guest"
```

and authorises edits such as "up to 128 bytes of added x86-64 code in a
**verified-unused region of an R-X PT_LOAD**, RIP-relative references only". That
authorisation presumes fixed load addresses. In a PIE binary the load base is
randomised, so a repair written against those addresses is not well-defined.

Both sibling fixtures agree with non-PIE:
`fixtures/public/CWE416.../build.json` lists `-fno-pie`, `-no-pie` in its flags,
and the CWE121 recipe uses the same pair.

Nothing in the repo would catch the difference: `tools/fixture_intake.py`
contains **no** ELF type check (no `PIE`, `DYN` or `e_type` reference). A PIE
binary passes intake silently.

### 1.3 What I did, and the alternative

I pinned the **non-PIE** build (`c9ddb9c2…`) into `build.json#output.sha256` and
both manifests' `original_sha256`, on the grounds that the contract and both
sibling fixtures require it and only the command line is missing the flags.

This is a decision I am flagging, not one I am hiding. If the Lead wants the
literal command instead:

### 1.4 If non-PIE is rejected

1. `build.sh`: drop `-fno-pie -no-pie` (i.e. revert to the committed recipe).
2. Rebuild in the guest → `d50641cb6c87e22350fc78952c70bbf295bd79d991edbd24c09fa06a3e62bb8a`,
   26304 bytes.
3. Replace `original.elf`; set `build.json#output.sha256`, `compiler`/`flags`/`argv`
   and both manifests' `original_sha256` to that value.
4. Regenerate `tests/SHA256SUMS`, re-run intake.
5. `contract.json`'s `environment_assumptions` needs changing too, and that file
   is outside my edit scope — so this path needs a contract decision as well.

The six expected blocks do **not** change: the two variants produced identical
observations on every case (verified, §2.2).

---

## 2. What was measured

### 2.1 Build

Two independent builds of the same source in the guest produced the same hash
both times, and the same hash as the build made 15 minutes earlier before the VM
was reverted. `src.c` still hashes to the SARD pin
`082045a2dc9feb41b2feb94e8a2b15bfca4595a8a889cd4e05a19ec3e2aa46a0`.

### 2.2 Six cases, measured — not predicted

All six were run as `printf '<input>\n' | ./original.elf`. Every case exits 0,
writes 52 bytes to stdout and nothing to stderr.

| id | stdin | rc | stdout |
|---|---|---:|---|
| `valid-lowest` | `0\n` | 0 | `Calling bad()...\n` + `1` at position 0 + nine `0` + `Finished bad()\n` |
| `valid-one` | `1\n` | 0 | same, position 1 is `1` |
| `valid-middle` | `5\n` | 0 | same, position 5 is `1` |
| `valid-highest` | `9\n` | 0 | same, position 9 is `1` |
| `invalid-index-ten` | `10\n` | 0 | ten `0`, **no abort** |
| `invalid-index-hundred` | `100\n` | 0 | ten `0`, **no abort** |

Found in every `expected` block as:

```json
"expected": {"return_code": 0,
 "stdout": "Calling bad()...\n0\n1\n0\n0\n0\n0\n0\n0\n0\n0\nFinished bad()\n",
 "stderr": "", "allowed_output_files": []}
```

(that example is `valid-one`; the others differ only in which of the ten digits
is `1`, and the two invalid cases are all `0`.)

### 2.3 The invalid case does not abort — and that matters

The task book anticipated two outcomes for `invalid-index-ten`: normal exit 0, or
an abort inside `free()`. Measured: **normal exit 0**. I also probed 11, 100 and
1000 on both variants; all exit 0 with identical 52-byte output. A write 4000
bytes past a 40-byte allocation is not noticed by this glibc.

Consequence for the verification ladder: an exit-code-only check cannot
distinguish this binary from a repaired one. The defect is only visible by
comparing stdout against the contract (§2.3 of the V3 style), or by a symbolic /
memory check. Worth knowing before V3 is written for this fixture.

Two side observations, recorded because they are easy to trip over:

- `atoi` overflow: stdin `999999999999` makes `data` negative, so the existing
  `data >= 0` guard fires and the run prints
  `ERROR: Array index is negative.` (64 bytes). That path is the one the repair
  contract reuses for `index >= 10`.
- Both PIE and non-PIE variants produce byte-identical observations on all
  probes, so the variant question does not affect the expected blocks.

---

## 3. The intake short-circuit — why "0 findings after two files" was wrong

The task book says the fixture passes intake except for `original.elf` and
`tests/SHA256SUMS`. That is what a run on the committed tree reports:

```
missing_file  original.elf       required for intake
missing_file  tests/SHA256SUMS   required for intake
FAILED (2 finding(s))
```

But intake **stops at the missing artefacts**. Supply them and it continues into
schema validation, where the committed fixture had seven more findings:

```
missing_field   build.json  missing 'compiler'
missing_field   build.json  missing 'flags'
missing_field   build.json  missing 'argv'
missing_field   build.json  missing 'source'
missing_field   build.json  missing 'network'
invalid_shape   build.json#output   expected an object
too_few_valid   tests/valid.json    3 cases, need at least 4
too_few_invalid tests/invalid.json  1 cases, need at least 2
```

So adding two files could never have reached `OK`. This is a fixture-side defect
that only becomes visible once the artefacts exist; flagging it because the same
trap will hit any fixture prepared the same way.

---

## 4. Two cases added — what and why

`fixture_intake.py` requires `MIN_VALID_CASES = 4` and `MIN_INVALID_CASES = 2`.
The committed manifests had 3 and 1. That also explains "six cases" in the
request: six is intake's minimum, while the table listed four.

Added, with the rationale recorded in each entry:

| id | file | stdin | why this value |
|---|---|---|---|
| `valid-one` | `tests/valid.json` | `1\n` | completes the interior of the valid domain 0..9 alongside 0, 5, 9 |
| `invalid-index-hundred` | `tests/invalid.json` | `100\n` | a far out-of-bounds index: shows the missing guard is not an off-by-one, and that glibc stays silent even ~400 bytes past the block |

Both were measured on the built binary before being written down. If the fixture
owner wants different values, they are one rebuild away — but the two ids must
stay out-of-range for the invalid one, or the invalid/valid split stops meaning
anything.

---

## 5. `build.json` rewritten to the intake schema

The committed `build.json` described the build in prose shapes
(`inputs`, `toolchain`, `output` as a string, `status`, `reproduction`) that
intake does not read. Rewritten to the shape the checker requires, modelled on
`fixtures/public/CWE416.../build.json`:

```json
{
  "schema_version": 1,
  "compiler": {"name": "gcc", "version": "13.3.0"},
  "flags": ["-O0", "-g", "-fno-pie", "-no-pie", "-DINCLUDEMAIN", "-DOMITGOOD"],
  "argv": ["gcc", "-O0", "-g", "-fno-pie", "-no-pie", "-DINCLUDEMAIN",
           "-DOMITGOOD", "-I", "support", "-o", "original.elf",
           "src.c", "support/io.c"],
  "source": {
    "url": "sard://2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip",
    "commit": "sha256:ada9d7e1c323d283446df3f55bdee0d00bda1fed786785fe98764d58688f38eb",
    "license": "NIST SARD test suite; archive identity recorded in defect.json"
  },
  "output": {"path": "original.elf", "sha256": "c9ddb9c2…c4915"},
  "network": false
}
```

Two notes on `source`: I did **not** invent an `https://` URL for the corpus —
`sard://` plus the archive hash mirrors the `repo://` convention already used by
the CWE416 fixture. The archive identity (`ada9d7e1…`) is copied from
`defect.json`, which remains the authority for provenance.

---

## 6. `build.sh` is missing the two flags

Reported, not patched: the committed `build.sh` compiles without
`-fno-pie -no-pie`, which is why §1 happens. I left it byte-identical so the
choice in §1 stays open. Fixing it is a one-line change once §1 is decided.

---

## 7. Files changed

```
M  fixtures/public/CWE122_c_CWE129_fgets_01/build.json      schema rewrite
M  fixtures/public/CWE122_c_CWE129_fgets_01/tests/valid.json    4 cases filled
M  fixtures/public/CWE122_c_CWE129_fgets_01/tests/invalid.json  2 cases filled
A  fixtures/public/CWE122_c_CWE129_fgets_01/original.elf   26344 bytes, c9ddb9c2…c4915
A  fixtures/public/CWE122_c_CWE129_fgets_01/tests/SHA256SUMS   12 entries, two spaces, no asterisk
```

Untouched, verified by `git diff --stat` (empty) and by hash:

```
src.c            082045a2dc9feb41b2feb94e8a2b15bfca4595a8a889cd4e05a19ec3e2aa46a0  (SARD pin)
support/io.c
support/std_testcase.h
support/std_testcase_io.h
defect.json
contract.json
trigger.json
build.sh
```

`tests/SHA256SUMS` covers all 12 files (9 tracked inputs + `original.elf` +
2 manifests) and verifies clean with `sha256sum -c`. Case id, `cwe: CWE-122`
and `cwe_parent: CWE-787` are unchanged; the fixture was not renamed to CWE-787.

---

## 8. Window record

```
guest        binrepair-vm, Ubuntu 24.04.5 LTS, kernel 6.8.0-147-generic
toolchain    gcc 13.3.0 (--enable-default-pie), glibc 2.39
snapshot     uid 11 (gate4-harness baseline) — booted for this build
note         the VM had been powered off and reverted to uid 11 by another
             session mid-task; this build ran after that revert, so it is a
             baseline window, cleaner than the earlier uid 14 work
access       ssh lab@192.168.30.128, key D:\VMs\binrepair-u2404-x64-01\keys\id_ed25519
host         no gcc on the host; every compile and every run above is in-guest
```

All six inputs were transferred with `ssh cat` and hashed on both ends before the
build (`src.c`, `support/io.c`, `support/std_testcase.h`,
`support/std_testcase_io.h`, `build.sh` — all matched).

---

## 9. Not claimed

- Not Gate 6, not live success. Nothing merged to main, no tag, no push by me.
- T8.3 stays **blocked**: this returns one fixture, not an accepted second class.
  The M4 acceptance that T8.3 waits on has not happened.
- No repair candidate exists for CWE122; no V4/V5 run; `contract.json`'s
  `invalid_stdout` / `invalid_stderr` remain `null`, since they describe what a
  *repair* must produce, not what this binary does.
- The expected blocks are observations of this binary on this guest, not a
  universal contract. A different glibc could change whether the out-of-bounds
  write aborts; §2.3 records which side of that this run landed on.

---

## 10. Decisions requested

1. **§1: non-PIE (as pinned) or the literal PIE command?** If PIE, §1.4 lists the
   five steps, and `contract.json` also needs changing — outside my scope.
2. **§4: accept `valid-one` and `invalid-index-hundred`**, or substitute other
   inputs (a rebuild and a re-measure is ~2 minutes).
3. **§6: patch `build.sh`** to add `-fno-pie -no-pie`? One line, but it is the
   artefact recipe, so I would rather it be authorised than assumed.
