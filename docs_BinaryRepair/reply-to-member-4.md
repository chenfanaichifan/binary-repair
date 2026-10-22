# Reply to Member 4 — fixture, manifest and VM deliverables

**To:** Member 4 (verification slice)
**From:** Member 3 (sample and execution environment slice)
**Date:** 2026-10-20
**Re:** your memo of 2026-10-18, "fixture, test manifest, and VM deliverables"
**Status:** fixture candidate built and measured; **not frozen**; gate proofs 3–6
still outstanding.

**State note (2026-10-22):** this letter is kept as sent. The guest state has
changed since — the V4 toolchain is installed, the isolated wrapper exists, and
the snapshot chain was rebuilt. See `state-change-2026-10-22.md` for the current
facts; the statements below about "no snapshots", `uid 3` and open outbound NAT
describe 2026-10-20 and are not current.

## 1. The four answers

### 6.1 Host specs and virtualization

Measured on the actual workstation, not estimated:

| Item | Value |
|---|---|
| Host OS | Windows 11 Home China, 10.0.26200 build 26200.9711 |
| CPU | Intel Core Ultra X7 358H, 16 cores / 16 logical processors |
| RAM | 31.52 GiB (33,840,197,632 bytes) |
| Free disk (D:) | 404.89 GiB |
| Virtualization | VMware Workstation 17.5.0 build-22583795; guest boots and answers SSH |
| Guest now | Ubuntu 24.04.5 LTS, 4 vCPU / 7.8 GiB visible / 30 GiB disk (29 GiB root, 26 GiB free) |

**The 4 vCPU / 8 GiB / 30 GiB plan is now met** (resized 2026-10-20; guest
hostname is now `binrepair-vm`). Two consequences of the resize are disclosed
rather than glossed over:

1. the resize deleted the 2026-10-18 `clean-toolchain` snapshot; a replacement
   was taken on 2026-10-20 10:57 with the VM powered off (uid 3). It is a
   reset point, **not** a pre-sample baseline: the fixture was built at 10:27,
   so the guest already contains that work;
2. the pre-resize disk hash is obsolete. New hashes were taken with the VM
   powered off and are recorded in `vm-profile.md` §2 and
   `fixture-freeze-record.md` O3; they identify file bytes at that timestamp,
   not reproducible guest content.

Timing measurements from this guest are now representative of the planning
allowance.

Note on the firmware flag: `VirtualizationFirmwareEnabled` reads `False` while
a VMware guest actually runs. I treat the measured boot as the fact and the
flag as unreliable here.

### 6.2 Fixture and freeze date

| Field | Value |
|---|---|
| Suite | NIST Juliet Test Suite for C/C++ v1.3 (2017-10-01) |
| Case | `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b` |
| Path in suite | `C/testcases/CWE121_Stack_Based_Buffer_Overflow/s09/...` |
| Case SHA-256 | `8387d64613192b47c30658153548d111366f232a0bf03714e26643dd16ad343b` |
| Built | 2026-10-20 02:27 UTC, Ubuntu 24.04.5, gcc 13.3.0 |
| ELF SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Proposed freeze | **2026-10-21**, after gates 3–6 |

The NIST case is compiled unmodified. The only additions are a 90-byte
`main` (0x401256–0x4012af) that calls the exported sink with `argv[1]`
directly, and the `io.c` support unit. `DEST_CAPACITY = 50` (`char dest[50]`,
line 28), so the maximum valid input is 49 bytes.

### 6.3 Test-manifest format

**Accepted as-is.** No fields added, no shell strings, no unrestricted paths.
`stdin_literal` and `stdin_artifact` are both `null`; the only input channel is
`argv[1]`.

| File | SHA-256 |
|---|---|
| `tests/valid.json` | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| `tests/invalid.json` | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |

Oracle, as frozen:

- valid: `len <= 49`, reproduce the original's measured stdout/exit;
- invalid: `len >= 50`, exit **1**, stdout **empty**, stderr exactly
  `ERROR: input exceeds destination capacity\n`.

Both routes must emit the same bytes. If they do not, V3 becomes two standards,
which is what we are trying to prevent. Please confirm this is the contract
you will assert, and say now if the message text should change — after freeze
it costs a new manifest and new approvals.

