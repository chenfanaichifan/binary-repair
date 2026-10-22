# 12 — M4 plan: independent verification of the gate-3 acceptance evidence

**From:** Member 4 (verification slice)
**To:** Lead (reviewer/committer), Member 3 (candidate/guest producer), Member 5 (gate 3 owner)
**Date:** 2026-10-22
**Status:** **PLAN ONLY — ALL ITEMS `not_run`.** No guest is available to this workspace and no
command in this plan has been executed. The committed original and the CI-built candidate now
exist on `origin/main` @ `33235f5` (handoff 13 §3) as **inputs only**; they are not gate-3
evidence, and nothing below has been measured by M4 yet. Nothing here is a result, a pass, or a
prediction of one.
**Basis:** handoff 13 (ownership handoff; Route A artifacts; review findings §5.1–§5.7),
handoff 11 §3 (six gate-3 pass items) and §6 (M1's assignment), handoff 09 §11 (tail-cave ruling
and interim status), handoff 10 §2 (three isolation preconditions),
`verification-design.md` §4.4 (frozen oracle), §5 (gate matrix), §6 (negative scenarios),
Tech Design §8 ("Added-code policy") and §9 (V1, V2, V3, V5).

---

## 1. Scope, boundaries, and the non-negotiable rules

**Question this plan answers:** does the delivered Route A candidate have the evidence gate 3
requires, checked by M4 from the candidate bytes and the guest rather than from M3's
conclusions?

**Producer/verifier separation.** M5 produces the Route A candidate and `routea/` code; M3
produces the guest environment, the run path, and the isolation evidence; M4 verifies
independently, keeps its own copies and logs, and does not reuse the producers' outputs as its
own measurement. Producer artifacts are read-only to M4. M4 never edits, re-runs into the same
paths, or overwrites producer artifacts; M4's results live in M4's own evidence directory and are
hashed.

**What this plan is not.** Gate 3 pass is feasibility evidence for fixture selection. It is
not V0–V5 acceptance, not a V3 pass, not repair proof, and not a second success rule. The
acceptance engine still decides outcomes from evidence (handoff 11 §3, §6).

**Hard rules used by every item below.**

1. Missing evidence, a missing artifact hash, or a missing isolation precondition is
   **`NOT VERIFIED`** — never `passed`, never "probably".
2. A check not executed in this environment is `not_run`, never a pass (AGENTS.md: missing is
   not passing).
3. Failure does not change the oracle. The frozen constants, `valid.json`, `invalid.json`, and
   the manifest set hash stay exactly as frozen (handoff 09 §7, §11.1).
4. Every execution of the candidate records the candidate SHA-256 **before** the run and
   re-checks it after the run. A hash change voids the run.
5. The six frozen cases are the only cases that count. Exploratory inputs may be run but never
   substitute for a case.
6. No claim is made from a single register snapshot, a single log line, or a tool's exit code
   alone.

### 1.1 Frozen values this plan checks against

