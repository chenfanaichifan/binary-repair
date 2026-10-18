# To member 3: fixture, test manifest, and VM deliverables (Tech Design §5, §14)

**Recipient:** Member 3 (sample and execution environment slice)
**From:** Verification slice (Member 4)
**Date:** 2026-10-18
**Basis:** `docs_BinaryRepair/TechDesign-BinaryRepair-MVP.md` §3, §4, §5, §7, §13, §14
**Needs a reply:** four things — (1) host specs and virtualization availability; (2) chosen public fixture and expected date; (3) whether the test-manifest format below is acceptable; (4) who supplies the Route A / Route B / verifier proofs in the fixture selection gate. A fill-in template is at the end.

---

## 1. Why this blocks everyone

The verification slice can run pure logic today (29 unit tests passing), but V1–V4 checks need real artifacts:

- **V1 structure/placement** needs the actual x86-64 ELF bytes.
- **V3 concrete behaviour** needs the frozen valid/invalid test manifest and its oracle.
- **V4 bounded symbolic security** needs the function entry, symbols, and stack layout.
- **V5 reproducibility** needs versions and image hashes.

Without these, the integration, behaviour, and symbolic suites stay skipped. That is honest but it means the demonstration has no evidence. Member 3 is the only slice that can unblock this.

The Tech Design allows two acceptable outcomes for this week (§14): **real provenance and input metadata, or an explicit setup blocker.** A blocker is a valid delivery. A half-working environment presented as working is not.

## 2. What you must deliver

### 2.1 Environment baseline (can start today)

Record measured facts, not estimates:

- host CPU architecture (confirm x86-64, not just "Ubuntu")
- Ubuntu release, RAM, free disk
- virtualization availability (VT-x / AMD-V, hypervisor usable)
- planned guest allocation (4 vCPU, 8 GiB RAM, 30 GiB disk)

Suggested file: `docs_BinaryRepair/environment-baseline.md`

Do not infer this from the PRD. Run the commands and record the output. If the host cannot support the guest, say so in the same file and stop there — do not plan around hardware you have not measured.

### 2.2 Public fixture and provenance

Source one uncomplicated **CWE-121** case, preferably from **NIST Juliet C/C++ 1.3**. The suite is a source of fixtures, not evidence that a fixture works with both routes.

It must satisfy the supported profile (Tech Design §5):

- ELF64, little-endian, `EM_X86_64`, **non-PIE `ET_EXEC`**, single process, single thread
- a small C function with a reviewed System V AMD64 scalar/pointer interface, identifiable entry, ordinary returns, bounded input processing
- no packed or self-modifying code, no TLS-dependent repair region, no C++ exceptions, no unusual unwind, no unresolved indirect incoming transfers into overwritten bytes
- retained function symbols for localization; disclose every hint supplied
- existing protections preserved (NX, RELRO, stack protection, control flow) — a feature the adapter cannot preserve means `unsupported`, never silent removal

Provenance record must contain:

- source URL, test-suite ID, original file path
- build command, compiler version, **complete compile flags**
- SHA-256 of the produced ELF
- machine check: ELF class, endianness, machine, `ET_EXEC`, no PIE
- function under test and its entry address
- **binary-level violation evidence**: the command that triggers the overflow on the original binary and the observed result (this is V0/V3 evidence, not a source-code claim)

Suggested layout:

```
fixtures/public/<case-id>/original.elf
fixtures/public/<case-id>/provenance.md
```

### 2.3 Test manifest (the interface verification consumes)

The manifest is a freeze point. Per Tech Design §7 it may contain argument arrays, stdin artifact IDs, expected return/stdout/stderr, and optional allowed output files. It must **not** express arbitrary host commands, shell scripts, or unrestricted paths.

Proposed format for confirmation:

```json
{
  "schema_version": 1,
  "case_id": "CWE121_xxx",
  "original_sha256": "<64 hex>",
  "tests": [
    {
      "id": "valid-empty",
      "kind": "valid",
      "argv": ["./original", ""],
      "stdin_literal": null,
      "stdin_artifact": null,
      "expected": {
        "return_code": 0,
        "stdout": "",
        "stderr": "",
        "allowed_output_files": []
      },
      "rationale": "smallest defined-valid input"
    }
  ]
}
```

Required coverage:

| Kind | Cases |
|---|---|
| valid | empty, smallest, typical, maximum valid input |
| invalid | first invalid input, and a longer invalid input |
| oracle | expected return code **and** stdout/stderr, plus relevant side effects |

