# 118 — T30 rebuilt in a baseline window: same bytes, and the INCLUDEMAIN answer

**Owner:** M3 · **Date:** 2026-11-05 · **Branch:** `m3/cwe122-fixture-build`
(from `origin/integration/live-bridge-2026-11-03` @ `bcb7a30`)

**Status:** the upstream CWE-416 case was rebuilt in a **baseline-clean window**
(snapshot uid 11, `gate4-harness`) and reproduces
`c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9` — byte-identical
to the artefact T30 already carries. Twenty of the twenty-one compared
`build.json` fields match exactly; the twenty-first is the window, which is the
point of this run. (§6 tabulates the twenty-one and says why the prose fields are
read rather than tabulated.)

Record 116 stays as a build/trigger diagnostic for the synthetic fixture and is
**not** a T8.3 fixture. §7 restates that and closes it.

**One caveat about paths.** `docs/handoffs/evidence/T30/` is not in this branch's
tree. This branch was cut from `origin/integration/live-bridge-2026-11-03` at
`bcb7a30`; T30 landed afterwards on `member-3/t62-host-safe` at `c274893`, which
is not an ancestor here. Every `T30/...` reference below therefore names that
commit. The central claim is still checkable without checking it out:
`git cat-file -p c274893:docs/handoffs/evidence/T30/build/original.elf | sha256sum`
gives the same digest, and `git cat-file -s` the same 25,344 bytes. Whether T30
should be carried onto this line is a delivery decision and is not made here.

---

## 0. Return summary

```
cd /var/tmp/cwe416 && sh build.sh
  exit=0
  sha256=c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
  size=25344

readelf -h original.elf
  Class:  ELF64          Type: EXEC (non-PIE)      Entry: 0x4011b0

./trigger.sh               ./original.elf    1 run    exit_code=0 stdout_hex=05040a stdout_len=3 stderr_len=0
./trigger.sh --repeat 50   ./original.elf    50 runs  same observation, 50/50
./trigger.sh --repeat 200  ./original.elf    200 runs same observation, 200/200
  251 runs in total (1 + 50 + 200), one distinct observation
```

The three invocations are listed separately because the count claim is 251, not
50: an earlier version of this summary showed only the `--repeat 50` line, which
read as if the total were 50 while `07-rebuild.json#trigger.runs_total` and §5
both say 251. `04-trigger.txt` §1–§3 is the primary record.

Evidence: `docs/handoffs/evidence/t30-rebuild-2026-11-05/` (11 files,
`SHA256SUMS` 10/10 verified after export; the guest-side `06-SHA256SUMS` covers
`01`–`05` and is unchanged). The same 11 files travel as
`dist/M3-t30-rebuild-evidence-2026-11-05.zip` with a top-level digest in
`dist/M3-t30-rebuild-evidence-2026-11-05.zip.sha256`, so the record can be read
without this branch.

---

## 1. The question asked: INCLUDEMAIN and the actual gcc line

The answer is that the upstream case and the T30 recipe are consistent, and the
link failure in record 116 belongs to the synthetic fixture rather than to the
toolchain.

**Measured, at commit `c274893`:**

```
original.c:91   #ifdef INCLUDEMAIN
original.c:93   int main(int argc, char * argv[])
original.c:110  #endif
harness.c:21    void CWE416_Use_After_Free__malloc_free_char_01_bad(void);
harness.c:23    int main(void)
```

**And the gcc line in `build.sh`:**

```sh
gcc -O0 -g -fno-stack-protector -fno-pie -no-pie -Wall \
    -fdebug-prefix-map="$HERE"=. -ffile-prefix-map="$HERE"=. \
    -fdebug-prefix-map="$SUPPORT"=juliet/testcasesupport \
    -ffile-prefix-map="$SUPPORT"=juliet/testcasesupport \
    -I "$SUPPORT" -o "$OUT" \
    harness.c original.c "$SUPPORT/io.c"
```

There is **no `-DINCLUDEMAIN`**. The case file therefore contributes
`_bad`, `_good`, `goodG2B`, `goodB2G` and no `main`; `harness.c` is the only
translation unit with an entry point. One `main`, no collision, links cleanly.

**Why this matters beyond this fixture.** The synthetic
`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/src.c` carried an
unguarded `main` at line 90. That is what record 116 measured as
`multiple definition of 'main'`. Same CWE, same compiler, opposite outcome — the
difference is one preprocessor guard, and it was in the authored file, not in the
window and not in gcc.