| Value | Frozen value | Source |
|---|---|---|
| original ELF SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` | verification-design §4.4 |
| `valid.json` SHA-256 | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` | handoff 08; frozen test |
| `invalid.json` SHA-256 | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` | handoff 08; frozen test |
| manifest set SHA-256 | `a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78` | handoff 08 |
| `DEST_CAPACITY` | 50 | verification-design §4.4 |
| `MAX_VALID_LEN` | 49 | verification-design §4.4 |
| invalid path | rc 1, stdout empty, stderr exactly `ERROR: input exceeds destination capacity\n` (42 bytes), no crash | verification-design §4.4 |
| valid path | rc 0, stdout = `argv[1] + "\n"`, stderr empty | frozen `valid.json` |
| committed CI candidate SHA-256 | `f3cb9cbb503fb0d47ebebab7053fa2ed37b7876ffe5122157d31fefc783f9fa7` | handoff 13 §3; cross-check input only, never gate-3 evidence |
| gate-3 candidate SHA-256 | `<recorded at delivery/guest rebuild; never retyped from prose>` | I1 + I5 |

If any of the file hashes does not match, stop: the item is `NOT VERIFIED` under an identity
mismatch, and the run is not gate-3 evidence.

---

## 2. Inputs the producers must deliver before any item can start

No item proceeds on a partial delivery. Missing rows make the affected items `NOT VERIFIED`.

| # | Input | Required content | Affects |
|---|---|---|---|
| I1 | Final candidate ELF | path; SHA-256; delivered or guest-rebuilt byte-for-byte; the committed CI candidate `f3cb9cbb...` is a cross-check only and must be reproduced or the deviation recorded | all items |
| I2 | `original.elf` | path; SHA-256 must equal the frozen value | V0 shape; header/byte diffs |
| I3 | `tests/valid.json`, `tests/invalid.json` | delivered bytes; per-file hashes; manifest set hash | item 3 |
| I4 | Edit manifest | machine-readable; minimum fields in §2.1 | items 1, 2, six-item 2 |
| I5 | Re-apply recipe + tool versions | command/script that turns I2 into I1; hash of each tool/script; recorded deviation if byte-identical reproduction is not achieved | six-item 2 |
| I6 | Wrapper runbook | fixed invocation shape, root-owned path, hash/owner/mode, the attestation block it emits, and whether it can host M4's probe (§4.2) | items 1.2, 2.2, 3, 5 |
| I7 | Image + revert evidence | snapshot name/id, chain manifest file and its SHA-256, raw revert command/output/timestamp, guest fingerprint after revert | item 3, item 5 |
| I8 | Guest tool inventory | `readelf`, `objdump`, `gdb`, `python3` + `lief`, and the util-linux tools `unshare`/`runuser`/`setpriv` (versions, or exact absence report) | all execution/static items |
| I9 | Import evidence | `readelf -dW`/`--dyn-syms`/PLT facts for `write`/`fputs`/`fwrite`/`exit`, and guest syscall policy (seccomp) | item 2/3 risk, writer mechanism |

### 2.1 Minimum edit-manifest fields M4 needs

The manifest is M5/M3's artifact; M4 only reads it. Fields M4 will check against independent
measurements:

- `candidate_sha256`, `original_sha256`;
- `redirect`: `vaddr` (`0x401304`), original 5 bytes, written 5 bytes, target `vaddr`, displaced
  interval;
- `cave`: `vaddr_start` (`0x4018e9`), `vaddr_end` (`0x401fff`), `entry_vaddr`, added code/data
  intervals as **file offsets** and **vaddrs**, exact added bytes;
- `header_changes`: segment index + old/new `p_filesz`, `p_memsz`; any section-header change;
- `changed_file_intervals`: every edited file byte interval, inclusive offsets;
- `template_id` + parameters, `allowed_calls`;
- termination mechanism (`exit_group` / `exit@plt`) and writer mechanism (syscall / PLT);
- guest facts: CET state, seccomp policy, original PLT/dynsym writer facts.

If a claimed edit is not in `changed_file_intervals`, the candidate is rejected by the audit; if
the manifest omits a field, the dependent item is `NOT VERIFIED`. The committed
`routea/out/edit-manifest.json` is known to miss several of these fields (handoff 13 §5.2: the
displaced 5 bytes, the header before/after values with the program-header index, the complete
changed/added file intervals, the exact added bytes, writer/termination mechanism, tool
versions); the gate-3 record must cite a manifest that contains them, whether M5 extends it or
M4 emits a supplementary one from the recorded recipe.

### 2.2 Committed inputs M4 must re-measure (handoff 13 §3; inputs, not evidence)

These are cross-check values, not results. Each must be reproduced by M4's own measurement
before it counts.

| Committed fact | Value (source: handoff 13 §3, §5.1) |
|---|---|
| original ELF | 26,792 B, SHA-256 `aa428157...8393` |
| CI-built candidate | 26,792 B, SHA-256 `f3cb9cbb...f9fa7` (cross-check only) |
| redirect | 5 bytes at `0x401304`: `e8 c7 fd ff ff` -> `e8 e0 05 00 00`, target `0x4018e9` |
| return point | instruction after the 5-byte call begins at `0x401309` (the call occupies `0x401304`–`0x401308` inclusive; handoff 13 §5.1) |
| layout | patched R-X `PT_LOAD`: vaddr `0x401000`, offset `0x1000`, `p_filesz = p_memsz` `0x8e9` -> `0x1000`, flags `R E`; next `PT_LOAD` at vaddr/offset `0x402000`; file size `0x68a8 > 0x2000`; 13 program headers |
| cave | `0x4018e9`–`0x401fff`, 1,815 B, immediately after `.fini`; `.text` ends `0x4018dc`; no section covers it |
| added bytes | 72 bytes guard + 42-byte message = 114 added bytes at the cave |
| writer | `fprintf@plt` at `0x401120` and the `stderr` COPY relocation at `0x404080` already exist; no new import/relocation/GOT/PLT edit |
| imports | no `write`, `fputs`, `fwrite`, `exit`, `strlen`, or `strncpy` import (measured list in handoff 13 §3) |
| CI status | the CI `6/6` and CI layout audit are supplementary only; CI cannot satisfy gate-3 items 4–5 (handoff 13 §5.6) |

The contract writer authorization must match the measured mechanism: `fprintf` + `stderr` are
existing imports/objects, but handoff 09 §4.1 lists `write`/`fputs`/`fwrite`; M5's revision (or
a switch to a raw `write`/`exit_group`) is therefore an open contract dependency (handoff 13
§5.4), not something M4 may assume.

---

## 3. Evidence custody and execution controls

Raw M4 evidence goes under `var/jobs/m4-gate3/<run-id>/` (runtime artifacts, excluded from
source control per AGENTS.md); a hashed summary and the pass/fail table are reported to the Lead
for the record. The committed gate-3 record belongs in
`fixtures/public/CWE121_src_char_declare_cpy_51b/evidence/gate3/` as `gate3-record.md` plus its
`SHA256SUMS` (that directory's README defines the convention; raw logs stay in `var/jobs/` and
are cited by filename and hash). M4's own copies of I1–I3 are made first and hashed; the
producers' delivery is hashed separately for comparison.

Session header used for every guest session:

```bash
set -euo pipefail
RUN="gate3-m4-$(date -u +%Y%m%dT%H%M%SZ)"
JOB="/var/lib/binaryrepair/jobs/${RUN}"
EV="${JOB}/m4-evidence"
CAND="${JOB}/candidate.elf"; ORIG="${JOB}/original.elf"; TESTS="${JOB}/tests"
JOBWRAP="<root-owned wrapper path documented in I6>"
mkdir -p "$EV"
exec > >(tee -a "${EV}/12-session.log") 2>&1
set -x
sha256sum "$CAND" "$ORIG" "$TESTS/valid.json" "$TESTS/invalid.json" \
  > "${EV}/12-delivery-hashes.txt"
