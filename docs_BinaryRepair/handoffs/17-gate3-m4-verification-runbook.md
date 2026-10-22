# 17 — Gate 3 six-item verification runbook (M4, after M3's isolated run)

**Recipients:** Member 4 (executor/verifier), cc Member 3, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** **runbook — nothing here has been run yet.** Gate 3 stays `CONDITIONALLY FEASIBLE`
until M3's isolated run and M4's independent checks produce the six items. Missing evidence,
missing hashes, or a missing isolation precondition is `NOT VERIFIED`, never a pass.
**Canonical subject:** `origin/main` `1826505`; candidate `c4a159…aa82`; contract `24bfe568…4e37`;
original `aa428157…8393`; `valid.json` `17b2ee39…e76`; `invalid.json` `d493f370…90d`; manifest
set `a564f039…3a78`.
**Role split:** VMer owns the VM console (snapshot/power-on) and is **a separate window of the
same operator**, not M4 and not a fourth person; M3 prepares/executes inside the guest and
collects raw evidence; M4 verifies independently with its own copies and does not approve its
own evidence (handoff 13/16).

Rules: never edit the oracle/manifests/frozen hashes; never reuse M3's conclusions as M4's own
measurement; record the candidate SHA-256 before **and** after every execution; keep raw logs
under `var/jobs/m4-gate3/<run-id>/` (not committed) and cite them by filename + SHA-256.

---

## 0. Session header (run first, once)

```bash
set -euo pipefail
RUN="gate3-m4-$(date -u +%Y%m%dT%H%M%SZ)"
JOB="/var/lib/binaryrepair/jobs/${RUN}"
EV="${JOB}/m4-evidence"
CAND="${JOB}/candidate.elf"; ORIG="${JOB}/original.elf"; TESTS="${JOB}/tests"
M3_EV="${JOB}/m3-evidence"          # M3's raw output, read-only to M4
mkdir -p "$EV"
exec > >(tee -a "${EV}/17-session.log") 2>&1
set -x
date -u; uname -a; python3 --version; readelf --version | head -1
git -C <repo> log --oneline -1      # expect 1826505
```

Copy `original.elf`, `tests/`, candidate and the schema-2 manifest from M3's delivery into a
read-only M4 directory first; hash everything (`sha256sum`).

---

## 1. Item 1 — identity / separate copy / frozen tests unchanged

```bash
sha256sum "$ORIG" "$TESTS/valid.json" "$TESTS/invalid.json" "$CAND"
python3 - "$TESTS" <<'PY'
import hashlib, json, sys
tests = sys.argv[1]
v = hashlib.sha256(open(f"{tests}/valid.json","rb").read()).hexdigest()
i = hashlib.sha256(open(f"{tests}/invalid.json","rb").read()).hexdigest()
payload = {"case_id":"CWE121_src_char_declare_cpy_51b","manifests":[
    {"name":"invalid.json","sha256":i},{"name":"valid.json","sha256":v}],
    "original_sha256":"aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393",
    "schema_version":1}
canon = json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=False)
print("valid", v); print("invalid", i)
print("set", hashlib.sha256(canon.encode()).hexdigest())
PY
python3 - "$CONTRACT" <<'PY'
import json, sys
sys.path.insert(0, "<repo>")
from app.domain.contracts import contract_sha256
print("contract", contract_sha256(json.load(open(sys.argv[1]))))
PY
```

Expected: `aa428157…`, `17b2ee39…`, `d493f370…`, `a564f039…`, candidate `c4a159…`, contract
`24bfe568…`. Archive provenance is pinned (handoff 16 §8/§9): GitHub archive of commit `1826505`,
`https://codeload.github.com/chenfanaichifan/binary-repair/zip/1826505`,
`D:\BinRepair\.tmp\binrepair-main-1826505.zip`, downloaded 2026-10-22 18:30:24 +08, 471,658 B,
SHA-256 `b0f4a18414e3887581769dd010063e7860abc62c8359f4051c4367573c03f61f`, no `.git`; commit id +
archive hash + per-file hashes are the provenance. The fallback packaging hash is not required.

---

## 2. Item 2 — candidate identity, reproducibility, complete manifest

```bash
# primary recipe from the committed route-a delivery zip
unzip -o <repo>/dist/m5-routea-c4a159-2026-10-22.zip regen_c4a159.py -d "$EV/recipe"
python3 "$EV/recipe/regen_c4a159.py" "$ORIG" "$EV/repro-c4a159.elf"
sha256sum "$EV/repro-c4a159.elf"          # must equal c4a159…aa82
cmp "$CAND" "$EV/repro-c4a159.elf" && echo "byte-identical"

# secondary recipe (pyelftools+capstone, no LIEF)
python3 -m routea.cave build --elf "$ORIG" \
  --contract fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json \
  --cave 0x4018e9 --cave-size 1815 --out "$EV/repro-cli.elf" \
  --manifest "$EV/repro-cli-manifest.json" --scope-authorized
sha256sum "$EV/repro-cli.elf"
```