**A useful contrast that is easy to get backwards.** The CWE122 recipe *does*
pass `-DINCLUDEMAIN -DOMITGOOD` (record 117 §1.1), because there the case's own
`main` is the intended entry point and the harness is absent. So "define
INCLUDEMAIN or not" is a per-fixture decision, not a house style. Both are
correct; picking one globally would break one of the two fixtures.

**No Fix A/B on the T30 upstream.** Nothing was changed in `original.c`, and no
"Fix A" (define `INCLUDEMAIN` so the case supplies `main`) or "Fix B" (delete the
guard) was applied to the upstream sample. T30 links as it stands with an
unmodified case; the only file that would ever have needed such a change is the
synthetic `src.c` that record 116 measured, and that file is retired rather than
patched. Editing an upstream sample to make a recipe fit would turn a
reproduction into a rewrite, and `build.json#fixture.source_of_truth.sha256`
would stop describing what was compiled.

---

## 2. The window

`T30/build.json#window` records snapshot uid 14 (`t15-t6-work`) and states plainly
that the build ran on a working snapshot, **not** on the baseline, and that
`T30/isolation-reset.txt` §3 left the revert open. This run closes that.

| Step | Measured |
|---|---|
| Stop | `vmrun stop … soft`, exit 0 |
| Revert | `vmrun revertToSnapshot … gate4-harness`; `snapshot.current` `"11"` |
| Locks after revert | **0** `.lck` directories |
| Boot | `vmrun start … nogui`; SSH up after ~45 s |
| Boot time | `system boot 2026-11-05 21:43`, `uptime` "up 2 minutes" at capture |

The claim "baseline clean" is not the revert exit code. It is these three:

1. `~/cwe416` — created by the CWE416 fixture window — **absent**.
2. `~` contains exactly `D evaluator repair-input route-a`, the gate4-harness home.
3. Boot time is the boot the build ran in; nothing was inherited from a running VM.

Items 1–3 are in `01-window-and-isolation.txt` §1 and §3, measured by the guest.
The uid and the lock count cannot be: a guest cannot see its own snapshot uid or
the hypervisor's `.lck` directories. Those two are in `00-window-host.txt`,
measured on the host after the window closed — `vmrun list` 0 running,
`.vmsd` `snapshot.current = "11"`, `snapshot7.uid = 11` → `gate4-harness`,
`0` `*.lck` — and that file says in its own §7 that it is a re-read, not a
moment-of-revert sample.

---

## 3. The build

`sh build.sh`, verbatim, from `/var/tmp/cwe416`:

```
== inputs ==
fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e  original.c
cef8f533765f3f9184377bf72e32792f6a4128080da8467cb478340a679c63a9  harness.c
50ace91d0f9cd9f281d5d8ff3a9ca879ee2779d737030ae84e8e4be3df5b299c  …/testcasesupport/io.c
a78aaf3a54a6210260ad70123c09c3c283c6edf7808b6244205e00b8f2d9b8d0  …/testcasesupport/std_testcase.h
== output ==
c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9  /var/tmp/cwe416/original.elf
… ELF 64-bit LSB executable, x86-64, … BuildID[sha1]=951731d93ab7aa9e2a94dc87fb8915b784dd693a,
  for GNU/Linux 3.2.0, with debug_info, not stripped
sha256=c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
size=25344
```

stderr, unchanged from the first build and deliberately not suppressed:

```
original.c:36:5: warning: pointer 'data' used after 'free' [-Wuse-after-free]
original.c:34:5: note: call to 'free' here
```

All four inputs were hashed on the host before `scp`, in the guest after arrival,
and by `build.sh` itself on use. Three independent readings, same values.

`testcasesupport` came from the baseline snapshot's own
`~/evaluator/src/juliet-v1.3/C/testcasesupport`: **8 files**, `io.c` and
`std_testcase.h` hashing to `50ace91d…299c` and `a78aaf3a…b8d0`, which is what
`build.json#fixture.support_files` declares and what the NIST archive extraction
on the host produced. That checkout's `C/testcases/` contains **CWE121 only**,
which is exactly why `build.json` says the case source is supplied explicitly
rather than taken from the tree.

---

## 4. readelf

`readelf -h -l -S -d -n` is in `03-readelf.txt`. Against
`build.json#machine_check`:

| Field | Declared | Measured | |
|---|---|---|---|
| class | ELF64 | ELF64 | match |
| data | 2's complement, little endian | same | match |
| type | `EXEC (non-PIE)` | `EXEC (Executable file)` | match |
| machine | AMD x86-64 | AMD x86-64 | match |
| entry point | `0x4011b0` | `0x4011b0` | match |
| build id | `951731d9…693a` | `951731d9…693a` | match |
| stack canary | absent | 0 occurrences of `__stack_chk_fail` | match |
| needed | `libc.so.6` | `libc.so.6` | match |
| debug info | present, not stripped | `.debug_info` present | match |

Non-PIE is worth stating explicitly: the prefix-map flags normalise the recorded
paths but they do not touch `Type`, and `-fno-pie -no-pie` is what holds it at
`EXEC`. A fixture that silently built `DYN` would break any contract whose
`environment_assumptions` say non-PIE — which is the open question in record 117
§1 for the CWE122 recipe.

---

## 5. trigger

```
single             exit_code=0 stdout_hex=05040a stdout_len=3 stderr_len=0
--repeat 50        50x  … 05040a …
--repeat 200       200x … 05040a …
```

**251 runs, one distinct observation.** With ASLR left on, 10 plain runs produced
**10 distinct** values (`1c31020a`, `3d780a`, `46d6030a`, …) — that contrast is why
`setarch -R` is in the trigger rather than an aesthetic choice. The bytes read are
the freed chunk's first bytes; glibc's tcache overwrites them with next/key words
and the key carries a heap address.

The defect is silent: exit status stays 0, stderr stays empty, and the only
evidence is that stdout is 3 bytes where a correct program prints 100 (99 `A`
plus newline). `build.json#trigger.expected_observation` predicted exactly
`05040a`; measured, exactly `05040a`.

**ASan, as a diagnostic only.** `gcc … -fsanitize=address` reports
`heap-use-after-free`, `READ of size 2`, at `original.c:36` via `printLine`
(`io.c:15`), with the free at `original.c:34`, exit 1. That closes the loop
between three independent readings — the compiler warning (`-Wuse-after-free`),
the runtime bytes (`05040a`), and a sanitizer backtrace. The ASan binary is
**not** shipped: it is a different binary by design and must never be ingested.

---

## 6. What this run actually upgrades

Before: `build.json#reproducibility.stable` was true **within one snapshot**
(uid 14), and `build.json#window` said so and flagged the window as not baseline
clean. That is a weaker claim than it looks — a recipe reproducible only inside
one disk state could be reproducing the state rather than the source.

Now: same inputs, same toolchain, **different snapshot**, after a revert and a
cold boot, and the same 25,344 bytes out. The prefix-map flags are the reason it
can be the same bytes across two windows and two directories.

Scope, stated so it is not over-read: this holds on this guest image with
gcc 13.3.0 and glibc 2.39. It is not a claim about another distribution, another
compiler, or another libc.

`T30/build.json` was **not** edited. It is the historic record of the first build
and is bound by `T30/SHA256SUMS`; changing it would rewrite bytes an existing
record cites. `07-rebuild.json` sits beside it and carries the second-window
measurement plus the field-by-field comparison.

### The comparison, and what it covers

Twenty-one fields are tabulated in `07-rebuild.json#conformance`; twenty match.
They are the fields that define the artefact and its observation — `output.*`,
`machine_check.*`, `build.build_script.sha256`, `fixture.harness.sha256`,
`fixture.source_of_truth.sha256`, the two `support_files` digests,
`trigger.sha256`, `trigger.expected_observation`, `window.is_baseline`. The
free-text fields (origins, notes, `why_*`, reproduction prose) were read and
agree, but a string-equality row for them would assert nothing a reader cannot
see; `conformance_scope` states that in the file itself.

The one non-match is `window.is_baseline`: `false` at uid 14, `true` here. It is
the measurement, not a deviation.

Two corrections were made in this pass, both found by re-reading the committed
record against `build.json`. First, the count was written as "twelve of thirteen"
in this record's status line and in the evidence README, while the table itself
held twelve rows, eleven of them matching — a stale count carried over from an
earlier draft, not a measurement. Second, the machine rows (`class`, `data`,
`machine`, `needed`, `debug_info`) plus `output.file`,
`build.build_script.sha256`, `fixture.harness.sha256` and `trigger.sha256` were
quoted in the prose but missing from the table, so the table under-covered what
the record already claimed. Neither correction changes a measured value: `01`–`06`
are byte-identical, `06-SHA256SUMS` still holds, and `SHA256SUMS` was rebuilt on
the host for the two edited host files.

