# Route B/provider executor bundle

- mode: `fixed`
- function: `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink`
- original: `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`
- candidate: `208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717`
- audit_profile: `route_b_recompile`; static audit: `pass` (same_file_size=true; 4 PT_LOAD unchanged, 0 added)
- reproducibility: `measured` (2 runs, byte-identical)
- runtime manifest: `measured` (6/6, repaired_pass=true)
- executor_sha256: `4f07217583c00c3a02ceaa8294eb330270a0ba7ba9ec03ce3aa4fbcfa831b05d`
- probe_sha256: `d6e65427d3ee9d09050b92249e0a0e63a09f83ff9178a809588ecdafb5cfb96b`
- replacement_c_sha256: `a2e4ff8f5071c20328f977153775c8dc7d8bf8a9f867278a5de2d48b81ccc90e`

## v6 candidate fix (supersedes v5 candidate 63fcafa6)

The v5 candidate `63fcafa6ed01…6d01` failed V2 `extra_load_segments_within_contract`
(2 added PT_LOAD, contract `authorized_edits[2]` allows at most one R-X fallback).
The v6 `patch_function` (in `executor/probe_patcherex2.py`) now reuses the
verified-unused tail of the existing R-X PT_LOAD instead of carving new segments:

1. extend the R-X PT_LOAD `p_filesz`/`p_memsz` from `0x8e9` to `0x1000`
   (`authorized_edits[1]`, tail ending at `0x401fff`);
2. register that tail as RX free space via
   `p.allocation_manager.add_free_space(0x4018e9, 0x716, "RX")`;
3. let `ModifyFunctionPatch` place the recompiled `badSink` body + data there.

Result: `same_program_header_count = true`, `extra_load_segment_count = 0`,
`program_header_order_changed = false`, `relocations_added = 0`, file size
unchanged (26792 B). V2 interface 16/16 passed (see `v2-routeb-fixed.json`).
V3 behaviour 6/6 (`repaired_pass=true`). V5 reproducibility byte-identical ×2.

The executor main file `routeb/executor.py` is unchanged (sha256
`4f072175…b05d`); only `routeb/probe_patcherex2.py` changed (sha256
`d6e65427…b96b`).