Manifest completeness (schema 2): `displaced.original_hex` = `e8c7fdffff`; `added` has code
71 B (sha256 `cd032694…`) and data 42 B at `0x401930`; `intervals.changed` / `intervals.added`;
`header_changes.rx_load` old/new `0x8e9`→`0x1000`, phdr file offset `0xe8`, page-congruent,
no-overlap; `writer` = `write(2,msg,42)` syscall; `termination` = `exit_group(1)`;
`tool_versions`. Recompute the byte diff and require every changed offset to be inside the
declared intervals (displaced 5 bytes, added 113 bytes, header field bytes) with equal residue
hashes — M5's committed `audit.json` is not a substitute.

---

## 3. Item 3 — structural audit (static + runtime cave probe)

**Static views (independent):**

```bash
for f in "$ORIG" "$CAND"; do
  b=$(basename "$f" .elf)
  readelf -hW "$f" > "$EV/17-$b-hdr.txt"; readelf -lW "$f" > "$EV/17-$b-phdr.txt"
  readelf -SW "$f" > "$EV/17-$b-shdr.txt"; readelf -rW "$f" > "$EV/17-$b-reloc.txt"
  readelf -dW "$f" > "$EV/17-$b-dyn.txt"; readelf --dyn-syms -W "$f" > "$EV/17-$b-dynsym.txt"
  objdump -d -M intel "$f" > "$EV/17-$b-disasm.txt"
done
# LIEF 1.0.0 independent view: segments, flags, GNU_STACK NX, GNU_RELRO, dynamic imports
python3 - "$ORIG" "$CAND" > "$EV/17-lief-view.txt" <<'PY'
import sys, lief
for path in sys.argv[1:]:
    b = lief.parse(path)
    print("==", path)
    for s in b.segments:
        print("PT", str(s.type), str(s.flags), hex(s.file_offset), hex(s.virtual_address),
              hex(s.physical_size), hex(s.virtual_size), hex(s.alignment))
    print("entry", hex(b.entrypoint), "header_count", len(b.header.program_header_list))
    print("imports", sorted(s.name for s in b.dynamic_symbols if s.imported))
PY
```

Checks: exactly one changed `PT_LOAD` (`PT_LOAD[3]`, vaddr `0x401000`): `p_offset/p_vaddr/
p_paddr/p_flags/p_align` unchanged, `p_filesz = p_memsz = 0x1000`, page-congruent, no overlap
with `PT_LOAD[4]` at `0x402000`, file size `0x68a8`; `e_entry 0x401170` unchanged; no W+X;
`GNU_STACK` still non-exec; `GNU_RELRO` unchanged; dynamic/`.dynsym`/`.dynstr`/`.rela*`/`.got*`/
`.plt*` byte-identical; no new import; cave range `0x4018e9-0x401fff` covered by no section,
symbol, relocation, or incoming branch/RIP-relative reference; original filler zero.

**Runtime cave probe (guest + isolation):**

```bash
cat > "$EV/17-cave.gdb" <<'GDB'
set pagination off
set confirm off
break *0x401304
commands
 silent
 printf "SITE pc=%p rsp=%p rdi=%p rsi=%p rdx=%p rax=%p\n", $pc,$rsp,$rdi,$rsi,$rdx,$rax
 continue
end
break *0x4018e9
commands
 silent
 printf "CAVE pc=%p rsp=%p\n", $pc,$rsp
 x/12i $pc
 info proc mappings
 dump binary memory <EV>/17-cave-memory.bin 0x4018e9 0x402000
 continue
end
run
GDB
gdb -q -batch -x "$EV/17-cave.gdb" --args "$CAND" "AAAA" > "$EV/17-cave-probe.txt" 2>&1 || true
```

Expected: mapping `r-xp` covers `0x401000-0x401fff`; cave memory equals candidate file bytes
(dump the file range with python and `cmp`); the cave entry executes; no crash before entry.
Breakpoints: **`0x401304`**, **`0x4018e9`**, **`0x401309`** (never `0x401308`). Liveness traces:
break at `0x401304`, `0x4018e9`, `0x401309`, and `0x401317`, print `pc,rsp,rdi,rsi,rdx,rax,rbx,
rbp,r12-r15,eflags`, one line per hit, on all six cases; verdict `provable and preserved` or
`unknown` (`unknown` ⇒ unsupported, never pass).

---

## 4. Item 4 — six frozen cases + original V0 (reverted snapshot, wrapper)

Candidate hash before; per case run the wrapper (case id from the frozen manifest only):

