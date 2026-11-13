# BinaryRepair — tasks that cannot run on the macOS host

This list is for a member with a Linux VM, Windows runtime and/or macOS arm64 VM.
All commands assume the repository root is `binary-repair-gui/` unless stated.

Current local baseline (v4 tree):

```text
macOS (GNU readelf): 950 collected / 946 passed / 4 skipped / 0 failed
Linux VM:            950 collected / 943 passed / 7 skipped / 0 failed
```

v4 note: ELF/PE/Mach-O repair now has container-neutral analysis and guard
injection. PE x86-64/arm64 and AArch64 ELF use Unicorn instruction-level
evidence (works on Linux); Mach-O native execution exists only on macOS, so on
Linux those candidates must be recorded as `not_verified`, not success.

---

## L1. Linux non-browser baseline (must do first)

Environment: Ubuntu 24.04 x86-64, Python 3.11/3.12, `build-essential`,
`binutils`, `clang`.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q --ignore=tests/e2e \
  --junitxml=artifacts/ubuntu-verification/junit.xml
```

Expected: **0 failed**. Current collection is 950; on Linux the Mach-O native
tests and two Mach-O positive pipeline cases skip, leaving 7 skips and 943
passes in the local VM. Record the actual JUnit counts; do not copy a fixed
pass count.

Evidence to return:

```text
ubuntu-verification/junit.xml
ubuntu-verification/pytest.log
ubuntu-verification/environment.txt
SHA256SUMS
```

---

## L2. qemu-x86_64 native/guest checks

```bash
sudo apt-get install -y qemu-user qemu-user-static
qemu-x86_64 --version

chmod +x artifacts/vuln-elf/vuln.elf artifacts/vuln-elf/vuln-strict-fixed.elf
for n in 0 1 16 17 32; do
  printf 'A%.0s' $(seq 1 "$n") | ./artifacts/vuln-elf/vuln.elf \
    > "/tmp/vuln-$n.out" 2> "/tmp/vuln-$n.err"
  echo "n=$n exit=$?"
done
```

Return stdout/stderr/exit for each size, and the SHA-256 of every input/output.
The vulnerable fixture is expected to be non-rejecting for long input; the
strict fixture must reject 17/32 bytes.

Also run the unified CLI under qemu only if a static Linux build is available;
otherwise record `not_verified`.

---

## L3. CGC POV replay

Assets are in `datasets/cgc-linux-build/challenges/`.

```bash
QEMU="$(command -v qemu-x86_64 || command -v qemu-x86_64-static)"

python3 scripts/cgc_pov_replay.py "$QEMU" \
  datasets/cgc-linux-build/challenges/Palindrome/Palindrome \
  datasets/cgc-linux-build/challenges/Palindrome/pov_1.pov 15

python3 scripts/cgc_pov_replay.py "$QEMU" \
  datasets/cgc-linux-build/challenges/Palindrome/Palindrome_patched \
  datasets/cgc-linux-build/challenges/Palindrome/pov_1.pov 15
```

Expected: vulnerable `cb_signal=11`, patched `cb_exit=0`; repeat 3 times.
Do the same for `basic_messaging`. `Board_Game` is behavioral only;
`3D_Image_Toolkit` and `CGC_Hangman_Game` were not reproduced in the earlier
exploratory run.

This is **exploratory POV evidence**, not V0–V5 acceptance and not a hardened
guest.

Evidence: command, qemu version, raw stdout/stderr, exit/signal, 3 repeats,
SHA-256 of challenge/POV.

---

## L4. arm64 ELF

```bash
sudo apt-get install -y qemu-user gcc-aarch64-linux-gnu
qemu-aarch64 --version
```

Use the AArch64 fixture builders in `tests/test_arm64_repair.py` or compile a
static arm64 test binary. Run scan/repair and qemu-aarch64, capture exit/stdout.
If no arm64 runtime is available, report `not_verified`.

---

## W1. PE runtime (Wine or Windows VM)

Use `fixtures/pe/cli-64.exe` and a patched PE produced by `repair_pe` only if a
supported copy-call pattern is present. Run before/after with fixed inputs.

Return:

```text
stdout/stderr/exit code
PE original/patched SHA-256
Authenticode status: signature_invalidated true/false
```

Do not claim Authenticode remains valid. The current fixture does not contain a
supported copy-call pattern, so this task may only validate scan/negative
behavior until a real PE fixture is supplied.

---

## M1. Mach-O runtime (macOS arm64 VM)

Use `fixtures/macho/3D_Image_Toolkit` and the `__brfix`/MOVZ outputs from
`tests/test_macho_cave.py` / `repair_macho`.

Return:

```text
otool -l __TEXT/__brfix and LC_SEGMENT_64 before/after
codesign -dv / -vv output; codesign_invalidated true/false
actual run stdout/stderr/exit if the binary is runnable
```

If no macOS VM is available, record `not_verified`; static LIEF reparse is not
runtime evidence.

---

## H1. High-load compiler-timeout regression

The `a436b64` CI failure was a load-dependent `clang -fsyntax-only` timeout in
`test_c_overflow_patterns`. `774c584` raised the timeout to 20 s and treats
compiler timeout/OS errors as `compiler_unavailable`.

Run the regression on a loaded Linux runner:

```bash
python -m pytest -q tests/test_patch_validation.py
python -m pytest -q tests/test_c_overflow_patterns.py
```

Return the full log and note whether `compiler_unavailable` appears instead of a
false patch rejection.

---

## CI / evidence

Canonical remote evidence:

```text
0fe9241  run 43256887551  889 passed / 1 skipped / 0 failed / 890 total
df82b6c  run 43248205593  success (feature baseline)
774c584  run 43256190605  success (timeout fix)
9a451fd  run 43249875815  success (docs-only)
a436b64  run 43248544193  FAILURE (flake; not a green baseline)
```

After local changes, re-run Ubuntu CI and record the new run; do not reuse
numbers blindly.

---

## What not to claim

- `unsupported`/`not_verified`/`not_run` are not success.
- qemu-user is not a security sandbox.
- Static PE/Mach-O reparse is not runtime verification.
- A passing macOS test run is not a Linux acceptance run.
