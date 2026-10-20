# 04 — Member 3 oracle freeze (fixture CWE121_src_char_declare_cpy_51b)

**From:** Member 3
**To:** Member 4
**Date:** 2026-10-20
**Status:** answered from measured data. The fixture is built; gate proofs 3–6
are still open, so the fixture is a candidate, not an accepted freeze.

## 1. A or B? — A is selected and the shape was confirmed

A was chosen. The shape test was run over all 5,906 CWE121 `.c` files and
found **12** sinks that satisfy all three conditions at once:

1. signature `*_badSink(char * data)`;
2. body declares `char dest[N]`;
3. body calls `strcpy(dest, data)` with no length check.

All 12 have `N = 50`. Raw output: `fixtures/public/.../evidence/05-shape-search.txt`.

Selected case: `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b`
(s09). It is a sink-only translation unit, so the NIST file is compiled
**byte-for-byte unmodified** and the harness supplies `main`. B (source patch)
is not needed and was not used.

Correction to an earlier internal draft (`worklogs/2026-10-20/reply-to-member-4-oracle.md`):
that draft assumed a stock Juliet `main` reading stdin. The chosen 51b file has
**no `main`**; it exports `..._51b_badSink(char *data)`. There is no argv/stdin
conflict and no `-Dmain=` trick is required. The draft is superseded.

## 2. The four oracle items

### 2.1 `DEST_CAPACITY` and its source line

| Field | Value |
|---|---|
| `DEST_CAPACITY` | **50 bytes** |
| Source file | `C/testcases/CWE121_Stack_Based_Buffer_Overflow/s09/CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b.c` |
| Declaration | **line 28**: `char dest[50] = "";` |
| Unbounded copy | **line 30**: `strcpy(dest, data);` |
| Maximum valid length | **49 bytes** — `len(data) + 1 <= 50`; the NUL is the 50th byte |
| First invalid length | **50 bytes** — 51 bytes are written into a 50-byte object |

The 49/50 boundary is measured, not inferred: 49 passes, 50 is the first
out-of-capacity input.

### 2.2 Original binary behaviour at 0 / 1 / 10 / 49

Measured on `original.elf`
(`aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`), argv[1]
only, outputs compared as raw bytes:

| Length | return code | stdout | stderr |
|---:|---:|---|---|
| 0 | 0 | `"\n"` | `""` |
| 1 | 0 | `"A\n"` | `""` |
| 10 | 0 | `"AAAAAAAAAA\n"` | `""` |
| 49 | 0 | 49 × `A` + `"\n"` | `""` |

These four are the manifest's `valid` cases; all four pass against the
original (`evidence/06-manifest-vs-original.txt`).

### 2.3 `ERROR_STDERR`

Frozen per the team decision of 2026-10-20:

```text
return_code = 1
stdout      = ""
stderr      = "ERROR: input exceeds destination capacity\n"
```

The trailing newline is part of the string; matching is byte-exact.

Two clarifications that must not be lost:

- This is a **post-repair contract**, not an observation of the original. The
  original has no invalid path: length 50 exits 0 with a silent 1-byte
  overflow, length 100 dies with SIGSEGV (139). The manifest's invalid cases
  are therefore expected to **fail** on the original.
- The original **never returns 1**: length 50 returns 0 (silent overflow),
  length 100 returns 139 (SIGSEGV). A 4/6 run is the expected **V0**
  behaviour evidence; it is **not** gate 6 (see §6).
- Exact stderr is cheap for Route B (`fprintf`) and comparatively expensive
  for Route A: a new string plus a PLT call at a patch site whose live
  registers are unknown is closer to "add data and code" than to a minimal
  instruction change. **Gate 3 must test this before the fixture is frozen.**
  If Route A cannot produce the bytes, the options are (a) relax stderr to
  empty or non-empty-not-byte-exact, or (b) record Route A `unsupported` with
  this reason. That is a scope decision for Member 4 + Member 5, not something
  Member 3 can change after the freeze.