```bash
sha256sum "$CAND" > "$EV/17-candidate-before.txt"
for case in valid-empty valid-smallest valid-typical valid-maximum invalid-first invalid-longer; do
  sudo /usr/local/sbin/jobwrap gate3 patched "$case" > "$EV/17-$case.out" 2>&1 || true
done
sha256sum "$CAND" > "$EV/17-candidate-after.txt"
sudo /usr/local/sbin/jobwrap gate3 original all > "$EV/17-original-v0.out" 2>&1 || true
```

Expected per case: valid rc 0 / stdout `argv[1]+LF` / stderr empty; invalid rc 1 / stdout empty /
stderr exactly `ERROR: input exceeds destination capacity\n` (42 B) / no crash. `original` shape:
4/6 (invalid cases fail by design). Copy the wrapper's `summary.json` and per-case `.stdout` /
`.stderr` raw files; verify bytes with `cmp`/hex, not prose. Candidate hash before = after; a
change voids the run.

---

## 5. Item 5 — isolation evidence for that run

Record for the **same session**: new `gate3-harness` chain manifest + its SHA-256 (powered off),
guest fingerprint after revert, raw revert command/output/timestamp; wrapper hash/owner/mode;
attestation showing uid 1003, `CapEff=0`, `NoNewPrivs=1`, no usable egress, `sudo -n true`
fails, evaluator unreadable, fixed `execv` argv (no shell), scrubbed env, rlimits/core=0;
`Seccomp: 0` with no filter added. A run outside these controls is `NOT VERIFIED` even at 6/6.
VMer is **a separate window of the same operator** (not M4, not a fourth person); the snapshot
record names VMer, and M4 only verifies. Actual test counts, per-case rows, candidate
before/after hashes and the chain-manifest/fingerprint/revert/uid-1003/no-egress evidence are
**pending from the VMer window** — record actual values only, never a target count.

---

## 6. Item 6 — bundle, record, and hand-off

- Commit `docs/route-a/gate3-record.md` updated with per-item `PASS` / `FAIL` / `NOT VERIFIED`,
  the command actually run, observed values, and the raw-evidence filename + SHA-256;
- `docs/route-a/SHA256SUMS` for the committed record files; bundle hash recorded in the log;
- hand the record to M5 for the build/hash replay (unless the Lead has explicitly waived it) and
  to the Lead for approval. M4 never signs its own evidence as approved.

---

## Appendix A — V4 calibration plan (after gate 3, gate 6 support)

Gate 6 stays **partial** until the symbolic half exists; a smoke test is not a pass.

1. Load `original.elf` in angr with the recorded base address, stack setup, and `argv[1]`
   symbolically, using the harness entry `0x401256` / sink `0x4012b0`.
2. Calibrate on known unsafe input (50/100 bytes): the exploration must find the OOB write
   / saved-return overwrite; record the path and the counterexample.
3. Then run the bounded property on the original for the defined input domain with an explicit
   step/time budget; record `active/deadend/found` counts and the budget.
4. Report `unknown`/timeout/incomplete exploration as `inconclusive`, never as detection. Only a
   completed bounded exploration with a recorded property result counts, and it is still V4
   evidence, not V3 acceptance.

## Appendix B — result row template

```text
item=<1..6> status=<PASS|FAIL|NOT VERIFIED> command=<...>
observed=<hash|rc|bytes> evidence=<file> sha256=<...>
reason=<only for FAIL/NOT VERIFIED>
```

---

## 7. M5 patch review — status and scope (2026-10-22)

M5 reviewed M4's implementation patch in `docs/route-b/20-m4-patch-review.md`
(main `766499e`): **CHANGES REQUESTED — not approved, not canonical, not gate-3 evidence.**
The reviewed patch targets the superseded `f3cb9cbb…`/`ba33b4d0…` values and has six blocking
findings: (B1) old contract instead of `24bfe568…`; (B2) old candidate/code shape instead of
`c4a159…`; (B3) `manifest.py` enum extraction crashes on pyelftools 0.33 strings; (B4)
`inside_rx_load`/`cave_within_memsz` reject the authorized page-tail cave; (B5) the unpatched-
binary test asserts the wrong byte-audit result; (B6) `routea_vm_check.sh` hardcodes the old
identity. On the review host `tests/test_routea_manifest.py` passed 9/9 and
`tests/test_routea_cave.py` failed 7 tests, consistent with M4's "no ELF tests ran on the host"
caveat.

**This runbook does not depend on that patch.** It verifies main's canonical `c4a159…` /
`24bfe568…` tooling, which is the only Gate 3 subject. The M4 branch
`member-4-routea-gate3` stays superseded unless M4 either (a) retargets it to main
`1826505`/`ad1a1f8` with `24bfe568…`/`c4a159…`, fixes B1–B6, reruns both test files in the
guest and resubmits the new patch hash/base for M5 re-review, or (b) formally withdraws it as
superseded and keeps only the independent-verification role. **Decision pending with the Lead.**
Nothing here claims the patch is approved, and no second candidate or contract is admitted.