### 6.4 Gate ownership

Per your suggested default, and subject to Member 5 confirming:

| Gate | Owner | Status / needed by |
|---|---|---|
| 1. valid-input domain | Member 3 — **done** (0–49, measured) | — |
| 2. binary-level violation | Member 3 — **done** (100 × `A` → SIGSEGV) | — |
| 3. Route A patch feasibility | Member 5 | before 2026-10-21 |
| 4. Route B unchanged round trip | Member 5 | before 2026-10-21 |
| 5. safe placement, both routes | Member 5 + Member 3 | before 2026-10-21 |
| 6. verifier detects original violation | Member 4 | **partial** — concrete counterexample accepted; symbolic pending V4 |

Gate 6 is **not** satisfied by the manifest run: 4/6 against the original is
V0 behaviour evidence. Gate 6 needs a detection mechanism; the concrete
counterexample + crash record is accepted as partial, symbolic detection is
blocked on V4.

## 2. What this unlocks, and what it does not

- **V1 structure/placement:** unblocked. Real ELF64 `ET_EXEC`, non-PIE,
  symbols retained, 26,792 bytes.
- **V3 concrete behaviour:** unblocked. Six frozen cases with byte-exact
  oracles; a manifest run against the original gives **4/6 passed** — the four
  valid cases pass and the two invalid cases fail, which is the expected V0
  shape for a vulnerable binary
  (`fixtures/.../evidence/06-manifest-vs-original.txt`).
- **V4 bounded symbolic security:** **still blocked.** The guest has no
  angr/Claripy/Z3, no LIEF, no clang, and no Ghidra/JDK. Capstone and
  pyelftools are present but only import-tested. Do not schedule V4 until
  those are installed and smoke-tested, or record V4 as `unsupported` with
  the missing-backend reason.
- **V5 reproducibility:** partial. Tool versions, the Python dependency lock
  and the powered-off disk hashes (2026-10-20, `vm-profile.md` §2) are
  recorded. Still missing: a backend commit hash — the D: working copy has a
  Git repository but no commit yet, and fetch/push fail with
  `SEC_E_NO_CREDENTIALS`.

## 3. Isolation status (disclosed, not claimed)

The guest is not yet a compliant disposable execution environment:

1. the login user `lab` has passwordless sudo — jobs are not unprivileged;
2. outbound NAT is reachable — there is no per-job egress block (I fetched a
   byte range from NIST during setup);
3. the reset point post-dates the fixture build: `clean-toolchain` exists
   (2026-10-20 10:57) but reverting to it does not return the guest to a
   pre-sample state;
4. tools are not on a read-only mount separate from the job workspace.

These do not block fixture construction; they block a claim that jobs run
isolated. They are on the Member 3 fix list before any candidate is executed.

## 4. Attachments

- `docs_BinaryRepair/04-member-3-oracle-freeze.md` (the four oracle answers in one page)
- `docs_BinaryRepair/environment-baseline.md`
- `docs_BinaryRepair/vm-profile.md`
- `docs_BinaryRepair/vm-pip-freeze.txt`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/provenance.md`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/tests/{valid,invalid}.json`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/tests/README.md`
- `fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/` (raw command output)

## 5. Three things I need from you

1. Confirm the invalid-input oracle is frozen as written (exit 1, exact
   stderr above); it is a post-repair contract, not an original-behaviour
   observation.
2. Confirm the same manifest is used for V3 on both routes with byte-identical
   stderr, and that the 4/6 V0 result is recorded separately — **not** as
   gate 6.
3. Acknowledge the two freeze-record open items (O1 V4 blocked, O2 isolation
   incomplete) so the freeze cannot be read as "V4 ready". You said you will
   escalate both to the team lead; the durable copy is
   `docs_BinaryRepair/fixture-freeze-record.md`.

## 6. Evaluation limitation

Juliet 1.3 is public and the `good()` counterparts are public. A model may
recognise the case and the intended fix from training data. Results on this
fixture cannot support a claim of independent binary analysis. This must
appear next to any reported result.
