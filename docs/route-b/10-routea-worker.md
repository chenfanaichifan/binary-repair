# Route A worker — decode, trampoline plan, LIEF audit

**Status (2026-10-22):** decode + plan + edit-manifest schema implemented.
`build` is intentionally gated by `--scope-authorized`; **the candidate has not
been patched with the exact stderr message**, because Gate 3 is still
**NEEDS SCOPE RULING**. Gate 4 (Route B unchanged round trip) is **PASS**; see
[09-gate4-evidence.md](09-gate4-evidence.md).

## 1. Instruction boundaries (P0)

`routea/worker.py` reads the frozen ELF and the reviewed contract, resolves the
target function from `.symtab`, and disassembles exactly `st_size` bytes with
Capstone:

```json
{"name":"CWE121_..._badSink","entry":"0x4012b0","size":104,
 "instructions":[{"address":"0x4012b0","size":4,"mnemonic":"endbr64",...}, ...]}
```

For the candidate: 23 instructions from `0x4012b0` to `0x401317` (last `ret`).
The `call strcpy@plt` at `0x401304`–`0x401308` is present in the boundary list
and is not a patch point.

## 2. Trampoline plan (P0)

`plan_route_a()` takes the message and `max_valid_input_bytes` from the
`SecurityContract` (it does not hardcode them) and produces:

- detour at `0x4012c0`: `e9 3b 4d 00 00 90 90 90` (jmp to `0x406000`);
- R-- message at `0x405000`, 42 bytes from `contract.invalid_stderr`;
- R-X code at `0x406000`, 69 bytes: inline `strlen`, `cmp` with
  `max_valid_input_bytes`, valid jump to `0x4012f6`, invalid `fprintf(stderr,msg)`
  then `exit_group(1)` (syscall 231);
- no new relocations: existing `fprintf@plt` (`0x401120`) and `stderr`
  (`0x404080`) are reused;
- `strcpy@0x401304–0x401308` and harness `0x401256–0x4012af` untouched.

The plan JSON includes `detour`, `code_hex`, message hex, segment addresses and
the resolved symbols. `routeb/audit_route_a_layout.py` is an independent static
audit for the same plan.

## 3. LIEF build + edit manifest (P0/P1)

`build_patched_elf(..., scope_authorized=True)`:

1. adds one R-- `PT_LOAD` at `0x405000` (message);
2. adds one R-X `PT_LOAD` at `0x406000` (code), never W+X;
3. patches the detour at `0x4012c0`;
4. computes SHA-256 of original/patched;
5. audits segment vaddr/size/perms, original LOAD preservation, reloc counts,
   harness/strcpy bytes;
6. writes an edit manifest:

```json
{"schema_version":1,
 "original_sha256":"...", "patched_sha256":"...",
 "function":{"name":"...","entry":"0x4012b0","size":104},
 "edits":[{"kind":"overwrite","vaddr":"0x4012c0","size":8,
           "new_hex":"e93b4d0000909090","purpose":"detour to trampoline"}],
 "mappings":[{"vaddr":"0x405000","perm":"R","size":42,...},
             {"vaddr":"0x406000","perm":"R-X","size":69,...}],
 "relocations_added":[],
 "header_changes":{"original_size":26792,"patched_size":...},
 "scope_authorized":true,
 "audit":{"checks":{...},"new_segments":[...],"pass":true}}
```

`readelf -lW` remains the independent verifier: the code segment must be
`R E` and there must be no `W E` segment. The worker does not edit program
headers by hand; LIEF owns the layout, and the audit rejects any result that
does not preserve the original LOADs.

## 4. Status / what is blocked

| Item | Status |
|---|---|
| decode target function | implemented; 23 boundaries |
| trampoline plan | implemented; no candidate write |
| LIEF build | implemented but gated |
| edit manifest | schema implemented |
| candidate exact-stderr patch | **not applied — Gate 3 scope ruling missing** |
| LIEF build/readelf on candidate | not run for the same reason |

The Gate 3 decision still needs: allow new R--/R-X segments and file layout
change; define whether "two routes byte-identical" means bytes or behaviour;
allow `fprintf` to use `rdi`/`rsi`/`rax` (they are dead at the detour point).

## 5. Gate 4 paths (for acceptance)

- `routeb/probe_patcherex2.py` — Patcherex2 `ModifyFunctionPatch` round trip/fixed
- `routeb/verify.py` — synthetic `copy_name` oracle (not the Juliet manifest)
- `routeb/run_manifest_compare.py` — the Juliet 6-case comparator used for Gate 4
- `routeb/out/gate4/manifest-compare.json` — 6/6 PASS evidence
- [09-gate4-evidence.md](09-gate4-evidence.md) — environment + run link