The overlong input must take the defined error path **without an out-of-bounds destination access**. "It still crashed" is not an oracle; "it printed the error message and exited non-zero" is.

Suggested layout:

```
fixtures/public/<case-id>/tests/valid.json
fixtures/public/<case-id>/tests/invalid.json
fixtures/public/<case-id>/tests/README.md   # oracle rationale
```

### 2.4 Disposable VM or explicit blocker

If virtualization is available:

- disposable Ubuntu x86-64 guest, unprivileged execution user
- **no network during a job, no credentials, no host home mounts, no clipboard**
- snapshot reset between test runs so a candidate cannot alter a later test's oracle
- trusted tool executables and baseline files read-only to the execution user
- toolchain smoke-tested: Ghidra + JDK, Capstone, LIEF, LLVM/Clang, binutils/GDB, angr/Claripy/Z3
- record OS/kernel, Python/JDK, Ghidra release, backend commit, compiler flags, dependency lock, solver version, **and guest image hash**

If virtualization is not available: write `docs_BinaryRepair/vm-blocker.md` stating exactly what is missing and what would resolve it. Do not substitute the Windows host for the guest.

## 3. Fixture selection gate (Tech Design §5)

Do not freeze a fixture until all six are demonstrated on that fixture:

| # | Proof | Owner |
|---|---|---|
| 1 | a meaningful, freezable valid-input domain | Member 3 |
| 2 | a binary-level violation on the original binary | Member 3 |
| 3 | Route A patch feasibility | Member 5 |
| 4 | Route B unchanged round trip | Member 5 |
| 5 | safe placement for both routes | Member 5 + Member 3 |
| 6 | a verifier that detects the original violation | Member 4 |

Member 3 cannot declare the fixture accepted alone. If a sample fails a proof, record why and try another public case; do not substitute two different samples for the same input without team agreement.

## 4. What verification consumes from you

| Need | You provide | Unlocks |
|---|---|---|
| real x86-64 ELF bytes | `original.elf` | V1 structure/placement |
| frozen inputs + oracle | `tests/*.json` | V3 concrete behaviour |
| entry, symbols, stack layout | provenance + ELF inspection record | V4 symbolic modelling |
| versions + image hash | environment baseline + VM profile | V5 reproducibility |

Each thing you provide is a freeze point: changing it invalidates approvals and requires a new run. Tell member 4 before you change a hash.

## 5. Security lines (no reply needed, must be followed)

- **Never build or execute the sample on the Windows/host machine.** All building, parsing, and execution belongs in the isolated guest.
- Keep the **evaluator-only workspace separate** from the repair input: source, reference fix, source maps, hidden tests, and evaluator annotations must not enter the repair input or a model prompt.
- Disclose every hint (symbols, metadata) supplied with the fixture; the provider may already know public source, and that evaluation limitation must be stated.
- No network and no credentials inside the guest during a job.
- Prefer a recorded blocker over a fabricated environment.

## 6. Four points to confirm

| # | Question | Suggested default |
|---|---|---|
| 6.1 | Host specs and virtualization: what is actually available? | Record measured values; flag if the 4 vCPU / 8 GiB / 30 GiB plan is not achievable |
| 6.2 | Which public fixture (suite ID + case) will you freeze, and by when? | One CWE-121 case from Juliet C/C++ 1.3, named and dated |
| 6.3 | Is the test-manifest format in §2.3 acceptable? | Accept; add fields only if they are typed and path-safe |
| 6.4 | Who supplies gate proofs 3–6, and when? | Member 5 for 3–5, Member 4 for 6, all before the fixture is frozen |

## 7. Reply template (copy and fill in)

```text
Environment: host arch ____ / Ubuntu ____ / RAM ____ / free disk ____ / virtualization ____
Fixture: suite ____ / case ____ / expected freeze date ____
Manifest format: [ ] accept as-is  [ ] change: ____
Gate owners: Route A ____ / Route B ____ / placement ____ / verifier ____
VM: [ ] can build (image hash later)  [ ] blocked: ____
Other:
```

## 8. Appendix: current state (measured 2026-10-18)

- `python -m pytest tests/unit -q -p no:cacheprovider` -> **29 passed**
- `python -m pytest tests/integration -q -p no:cacheprovider -rs` -> **2 skipped** (`app.services.jobs`, `app.domain.candidates` missing; skip is not a pass)
- No fixture, no VM, and no symbolic tool exist in the current environment. V1–V4 cannot run at all yet.
- The local development host is Windows with Python 3.14.6; the documented target is Ubuntu 24.04 with Python 3.12. That mismatch is exactly what your environment baseline must resolve.