---

## 7. Record 116 stays a diagnostic

Record 116 measured the **synthetic** fixture and found its recipe does not link.
That finding stands and is useful. What it does **not** do is produce a public
sample: the synthetic `src.c` is team-authored, and `fixtures/public/README.md`
is explicit that a self-built sample does not carry the second-defect-class
obligation.

So 116 is reclassified here as **synthetic diagnostic — build/trigger only**. It
has no T8.3 identity: it is not a second defect class, it is not a fixture of
record, and no gate may cite it as either. Three consequences:

- `original.variant.elf` is not shipped anywhere and must not be ingested. A
  variant that differs from `build.json#argv` in two ways cannot stand in for the
  artefact that argv describes.
- The synthetic fixture's `output.sha256` stays `null`. Filling it with the
  variant digest would bind a recipe that was never run.
- Nothing from 116 relieves T8.3. The second-class obligation is unchanged and
  is not satisfied by anything in this record either — T30 is one defect class
  (CWE-416) measured again, and T8.3 stays **blocked**.

---

## 8. contract / tests / candidate — measured gaps, not filled

The instruction was to fill contract/tests/candidate before sending anything to
M4. I did not fill them, and this is why, measured rather than argued.

**CWE416 needs six edits before it can even load.** `SecurityContract` requires
17 keys and forbids unknown ones:

```
as-is                 ValueError: unknown contract fields:
                      ['invalid_behavior', 'max_input_bytes']
after removing those  ValueError: missing contract fields:
                      ['invalid_input_response', 'invalid_stderr',
                       'invalid_stdout', 'max_valid_input_bytes']
```

The four missing fields all describe an **input rejection path**. This case has no
input at all: `bad()` is called with no arguments and the use-after-free is
unconditional. Writing those four fields means inventing a rejection path the
program does not have, which is the gap record 113 documented and it has not
moved.

**CWE122 needs three, and one of them is a real decision.**

```
as-is                  missing: ['allowed_calls']
+ allowed_calls        TypeError: invalid_stdout must be a string
+ invalid_stdout=""    TypeError: invalid_stderr must be a string
+ invalid_stderr=""    loads  — but the contract's own
                       invalid_input_response says
                       "print the recorded stderr line",
                       and an empty string is not a line
```

`allowed_calls` and `invalid_stdout=""` are mechanical: the first is an
enumeration of the calls the case already makes plus the ones `authorized_edits`
permits, the second follows from "without printing the buffer".

`invalid_stderr` is not mechanical. Its bytes are the acceptance criterion for the
invalid path, and if I pick them by building a candidate first and reading its
output, the contract becomes a description of the repair rather than the
specification the repair must satisfy. That is the same circularity that record
115 §3 flagged about a build script hashing its own output — cheaper to avoid
than to unwind.

So the ordering is: contract bytes frozen first, then candidate built against
them. The first half is a contract-owner decision (record 117 §10 already asks it
alongside the PIE question), and I am not the owner of that file. Consequently
there is no candidate for CWE122 in this step, and nothing new goes to M4.

**Where this now stands (2026-11-05, after Lead instruction).** The CWE416
blocker is the same shape and is a policy question, not a measurement one: a
no-input sample cannot honestly fill four fields that describe an input rejection
path. Two ways out, both owned by Lead, neither taken here:

- **A — relax the contract** so a case with no input may declare the rejection
  path as structurally absent (a sentinel, or a contract variant), and the four
  keys become conditional rather than required.
- **B — narrow the fixture set** so only cases with an input rejection path are
  eligible, and CWE416 is recorded as out of scope for the contract, not as a
  gap.

Until one is chosen, contract, tests and candidate for T30 stay **untouched**, on
Lead's explicit instruction. T8.3 stays **blocked**; no candidate is created, no
V0–V5 gate is run, and the second-class obligation remains open.

---

## 9. Not claimed

- **T8.3 stays blocked.** One sample, one defect class; this run re-measures an
  existing artefact and adds no second class.
- **No candidate, no V0–V5.** Build, readelf and trigger only.
- **No fixture byte changed.** `build.json`, `contract.json`, `tests/`,
  `harness.c`, `original.c` are byte-identical to T30 at `c274893`.
- **No second `original.elf` shipped.** The rebuilt binary equals the committed
  one; shipping a copy would put two paths on one hash.
- **No claim about other toolchains.** gcc 13.3.0 / glibc 2.39 on
  `binrepair-vm`, and nothing wider.