```

Every evidence file below is created inside `$EV`. At the end:

```bash
( cd "$EV" && sha256sum ./* > SHA256SUMS )
sha256sum "${EV}/SHA256SUMS" | tee "${EV}/12-evidence-bundle-hash.txt"
```

`12-session.log` is included; command arguments, working directory, guest fingerprint, UTC
start/end, and tool versions are part of the record.

**Isolation for every candidate execution** (including the probe runs in §4.2 and §5.2): the
run must satisfy §7. A run outside those controls is `NOT VERIFIED`, even if the observable is
correct.

---

## 4. Critical item 1 — cave loading and mapping (0x4018e9–0x401fff)

### 4.1 Static header and byte audit (no execution)

**Commands.**

```bash
for f in "$ORIG" "$CAND"; do
  b=$(basename "$f" .elf)
  readelf -hW  "$f" > "${EV}/12-${b}-elf-header.txt"
  readelf -lW  "$f" > "${EV}/12-${b}-program-headers.txt"
  readelf -SW  "$f" > "${EV}/12-${b}-section-headers.txt"
  readelf -dW  "$f" > "${EV}/12-${b}-dynamic.txt"
  readelf -rW  "$f" > "${EV}/12-${b}-relocations.txt"
  readelf --dyn-syms -W "$f" > "${EV}/12-${b}-dyn-syms.txt"
done
diff -u "${EV}/12-original-program-headers.txt" "${EV}/12-candidate-program-headers.txt" \
  > "${EV}/12-program-header-diff.txt" || true
diff -u "${EV}/12-original-dynamic.txt" "${EV}/12-candidate-dynamic.txt" \
  > "${EV}/12-dynamic-diff.txt" || true
diff -u "${EV}/12-original-relocations.txt" "${EV}/12-candidate-relocations.txt" \
  > "${EV}/12-relocation-diff.txt" || true
# Independent view (must agree with readelf on the changed segment):
python3 - "$ORIG" "$CAND" > "${EV}/12-lief-segments.txt" <<'PY'
import sys
try:
    import lief
except Exception as exc:            # missing LIEF makes the item NOT VERIFIED
    print("LIEF_UNAVAILABLE:", exc)
    raise SystemExit(3)
for path in sys.argv[1:]:
    b = lief.parse(path)
    print("==", path)
    for s in b.segments:
        print("PT", str(s.type), "flags", str(s.flags),
              "off", hex(s.file_offset), "vaddr", hex(s.virtual_address),
              "filesz", hex(s.physical_size), "memsz", hex(s.virtual_size),
              "align", hex(s.alignment))
PY
```

**Byte/residue audit.** M4 computes the file offset of the cave range from the **candidate**
program headers (the range is not file-backed in the original), and computes the changed program
header field bytes from its own `original`/`candidate` comparison — never from the edit manifest.
It then requires: same file size; the only program-header field differences are `p_filesz` and
`p_memsz` of exactly one `PT_LOAD`; every differing byte is in the detour interval, the cave
interval, or those header field bytes; the residue (all bytes outside those positions) hashes
identically. The edit manifest's claimed intervals are then cross-checked against this measured
set; an unlisted change is rejected, and a missing manifest field is `NOT VERIFIED`.

```bash
cmp -l "$ORIG" "$CAND" > "${EV}/12-byte-diff-raw.txt" || true
set +e
python3 - "$ORIG" "$CAND" "${EV}/12-edit-manifest.json" "${EV}/12-byte-diff-audit.txt" <<'PY'
import hashlib, json, struct, sys
o, c, man, out = sys.argv[1:5]
a, b = open(o, "rb").read(), open(c, "rb").read()
m = json.load(open(man))

def phdrs(buf):
    e_phoff, = struct.unpack_from("<Q", buf, 0x20)
    e_phentsize, e_phnum = struct.unpack_from("<HH", buf, 0x36)
    rows = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        t, f, o_, va, pa, fs, ms, al = struct.unpack_from("<IIQQQQQQ", buf, off)
        rows.append(dict(index=i, phdr_off=off, type=t, flags=f, offset=o_,
                         vaddr=va, filesz=fs, memsz=ms, align=al,
                         raw=(t, f, o_, va, pa, fs, ms, al)))
    return e_phoff, e_phentsize, rows

po, pc = phdrs(a), phdrs(b)
phoff_a, phent_a, sa = po; phoff_c, phent_c, sc = pc

# 1) program-header differences: only p_filesz/p_memsz of one segment.
field_names = ["p_type", "p_flags", "p_offset", "p_vaddr", "p_paddr",
               "p_filesz", "p_memsz", "p_align"]
changed_segments, header_bytes = {}, set()
for i, (x, y) in enumerate(zip(sa, sc)):
    if x["raw"] == y["raw"]:
        continue
    for f, (u, v) in enumerate(zip(x["raw"], y["raw"])):
        if u != v:
            changed_segments.setdefault(i, set()).add(field_names[f])
            # ELF64: p_filesz at +32, p_memsz at +40 within the phdr entry
            base = phoff_c + i * phent_c
            span = {"p_filesz": range(base + 32, base + 40),
                    "p_memsz": range(base + 40, base + 48)}.get(field_names[f], range(0))
            header_bytes |= set(span)
allowed_header = set(header_bytes)
if sa and sc and len(sa) != len(sc):
    raise SystemExit("program-header count changed")

# 2) cave range must not be file-backed in the original (tail extension, not remap).
def file_off(rows, vaddr):
    for s in rows:
        if s["type"] == 1 and s["vaddr"] <= vaddr < s["vaddr"] + s["filesz"]:
            return s["offset"] + (vaddr - s["vaddr"])
    raise SystemExit(f"vaddr {vaddr:#x} not file-backed")
try:
    orig_cave_end = max(s["offset"] + s["filesz"] for s in sa if s["type"] == 1
                        and s["vaddr"] <= int(m["cave"]["vaddr_start"], 16))
except ValueError:
    orig_cave_end = 0
cave_start = int(m["cave"]["vaddr_start"], 16); cave_end = int(m["cave"]["vaddr_end"], 16)
cave_off = file_off(sc, cave_start); cave_len = cave_end - cave_start + 1
detour_off = file_off(sc, int(m["redirect"]["vaddr"], 16))

# 3) allowed positions: detour, cave, and the independently computed header fields.
allowed = set(range(detour_off, detour_off + 5)) | set(range(cave_off, cave_off + cave_len))
allowed |= allowed_header
diffs = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
outside = [i for i in diffs if i not in allowed]
header_ok = (len(changed_segments) == 1 and
             all(f <= {"p_filesz", "p_memsz"} for f in changed_segments.values()))
detour_changed = any(detour_off <= i < detour_off + 5 for i in diffs)

def residue(buf):
    return hashlib.sha256(bytes(x for i, x in enumerate(buf) if i not in allowed)).hexdigest()

lines = [
    f"sizes original={len(a)} candidate={len(b)}",
    f"phnum original={len(sa)} candidate={len(sc)}",
    f"changed_segments={ {i: sorted(v) for i, v in changed_segments.items()} }",
    f"header_fields_ok={header_ok}",
    f"detour_changed={detour_changed}",
    f"cave_file_offsets=0x{cave_off:x}..0x{cave_off + cave_len - 1:x}",
    f"original_file_backed_cave_end<=0x{orig_cave_end:x}",
    f"diff_bytes={len(diffs)} outside_allowed={len(outside)}",
    "outside_sample=" + ",".join(hex(i) for i in outside[:40]),
    f"redirect_actual_hex={b[detour_off:detour_off + 5].hex()}",
    f"cave_actual_sha256={hashlib.sha256(b[cave_off:cave_off + cave_len]).hexdigest()}",
    f"residue_original={residue(a)}",
    f"residue_candidate={residue(b)}",
]
open(out, "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
if outside or not header_ok or not detour_changed or len(a) != len(b) or residue(a) != residue(b):
    raise SystemExit(2)
PY
printf 'audit_rc=%s\n' "$?" >> "${EV}/12-byte-diff-audit.txt"
set -e
```

M4 then compares `redirect_actual_hex` / `cave_actual_sha256` with the edit manifest's stated
bytes. A header field change other than `p_filesz`/`p_memsz` of one segment, or a change outside
the allowed positions, is a reject. Section headers are separate: they must be identical unless
the edit manifest records a change; a section-only change is never runtime-mapping evidence, and
a new `SHF_ALLOC`/`SHF_EXECINSTR` section is a reject. The before/after identities are
`12-delivery-hashes.txt` (original + candidate + both manifests) plus the residue hashes above.

**Reproducibility (six-item 2).** In a separate directory, re-apply the recorded I5 recipe to a
fresh copy of `original.elf`; the result must be byte-identical to the delivered candidate:

```bash
RAPP="${JOB}/reapply"
mkdir -p "$RAPP"; cp "$ORIG" "${RAPP}/original.elf"
# <I5 recipe command(s)>, with the working name changed to reapply-candidate.elf
sha256sum "${RAPP}/reapply-candidate.elf" > "${EV}/12-reapply-hash.txt"
cmp "$CAND" "${RAPP}/reapply-candidate.elf" > "${EV}/12-reapply-cmp.txt" 2>&1 || true
```

Byte-identical is a pass; a recorded deviation from I5 is acceptable only if the delivery states
it explicitly and the deviation is reproduced; otherwise six-item 2 is `NOT VERIFIED`.


Handoff 13 §3 records the expected shape (patched `PT_LOAD` vaddr `0x401000`, offset `0x1000`,
`p_filesz = p_memsz` `0x8e9` -> `0x1000`, flags `R E`, next `PT_LOAD` at `0x402000`, 13 program
headers, file size `0x68a8`). M4 must reproduce every value independently; the handoff values are
checks, not evidence.

**Expected observable.** Exactly one `PT_LOAD` changed: `p_filesz` increased so the file-backed
end is at least `0x401fff`, `p_memsz` increased consistently; `p_offset`, `p_vaddr`, `p_paddr`,
`p_align`, `p_flags` unchanged; same program-header count; no new `PT_LOAD`; no change to
`e_entry`; ELF file size unchanged; `p_offset ≡ p_vaddr (mod 0x1000)`; `p_offset + p_filesz <
file size` (handoff 11 §3 item 3); new segment end does not overlap the next loadable segment;
`p_memsz >= p_filesz`.
LIEF reports the same segment values as `readelf`. The diff audit reports zero differing bytes
outside allowed intervals and equal residue hashes. Dynamic entries, `dynsym`, relocations,
`.got`, `.got.plt`, and `.plt` are byte-identical; no new import; NX/`GNU_STACK` not
executable; `GNU_RELRO` unchanged; no `PF_W` segment has `PF_X`; no permission broadening;
canary/stack-protector artifacts unchanged.

**Cave-unused proof (static, on the original).**

```bash
readelf -SW "$ORIG" > "${EV}/12-cave-sections.txt"
readelf -sW "$ORIG" > "${EV}/12-cave-symbols.txt"
readelf -rW "$ORIG" > "${EV}/12-cave-relocations.txt"
readelf --debug-dump=frames "$ORIG" > "${EV}/12-cave-unwind.txt" 2>&1 || true
objdump -d -M intel "$ORIG" > "${EV}/12-orig-full-disasm.txt"
```

Expected: no section whose load address or file range intersects the cave; no symbol with
`st_value` in `[0x4018e9, 0x401fff]`; no relocation whose `r_offset` is in the range; no unwind
FDE covering the range; no branch/call target in the range in the original disassembly. The
original segment's file-backed end is `0x4018e9` (i.e. the range is not mapped today); record
that fact. "Zero bytes" is not evidence of unused storage; the reference audit plus the
runtime probe are.

**PASS criterion.** All header/byte/LIEF/reference checks as stated.

**REJECT criterion.** Any extra header change, a second changed segment, page-congruence
failure, overlap, permission/NX/RELRO/dynamic/relocation/import change, differing byte outside
allowed intervals, residue mismatch, LIEF/`readelf` disagreement, or a reference into the
range.

**NOT VERIFIED rule.** Missing candidate/original bytes, missing edit manifest, missing
`readelf`/`objdump`/LIEF, or an unreadable header diff makes this item `NOT VERIFIED`.

**Evidence files.** `12-{original,candidate}-{elf,program,section}-headers.txt`,
`12-program-header-diff.txt`, `12-dynamic-diff.txt`, `12-relocation-diff.txt`,
`12-lief-segments.txt`, `12-byte-diff-raw.txt`, `12-byte-diff-audit.txt`,
`12-cave-{sections,symbols,relocations,unwind}.txt`, `12-orig-full-disasm.txt`.

### 4.2 Runtime mapping and execution probe

**Requirement.** M4 must observe, on the running candidate: the range is mapped, permissions
are R-X, the memory bytes equal the candidate file bytes, and an instruction at the chosen cave
entry executes. The probe runs under §7 isolation. Preferred vehicle: the wrapper's documented
probe mode; if the wrapper cannot host a debugger, M4 uses an equivalent isolation harness
(§7.3) and the Lead reviews the equivalence. If neither is possible, this item is `NOT
VERIFIED`; a static audit alone cannot establish runtime mapping.

**Commands (template; placeholders are replaced from the edit manifest, not guessed).**

```bash
# File-side bytes and hash for the cave range:
python3 - "$CAND" "${EV}/12-cave-range-file.bin" 0x4018e9 0x401fff \
  > "${EV}/12-cave-range-file.json" <<'PY'
import hashlib, json, struct, sys
path, out, start, end = sys.argv[1], sys.argv[2], int(sys.argv[3], 16), int(sys.argv[4], 16)
buf = open(path, "rb").read()
e_phoff, = struct.unpack_from("<Q", buf, 0x20)
e_phentsize, e_phnum = struct.unpack_from("<HH", buf, 0x36)
for i in range(e_phnum):
    t, f, off, va, pa, fs, ms, al = struct.unpack_from("<IIQQQQQQ", buf, e_phoff + i * e_phentsize)
    if t == 1 and f & 1 and va <= start < va + fs:
        fo = off + (start - va); n = end - start + 1
        data = buf[fo:fo + n]
        print(json.dumps({"file_offset": hex(fo), "length": n,
                          "sha256": hashlib.sha256(data).hexdigest()}))
        open(out, "wb").write(data)
        break
PY

# gdb probe script (literal paths/addresses filled in):
cat > "${EV}/12-gdb-cave.gdb" <<GDB
set pagination off
set confirm off
set breakpoint pending on
break *0x401304
commands
  silent
  printf "SITE pc=%p rsp=%p rdi=%p rsi=%p rdx=%p rax=%p\n", \$pc, \$rsp, \$rdi, \$rsi, \$rdx, \$rax
  continue
end
break *<CAVE_ENTRY_VADDR>
commands
  silent
  printf "CAVE pc=%p rsp=%p\n", \$pc, \$rsp
  x/8i \$pc
  info proc mappings
  dump binary memory ${EV}/12-cave-memory.bin 0x4018e9 0x402000
  continue
end
run
GDB

# Invalid-first is 50 x 'A'; generate the bytes, do not retype the frozen literal.
ARG="$(printf 'A%.0s' {1..50})"
sudo unshare -n -- env -i PATH=/usr/bin:/bin HOME=/tmp TERM=dumb \
  runuser -u 1003 -- setpriv --no-new-privs \
  gdb -q -batch -x "${EV}/12-gdb-cave.gdb" \
  --args "$CAND" "$ARG" > "${EV}/12-cave-probe-gdb.txt" 2>&1 || true

cmp "${EV}/12-cave-range-file.bin" "${EV}/12-cave-memory.bin" \
  > "${EV}/12-cave-bytes-cmp.txt" 2>&1 || true
sha256sum "${EV}/12-cave-range-file.bin" "${EV}/12-cave-memory.bin" \
  > "${EV}/12-cave-bytes-sha256.txt"
```

**Expected observable.** `info proc mappings` contains one range with `r-xp` covering the whole
`0x4018e9`–`0x401fff` interval (mapping page end at least `0x402000`); the `CAVE` breakpoint hits
on the invalid case and `x/8i $pc` decodes real instructions (matching the edit manifest's added
bytes); `12-cave-bytes-cmp.txt` is empty and both SHA-256 values are equal; no SIGSEGV before
the cave entry.

**PASS criterion.** All four observables plus the §4.1 static audit pass.

**REJECT criterion.** Range not mapped or not executable; mapped permissions differ from R-X;
memory ≠ file bytes; cave breakpoint not reached; `x/i` shows undecodable bytes; a crash occurs
before the cave entry; the probe ran outside §7 controls.

**NOT VERIFIED rule.** No candidate, no debugger, no guest, no wrapper/probe path, or a run not
covered by §7 evidence ⇒ `NOT VERIFIED` (never pass).

**Evidence files.** `12-cave-range-file.bin`, `12-cave-memory.bin`, `12-cave-bytes-cmp.txt`,
`12-cave-bytes-sha256.txt`, `12-cave-probe-gdb.txt`, `12-cave-range-file.json`.

---

## 5. Critical item 2 — register and flag liveness at 0x401304

### 5.1 Static decode and dataflow (no execution)

```bash
objdump -d -M intel --start-address=0x4012a0 --stop-address=0x401320 "$ORIG" \
  > "${EV}/12-orig-disasm-site.txt"
objdump -d -M intel --start-address=0x4012a0 --stop-address=0x401320 "$CAND" \
  > "${EV}/12-cand-disasm-site.txt"
objdump -d -M intel --start-address=<CAVE_START> --stop-address=<CAVE_END> "$CAND" \
  > "${EV}/12-cand-disasm-cave.txt"
objdump -d -M intel --start-address=0x401256 --stop-address=0x4012b0 "$ORIG" \
  > "${EV}/12-orig-disasm-main-caller.txt"
```

**Expected observable / analysis M4 records.**

- Full instruction coverage of `0x4012b0`–`0x401317` with no gap or split; the 5-byte
  instruction at `0x401304` is the redirect and does not split a neighbour; its target is
  inside the cave and within rel32 range.
- The 5-byte call occupies `0x401304`–`0x401308` inclusive, so the valid path continues at
  **`0x401309`** (handoff 13 §5.1). Any text or script that uses `0x401308` as the return point
  breaks mid-instruction and can never hit; handoff 09 §4.1 entry 1 is already corrected.
- The instructions after `0x401309` up to the function's return are listed, with every register
  and flag read before write (true live-out, not a guess).
- Live-in at `0x401304` is stated per register: which values must be correct for the redirect,
  which the valid path must reproduce at `0x401309`, and which may be clobbered.
- Cave writes are listed: callee-saved registers `rbx`, `rbp`, `r12`–`r15` must not be
  clobbered, or must be save/restored with equal values at `0x401309`; `rsp` must be balanced;
  no `ret` without a matching `call` if a shadow stack is active; any indirect branch target
  needs `ENDBR64` if IBT is enforced; `syscall` clobbers `rcx`/`r11` (acceptable only if both
  are dead).
- Flag liveness: whether `0x401309`–`0x401317` reads flags before defining them. If yes, the
  cave must preserve the flags that code needs at return; if the path only reads flags left by
  the added `strcpy` call, the state after the call is the original state and is recorded as
  such.
- Stack alignment: `rsp % 16` at `0x401304` in the original (SysV requires 0 at the call
  instruction), at cave entry (redirect via `jmp` keeps `rsp`), at the cave's added `strcpy`
  call (must be 0), and at `0x401309` (must equal the original post-call `rsp`).

**PASS criterion (static part).** The decode covers the whole interval; every live register and
flag is classified with a reason; no unexplained write; the cave/trampoline preserves every
live value and every callee-saved register; alignment reasoning is consistent with the
observed `rsp` in §5.2.

**NOT VERIFIED (static part).** Missing candidate/original bytes, a missing disassembler, or an
undecodable interval makes the static part `NOT VERIFIED`; the item cannot pass on partial
coverage.

### 5.2 Dynamic trace

The trace runs under §7 isolation, on the final candidate, for **all six frozen cases** — a
single snapshot is not liveness proof. The gdb script breaks at `0x401304`, at `0x401309`
(valid path), at the cave entry, at the cave's added `strcpy` call, and at the function return
`0x401317`, printing `pc, rsp, rdi, rsi, rdx, rax, rbx, rbp, r12, r13, r14, r15, eflags`
(register-by-register, one line per hit; `$eflags`, or `$rflags` where the gdb build exposes
only that name). The original is traced on the four valid cases for a
baseline; the original on invalid input is the documented V0 crash and is recorded separately
in §6.3.

```bash
cat > "${EV}/12-gdb-liveness.gdb" <<GDB
set pagination off
set confirm off
set breakpoint pending on
break *0x401304
commands
  silent
  printf "SITE pc=%p rsp=%p rdi=%p rsi=%p rdx=%p rax=%p rbx=%p rbp=%p r12=%p r13=%p r14=%p r15=%p eflags=%08x\n", \$pc, \$rsp, \$rdi, \$rsi, \$rdx, \$rax, \$rbx, \$rbp, \$r12, \$r13, \$r14, \$r15, \$eflags
  continue
end
break *0x401309
commands
  silent
  printf "AFTER_COPY pc=%p rsp=%p rax=%p rdi=%p rsi=%p eflags=%08x\n", \$pc, \$rsp, \$rax, \$rdi, \$rsi, \$eflags
  continue
end
break *<CAVE_ENTRY_VADDR>
commands
  silent
  printf "CAVE pc=%p rsp=%p rdi=%p rsi=%p\n", \$pc, \$rsp, \$rdi, \$rsi
  continue
end
break *<CAVE_STRCPY_CALL_VADDR>
commands
  silent
  printf "CAVE_CALL pc=%p rsp=%p rdi=%p rsi=%p\n", \$pc, \$rsp, \$rdi, \$rsi
  continue
end
run
GDB
```

Run the script once per case, with the case's frozen `argv[1]`, e.g.:

```bash
for case in valid-empty valid-smallest valid-typical valid-maximum invalid-first invalid-longer; do
  ARG=$(python3 - "$TESTS" "$case" <<'PY'
import json, sys
tests, case = sys.argv[1], sys.argv[2]
for name in ("valid.json", "invalid.json"):
    for c in json.load(open(f"{tests}/{name}"))["tests"]:
        if c["id"] == case:
            sys.stdout.write(c["argv"][1])
PY
)
  sudo unshare -n -- env -i PATH=/usr/bin:/bin HOME=/tmp TERM=dumb \
    runuser -u 1003 -- setpriv --no-new-privs \
    gdb -q -batch -x "${EV}/12-gdb-liveness.gdb" \
    --args "$CAND" "$ARG" > "${EV}/12-trace-${case}.txt" 2>&1 || true
done
```

**Expected observable.** On all four valid cases: `SITE` lines show the same live values
(notably `rdi` = `&dest`, `rsi` = input data) across cases, `CAVE` and `CAVE_CALL` are reached,
`AFTER_COPY` is reached with `rax` = destination and `rsp` equal to the original trace's
post-call value; the function returns with the caller's frame intact. On the two invalid cases:
`CAVE` is reached, the writer/termination path runs, `AFTER_COPY` is **not** reached, and the
process exits 1 without a crash. Traces for the original on valid cases show the same live set
at `0x401304`.

**PASS criterion (explicit verdict).** The verdict is exactly one of:

- **`provable and preserved`** — static coverage plus traces on all six cases establish the
  live set, the callee-saved preservation, stack alignment at both `strcpy` call sites, and
  flag liveness; the cave clobbers only values proven dead.
- **`unknown`** — any coverage gap, any trace inconsistency, any clobber of a live value, any
  ambiguity about flags/alignment, or a single-snapshot-only basis.

`unknown` ⇒ the route outcome is `unsupported` under Tech Design §8; it is never a pass and the
candidate is not gate-3 evidence.

**REJECT criterion.** A proven clobber of a live value, broken stack balance, split
instruction, out-of-range redirect, or an invalid-path return to `main`.

**NOT VERIFIED rule.** No guest/debugger/candidate, or a trace outside §7 controls, or missing
original trace baseline ⇒ `NOT VERIFIED`.

**Evidence files.** `12-orig-disasm-site.txt`, `12-cand-disasm-site.txt`,
`12-cand-disasm-cave.txt`, `12-orig-disasm-main-caller.txt`, `12-trace-<case>.txt` (six),
`12-trace-original-<valid-case>.txt` (four), `12-liveness-verdict.md`.

---

## 6. Critical item 3 — six-case oracle and original V0

### 6.1 Isolation preconditions for the run (hard gate)

Before the six-case run, M4 records the §7 evidence **for the same session**: reverted snapshot,
no egress, unprivileged user 1003, wrapper conditions, guest fingerprint. A run without all
three preconditions is `NOT VERIFIED` and is not gate-3 evidence, even if it scores 6/6
(handoff 10 §2, handoff 11 §3 item 5).

### 6.2 Run the six frozen cases on the candidate

The candidate under test is I1: a guest-rebuilt candidate that reproduces the committed CI
candidate byte-for-byte, or a candidate whose deviation is recorded and reviewed (handoff 13
§5.5). The CI build and its `6/6` are supplementary only; they are not gate-3 evidence (handoff
13 §5.6). Candidate SHA-256 is recorded immediately before the run and re-checked after it.
`argv[1]` is taken from the frozen manifest by the extractor in §5.2, never retyped.

```bash
sha256sum "$CAND" > "${EV}/12-candidate-hash-before.txt"
set +e
for case in valid-empty valid-smallest valid-typical valid-maximum invalid-first invalid-longer; do
  ARG=$(python3 - "$TESTS" "$case" <<'PY'
import json, sys
tests, case = sys.argv[1], sys.argv[2]
for name in ("valid.json", "invalid.json"):
    for c in json.load(open(f"{tests}/{name}"))["tests"]:
        if c["id"] == case:
            sys.stdout.write(c["argv"][1])
PY
)
  # Wrapper invocation exactly as documented in I6. It must accept the job id, case id,
  # candidate path and argv[1] as an execv array, and run under the §7 controls.
  sudo -n "${JOBWRAP}" --job "$RUN" --case "$case" --elf "$CAND" --arg "$ARG" \
    > "${EV}/12-case-${case}-stdout.bin" \
    2> "${EV}/12-case-${case}-stderr.bin"
  printf '%s\n' "$?" > "${EV}/12-case-${case}-rc.txt"
done
set -e
sha256sum "$CAND" > "${EV}/12-candidate-hash-after.txt"
```

The wrapper's own fixed-shape run log for each invocation is captured from the path the I6
runbook documents; if the delivered wrapper emits no per-run log, the §7.1 attestation for this
session is the isolation record and item 5 depends on it.

**Expected observable (per case, recorded individually).**

| Case | argv[1] | rc | stdout bytes | stderr bytes | crash |
|---|---|---|---|---|---|
| `valid-empty` | `""` | 0 | `"\n"` | empty | no |
| `valid-smallest` | `"A"` | 0 | `"A\n"` | empty | no |
| `valid-typical` | 10 × `A` | 0 | 10 × `A` + `"\n"` | empty | no |
| `valid-maximum` | 49 × `A` | 0 | 49 × `A` + `"\n"` | empty | no |
| `invalid-first` | 50 × `A` | 1 | empty | exactly `ERROR: input exceeds destination capacity\n` (42 bytes) | no |
| `invalid-longer` | 100 × `A` | 1 | empty | same 42 bytes | no |

M4 compares bytes and exit code exactly, using the manifest's expected values (for valid stdout,
`argv[1] + "\n"`); it records a per-case row rather than an aggregate. `rc >= 128`, a reported
signal, a core file, or any timeout is a crash/failure. Candidate hash before = after; if not,
the run is void.

**PASS criterion.** All six cases match exactly, no crash, candidate hash stable, and §6.1
isolation evidence present.

**REJECT criterion.** Any case mismatch (report case id, expected and actual bytes/rc in hex),
any crash, any hash change. Do not adjust the oracle; diagnose the candidate.

**NOT VERIFIED rule.** Missing candidate, missing wrapper, a run outside §7 controls, a missing
snapshot/revert record, or an unrecorded candidate hash ⇒ `NOT VERIFIED`.

### 6.3 Original V0 shape (separate, same session)

Run `original.elf` on the same six cases through the same wrapper and controls, after
confirming its hash is `aa428157...`. Record every case; the documented V0 shape is **4/6**:
the four valid cases pass (rc 0, expected stdout), and the two invalid cases fail because the
original does not take the repaired error path (documented SIGSEGV; record the actual fact).
This is V0 evidence, not gate 3 and not a repaired-oracle pass. A different original hash stops
the run under identity failure.

**Evidence files.** `12-case-<id>-stdout.bin`, `12-case-<id>-stderr.bin`,
`12-case-<id>-rc.txt`, `12-case-<id>-expected.json` (optional dump), `12-six-case-summary.md`,
`12-original-v0-<id>-{stdout,stderr,rc}.bin/.txt`, `12-candidate-hash-before.txt`,
`12-candidate-hash-after.txt`, `12-isolation-attestation.txt`.

---

## 7. Isolation evidence (gate-3 item 5) and the probe controls

### 7.1 Three hard preconditions (handoff 10 §2, handoff 11 §2–§3)

1. **Clean snapshot after the toolchain freeze, used to reset runs.** M4 verifies: snapshot
   name/id, chain manifest file + its SHA-256, raw revert command/output/timestamp, post-revert
   guest fingerprint; and M4's own live fingerprint matches the frozen one. M4 does not accept
   "reverted" as a claim; a missing raw log or a fingerprint mismatch ⇒ `NOT VERIFIED`.
2. **Job-time egress blocked.** Netns created before dropping privileges; no usable interface;
   an egress attempt fails; raw output recorded.
3. **Unprivileged execution user without passwordless sudo.** uid 1003; `CapEff` = 0;
   `NoNewPrivs` = 1; `sudo -n true` fails; evaluator directory unreadable; setuid-root binary
   not reachable; wrapper is root-owned and not writable by 1003; 1003 cannot invoke the
   wrapper; fixed invocation shape with validated identifiers, argv as an `execv` array, no
   shell string; environment scrubbed (no secrets, no `LD_PRELOAD`); inherited fds closed;
   rlimits set (CPU/AS/FSIZE/NPROC/NOFILE, core = 0); umask set; `chdir` to the job dir.

Tracked, not hard-blocking: tools on a read-only mount, or the deferral is recorded (handoff 10
§2, handoff 11 §2).

**Commands (template).**

```bash
sudo unshare -n -- runuser -u 1003 -- setpriv --no-new-privs bash -c '
  id
  grep -E "^(Uid|Gid|CapEff|CapBnd|NoNewPrivs):" /proc/self/status
  ip addr; ip route
  sudo -n true; echo "sudo_rc=$?"
  python3 -c "import socket; socket.create_connection((\"192.0.2.1\", 9), timeout=2)"; echo "egress_rc=$?"
  ls -ld <EVALUATOR_PATH> 2>&1; echo "evaluator_rc=$?"
  ulimit -c; umask; env | grep -i '^LD_PRELOAD=' || true
' > "${EV}/12-isolation-attestation-run.txt" 2>&1 || true
stat -c '%U %G %a %n' "${JOBWRAP}" > "${EV}/12-wrapper-ownership.txt"
sha256sum "${JOBWRAP}" >> "${EV}/12-wrapper-ownership.txt"
```

**PASS criterion.** All §7.1 items hold for the same session as the six-case run, with raw
output and hashes. **NOT VERIFIED** if any item is missing; **REJECT** if 1003 can invoke the
wrapper, if the wrapper passes a shell string, or if egress/no-sudo checks succeed unexpectedly.

### 7.2 Wrapper conditions from handoff 11 §2

M4 checks the wrapper artifact (owner/mode/hash), its fixed interface, and its run log. It does
not accept M3's earlier isolation logs as its own run evidence; the attestation block must be
produced by M4's own invocation.

### 7.3 Probe-run equivalence (only if the wrapper cannot run gdb)

The runtime probe and liveness traces execute the candidate, so they need the same controls. If
the wrapper cannot host a debugger, M4 uses an equivalent harness (root-created netns, uid 1003,
no `NoNewPrivs`/capabilities, scrubbed env, rlimits/core 0, read-only job dir) and records the
full command and the same attestation block; the Lead reviews the equivalence **before** the
result is used. If equivalence is not reviewed, the runtime/liveness results are `NOT VERIFIED`.

---

## 8. The six-item gate-3 checklist (handoff 11 §3) and M4 mapping

All six are required; the three critical items above are necessary but not the whole gate.

| # | Handoff 11 §3 item | M4 check | Pass criterion | Status here |
|---|---|---|---|---|
| 1 | Separate candidate copy; original untouched; manifest hashes unchanged | §1.1 hashes; §3 delivery hashes | original `aa428157...`; `valid.json` `17b2ee39...`; `invalid.json` `d493f370...`; set `a564f039...`; producer artifacts unmodified | `not_run` |
| 2 | Candidate identity and reproducibility; edit manifest complete | §4.1 byte/residue diff; re-apply recipe I5 | candidate hash recorded before/after; recorded recipe reproduces identical candidate bytes (or deviation recorded); manifest lists all changed/added intervals, header fields, detour, displaced bytes | `not_run` |
| 3 | Structural audit (cave mapped R-X, page-congruent header extension, no overlap, `< file size`, no other header change, flags/NX/RELRO/canary/W^X, `readelf` + LIEF, no relocation/import/GOT/PLT edit) | §4.1 + §4.2 | all §4.1/§4.2 criteria pass | `not_run` |
| 4 | Six-case run 6/6, byte-exact, rc 0/1, no crash, exact 42-byte stderr, candidate hash recorded before run, reverted snapshot | §6 | all six rows match; hash stable; snapshot evidence | `not_run` |
| 5 | Isolation evidence for that run | §7 | all §7.1 conditions evidenced for the same session | `not_run` |
| 6 | Evidence bundle: raw outputs + hashes for every item | §3 | `SHA256SUMS` verified; session log included; every claimed result traces to a raw file | `not_run` |

**Gate-3 recommendation labels (M4 issues exactly one):**

- **`GATE 3 PASS`** — all six items `PASS`, including all three critical items.
- **`GATE 3 FAIL`** — any item `FAIL`; report the concrete failing fact.
- **`GATE 3 NOT VERIFIED`** — any item `NOT VERIFIED`; gate 3 stays open (work status at most
  `CONDITIONALLY FEASIBLE`). Never shown as pass.

Gate 3 pass remains fixture-selection feasibility, not V0–V5 acceptance, V3, or repair proof;
the acceptance engine decides outcomes from evidence.

---

## 9. What cannot be verified in this environment (and now)

No guest is available to this workspace; the committed `original.elf` and CI candidate exist on
`origin/main` @ `33235f5` but are inputs only, no M3 isolation/guest delivery has arrived, and no
command in this plan has been run by M4. Static items could be executed later on own copies of
the committed blobs, but nothing here is measured yet. Therefore:

| Item | Requires | Status now |
|---|---|---|
| 1. separate copy / identity hashes | committed blobs on `origin/main`@`33235f5` + own copies | `not_run` |
| 2. reproducibility (re-apply recipe) | committed candidate + I5 recipe + toolchain | `not_run` |
| 3. structural header/byte audit | committed candidate/original + `readelf` + LIEF | `not_run` |
| 3b. runtime cave probe | guest + isolation + debugger | `not_run` |
| 4. six-case run | guest + snapshot + wrapper + I1–I3 | `not_run` |
| 5. isolation evidence | guest + hypervisor/revert raw logs | `not_run` |
| 6. evidence bundle | results of items 1–5 | `not_run` |
| Critical liveness (static + dynamic) | candidate/original bytes + guest + debugger | `not_run` |
| Original V0 shape (4/6) | `original.elf` + guest | `not_run` |

Only frozen values from documents are quoted above; none is a measurement of the delivered
candidate. Any result reported before the guest exists and the committed artifacts have been
independently measured would be fabricated and is prohibited.

---

## 10. Reporting format and rules

- M4 reports per item: `PASS` / `FAIL` / `NOT VERIFIED`, with the raw evidence filename(s),
  the command actually run, the observed bytes/values, and the SHA-256 of each artifact.
- Per-case rows for the six cases, not an aggregate. For mismatches, both expected and actual
  bytes are shown in hex with a case id.
- No oracle, manifest, or frozen-constant change, ever. A failing candidate is diagnosed; a
  placement/encoding limitation is reported as `unsupported` with the concrete fact (handoff 09
  §5, handoff 11 §3).
- Acceptance outcomes remain the acceptance engine's decision; M4's confirmation is evidence,
  not a second success rule (handoff 11 §6).
- Raw evidence stays under `var/jobs/m4-gate3/<run-id>/`; the committed record cites hashes and
  the evidence-bundle hash. `var/jobs/` is excluded from source control.

---

## 11. Open dependencies to resolve before the run

1. **Delivery path and hashes** (I1–I4): where M3 places the candidate, original, tests, edit
   manifest, and re-apply recipe, plus their hashes.
2. **Wrapper runbook** (I6): exact fixed invocation, attestation block, and whether a probe/gdb
   mode exists; otherwise Lead approval of the equivalent harness in §7.3.
3. **Image/revert evidence** (I7): chain manifest, snapshot id, raw revert log; M4's guest
   fingerprint comparison.
4. **Guest and tool access** (I8): account/SSH method; `readelf`, `objdump`, `gdb`, `python3` +
   `lief` availability and versions. A missing debugger blocks the dynamic liveness and runtime
   cave observables (they become `NOT VERIFIED`, not pass).
5. **Cave entry and call addresses** from the edit manifest (needed to instantiate the gdb
   scripts; not typed from prose).
6. **Import/PLT facts** (I9) and guest seccomp policy, so a syscall-based writer is either
   confirmed feasible or the limiting fact is recorded.
7. **Contract writer authorization** (handoff 13 §5.4): the committed probe uses `fprintf@plt` +
   the `stderr` COPY relocation, while handoff 09 §4.1 lists `write`/`fputs`/`fwrite`. M5's
   contract revision must authorize the measured mechanism (or the repair must switch to a raw
   `write`/`exit_group` with the guest seccomp result). M4 may not treat the probe's
   `allowed_calls=[fprintf,...]` as an approved contract.
8. **Contract text off-by-one** (handoff 13 §5.1): the redirect's valid-path return is
   `0x401309`, not `0x401308`; the contract revision and every record/script must use the
   corrected value before freeze (handoff 09 §4.1 entry 1 is already corrected).
9. **Committed record and independent replay** (handoff 13 §7): the `gate3-record.md` +
   `SHA256SUMS` bundle is committed for review; M5 replays the build/hash commands and the Lead
   approves. M4 does not approve its own evidence.

---

## 12. Confirmation log

- 2026-10-22 — M4 created this plan at the Lead's direction (M1 assignment recorded in handoff
  11 §6): independent verification of the three critical gate-3 items plus all six gate-3 pass
  items. Status: **plan only, all items `not_run`**; no guest available in this workspace and no
  M3 isolation/guest delivery yet. No result, pass, or unsupported conclusion is claimed.
- 2026-10-22 — revised against handoff 13 (ownership moved to M4; committed original and
  CI candidate on `origin/main` @ `33235f5` are inputs only; return point corrected to
  `0x401309`; committed edit-manifest gaps and writer/contract dependency recorded). Nothing was
  executed and no status changed.