### 2.4 Harness call shape

```c
int main(int argc, char **argv)
{
    if (argc != 2) { fprintf(stderr, "usage: %s <input>\n", argv[0]); return 2; }
    CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(argv[1]);
    return 0;
}
```

- **`argv[1]` is passed directly.** No `strdup`, no staging buffer, no
  truncation, no length validation. The overflow happens in the sink's own
  frame.
- `argc != 2` is harness behaviour (exit 2) and is **not** part of the manifest.
- The harness does **not** implement the invalid path; a candidate must.

## 3. Environment baseline (measured)

| Item | Value |
|---|---|
| Host | Windows 11 Home China 25H2, build 26200.9711; Lenovo 21VH |
| Host CPU | Intel Core Ultra X7 358H, 16 cores / 16 logical processors |
| Host RAM / free disk | 31.52 GiB / 404.89 GiB free on D: |
| Virtualization | VMware Workstation 17.5.0 build-22583795; guest boots and serves SSH |
| Guest | Ubuntu 24.04.5 LTS, kernel 6.8.0-147, x86-64 |
| Guest allocation | **4 vCPU / 7.8 GiB visible / 30 GiB disk (29 GiB root, 26 GiB free)** |
| Guest hostname | `binrepair-vm` (192.168.30.128, NAT) |

The VM is built and usable. It is **not** a blocker. Two caveats are part of
the baseline:

1. the 2026-10-20 resize deleted the 2026-10-18 `clean-toolchain` snapshot; a
   replacement was taken on 2026-10-20 10:57 with the VM powered off. It is a
   reset point but **not** a pre-sample baseline (the fixture was built at
   10:27), so it cannot be used to show the guest was untouched before the
   sample entered;
2. clang, Ghidra/JDK, LIEF and angr/Z3 are still missing, so V4 cannot run yet.

## 4. Original ELF + manifest delivery

Already built and measured; available now, not "soon":

| Artifact | SHA-256 |
|---|---|
| `original.elf` (26,792 B) | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| `tests/valid.json` | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| `tests/invalid.json` | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |

Paths: `fixtures/public/CWE121_src_char_declare_cpy_51b/`. Provenance, build
script, harness and raw evidence are in the same directory.

## 5. `vm-blocker.md`

Not written and not applicable: the VM exists, boots, and ran the fixture. A
blocker file is for "cannot build the guest", not for "the guest still has
gaps". The real gaps (post-sample snapshot, missing V4 toolchain, sudo user,
open NAT, no read-only tool mount)
are recorded in `docs_BinaryRepair/vm-profile.md` and in the reply, so they
cannot be mistaken for completed isolation.

## 6. Gate 6 and V0 are different (confirmed with Member 4)

- **Manifest 4/6 is V0/V3 behaviour evidence.** It shows the original is
  vulnerable (valid pass, invalid fail); it does not show that a verifier can
  detect the violation.
- **Gate 6 is partial.** Member 4 accepts the concrete counterexample and
  crash record as part of gate 6: 100 × `A` → SIGSEGV, `rip = 0x401317`,
  saved `rbp`/return slot overwritten with `0x4141414141414141`
  (`evidence/07-gate6-crash-evidence.txt`, summary in
  `docs_BinaryRepair/gate6-crash-summary.md`). Symbolic detection of the
  out-of-bounds path is pending V4 and is not claimed.
- **V4 blocker and isolation gaps are escalated to the team lead by Member 4.**
  They are written into the fixture's
  `docs_BinaryRepair/fixture-freeze-record.md` as explicit open items so the
  freeze cannot read as "V4 ready" or "isolated execution ready".
- **One manifest for both routes.** Member 4 will run V3 against Route A and
  Route B with this same manifest and assert byte-identical stderr; V0 is
  recorded separately.
