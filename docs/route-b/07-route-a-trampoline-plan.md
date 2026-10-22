# Route A trampoline plan — CWE121 candidate (conditional)

**Status:** **CONDITIONALLY FEASIBLE** (scope ruled; cave load PASS; 6 cases not yet
measured). This is a byte-level plan and layout audit, not an executed patch.
The reviewed six-entry `authorized_edits` allows a 5-byte redirect at `0x401304`,
the existing R-X tail extension to `0x401fff` (no new segment), up to 256 bytes of
added code and 64 bytes of read-only data, and an fd-2/exit-1 invalid path.
Under a "no new section / no length change" policy, Route A is **UNSUPPORTED**
for this fixture.

**Measurement update (2026-10-22):**

- the usable window in `badSink` is **19 bytes, zero slack** — no room for guard + exact stderr;
- the PLT has **no `strlen` / `strncpy`**, so the guard must be inline in the trampoline;
- strategy C (detour + R-X trampoline + cave string) is structurally feasible;
- **cave probe PASS**: `0x4018e9–0x401fff`, 1815 B, `r-xp`, runtime read of written
  bytes; **no header change needed**; delivery will include the probe command + output;
- patch point: `0x401304` (`call strcpy@plt`), not the `endbr64 + push rbp` at
  `0x4012b0`;
- the exact error string is placed **inside the existing R-X cave** (read-only
  data, no W+X), not in a new R-- segment; no new segment is required;
- 6 cases are **candidate execution**: snapshot revert + network cut + unprivileged
  user are required; snapshot revert is **not yet measured**, so the 6 cases are not run;
- plan: revert test → trampoline → patch copy → audit → 6 cases;
- until 6/6 runs, Gate 3 stays **CONDITIONALLY FEASIBLE**, never `pass`;
- failures must be reported before **2026-10-23 18:00**, no retroactive edits.

**Reviewed contract (2026-10-22):**

`fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json`,
canonical hash `1a0ad101097461b207e3ea07e264d8d6eb03bc57d1f54c7b9e41c2955015c10c`.
The six `authorized_edits` entries are:

1. 5-byte relative redirect of `call strcpy@plt` at `0x401304`, branch back on the valid path;
2. extend the existing R-X `PT_LOAD` `p_filesz/p_memsz` to `0x401fff` if needed
   (record offset/vaddr/filesz/memsz/align; no overlap);
3. no new segment/dynamic import/GOT/PLT/relocation edit or permission broadening;
   only as a fallback, one new R-X `PT_LOAD`;
4. invalid path writes fd 2 and exits 1 without returning to `main` or writing stdout;
5. up to 256 bytes of added x86-64 code in the verified-unused R-X tail;
6. up to 64 bytes of added read-only data with exactly
   `ERROR: input exceeds destination capacity\n`, RIP-relative references only.

> **Resolved 2026-10-22:** entry 1 now says branch back to **`0x401309`**,
> the instruction after the 5-byte call at `0x401304`. Canonical hash is
> `1a0ad101097461b207e3ea07e264d8d6eb03bc57d1f54c7b9e41c2955015c10c`.
> The other five entries, oracle, harness and `original.elf` are unchanged.

Input: `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf`
SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`.

---

## 1. Edit set

| Region | Action |
|---|---|
| `0x4012c0`–`0x4012c7` in `badSink` | replace dead zeroing with `jmp 0x406000` + 3 NOPs |
| new R-- segment at `0x405000` | exact 42-byte error message |
| new R-X segment at `0x406000` | 66-byte guard/error trampoline |
| ELF program headers | add two `PT_LOAD`; file length grows |
| `main` `0x401256`–`0x4012af` | **untouched** |
| 5-byte call at `0x401304` | **Strategy C redirects it as a whole; see 12** |
| other functions/data | untouched |

Original detour site bytes (8-byte `mov qword [rbp-0x40],0`):

```text
48 c7 45 c0 00 00 00 00
```

Replacement:

```text
e9 3b 4d 00 00 90 90 90
```

`e9 rel32` from `0x4012c0` to `0x406000` (`0x4d3b`), then three NOPs.

---

## 2. New segments (proposed)

| Segment | vaddr | file offset | filesz | flags | content |
|---|---:|---:|---:|---|---|
| message | `0x405000` | `0x7000` | `0x1000` | `R` | 42-byte string, rest zero |
| trampoline | `0x406000` | `0x8000` | `0x1000` | `R\|X` | 66-byte code, rest zero |

Both satisfy `vaddr % 0x1000 == offset % 0x1000`. Original file is 26,792
(`0x68a8`) bytes; the proposed file is `0x9000` (36,864) bytes. LIEF may choose
different offsets; the audit records the actual values and checks the congruence.

The two new `PT_LOAD` entries increase `e_phnum`; a tool may relocate the program
header table. That is an allowed layout change **only if** the audit confirms every
original `PT_LOAD` keeps its vaddr and permissions, and the entry point is unchanged.

---

## 3. Error message

Length **42** (including the trailing newline):

```text
ERROR: input exceeds destination capacity\n
```

Hex:

```text
4552524f523a20696e70757420657863656564732064657374696e6174696f6e2063617061636974790a
```

The contract requires this exact stderr and empty stdout. `fprintf` writes the
message as its format string; it contains no `%`, so no format expansion occurs.

---

## 4. Trampoline bytes

At `0x406000`, 66 bytes:

```text
4c8b45b831c941803c0800740348ffc1ebf44883f9310f8621000000488b3d5de0ffff
488d35d6efffff31c0e8efb0ffffb8e7000000bf010000000f05e9b4b2ffff
```

Disassembly:

```text
406000: mov  r8, [rbp-0x48]       ; data pointer saved at 0x4012bc
406004: xor  ecx, ecx
406006: cmp  byte [r8+rcx], 0     ; inline strlen
40600b: je   0x406010
40600d: inc  rcx
406010: jmp  0x406006
406012: cmp  rcx, 49              ; max_valid_input_bytes
406016: jbe  0x40603d             ; valid -> jump back
40601c: mov  rdi, [rip-0x1fa3]    ; stderr (0x404080)
406023: lea  rsi, [rip-0x102a]    ; message (0x405000)
40602a: xor  eax, eax             ; variadic
40602c: call 0x401120             ; existing fprintf@plt
406031: mov  eax, 231             ; exit_group
406036: mov  edi, 1
40603b: syscall
40603d: jmp  0x4012f6             ; original strcpy path
```

Control flow:

- `len <= 49` → jump to `0x4012f6`, execute `strcpy` + `printLine` as before;
- `len >= 50` → `fprintf(stderr, message)`, then `exit_group(1)`.

`badSink` is `void` and `main` forces `eax=0`; a plain `return 1` would **not**
produce exit code 1. The syscall is required for the contract.

The dead zeroing of `dest` is skipped on the valid path. `dest` is never read after
`strcpy` (only `data` is passed to `printLine`), so behaviour is unchanged. If a
reviewer requires identical frame contents, add the 50-byte zero loop to the
trampoline (no external calls) before jumping back.

---

## 5. Relocations / symbols

- **No new dynamic relocations and no new dynamic symbols.**
- `fprintf` is already imported; its PLT stub is `0x401120`.
- `stderr` is the existing object at `0x404080`; the trampoline uses a RIP-relative
  load, no GOT relocation.
- The message uses a RIP-relative `lea`.
- `strcpy@plt` (`0x4010d0`) is untouched; the valid path reuses the original call.
- `printLine` is a local function; the valid path returns to the original call site
  in `badSink`, so no new call is introduced.

Expected audit: `.rela.plt` and `.rela.dyn` entry counts unchanged.

---

## 6. CET / registers / stack

- **CET IBT:** the new code is entered by a **direct** `jmp`; no `endbr64` is
  required at `0x406000`. The `call 0x401120` lands on the existing `endbr64` PLT
  stub. Do not change the entry to an indirect branch without adding `endbr64`.
- **SHSTK:** no return address is written; the invalid path exits by syscall, the
  valid path returns through the original `ret`. Shadow stack is unaffected.
- **Stack:** at `0x4012c0`, after `sub rsp,0x50`, `rsp` is 16-byte aligned; the
  `fprintf` call satisfies the SysV requirement.
- **Registers:** `r8`/`rcx` are in the handoff's scratch set. `fprintf` requires
  `rdi`/`rsi`/`rax`; at the detour point those are dead because `0x4012f6`
  reloads `rdx`/`rax`/`rsi`/`rdi`. If the "only rcx/r8-r11" constraint is literal,
  this needs an explicit exception — **scope ruling**.

---

## 7. Layout audit (LIEF + readelf)

Build (on Ubuntu, LIEF current; `lief` 0.12 is known to over-allocate segments):

```python
import lief
b = lief.ELF.parse("original.elf")
for addr, data, flags in (
    (0x405000, MESSAGE, lief.ELF.SEGMENT_FLAGS.R),
    (0x406000, CODE, lief.ELF.SEGMENT_FLAGS.R | lief.ELF.SEGMENT_FLAGS.X),
):
    seg = lief.ELF.Segment()
    seg.type = lief.ELF.SEGMENT_TYPES.LOAD
    seg.flags = flags
    seg.content = list(data)
    seg.virtual_address = addr
    seg.physical_address = addr
    seg.alignment = 0x1000
    b.add(seg)
b.patch_address(0x4012c0, list(DETOUR))
b.write("roundtrip_route_a.elf")
```

Audit:

```bash
readelf -lW roundtrip_route_a.elf
readelf -SW roundtrip_route_a.elf
readelf -rW roundtrip_route_a.elf
readelf -hW roundtrip_route_a.elf
objdump -d --start-address=0x4012c0 --stop-address=0x4012c8 roundtrip_route_a.elf
objdump -d --start-address=0x406000 --stop-address=0x406042 roundtrip_route_a.elf
sha256sum original.elf roundtrip_route_a.elf
```

Pass criteria:

- [ ] new `LOAD` at `0x405000` has `R` only; content at `0x405000` equals the message;
- [ ] new `LOAD` at `0x406000` has `R|E`; content equals the code bytes;
- [ ] `0x4012c0` contains `e9 3b 4d 00 00 90 90 90`;
- [ ] original `LOAD` vaddrs and flags are unchanged; entry point unchanged;
- [ ] `.rela.plt` / `.rela.dyn` counts unchanged;
- [ ] no segment overlaps; `vaddr % 0x1000 == offset % 0x1000`;
- [ ] `readelf -lW` shows no `W|E` segment;
- [ ] harness bytes `0x401256`–`0x4012af` unchanged;
- [ ] Strategy C call-redirect bytes at `0x401304` recorded; see `12`.

Then run the frozen manifest on the patched ELF; expected 6/6:

- valid 0/1/10/49 bytes: exit 0, stdout = input + `\n`, stderr empty;
- invalid 50/100 bytes: exit 1, stdout empty, stderr exact 42-byte message.

`routeb/audit_route_a_layout.py` implements the static checks above and can be
run in CI after a LIEF build.

---

## 8. Risks / open items

| Risk | Mitigation |
|---|---|
| LIEF relocates PHDR or over-allocates segments | audit original LOADs/entry; use current LIEF; record actual offsets |
| `fprintf` buffering | stderr is unbuffered by default; if not, add `fflush(NULL)` (would need a new PLT) |
| CET IBT on an indirect entry | use a direct `jmp`; add `endbr64` if the entry ever becomes indirect |
| dead zeroing skipped | dest is unread; optionally add the zero loop in the trampoline |
| `authorized_edits` does not allow segments | Route A = **UNSUPPORTED**; do not ship a hand-written relocation engine |
| "two routes byte-identical" interpreted literally | infeasible; needs a scope definition (behaviour vs bytes) |
