# 15 — To Member 3: run the Route A design's VM checks and deliver the guest evidence

**Recipients:** Member 3 (guest owner and executor), cc Member 4, Member 5, Lead
**From:** Lead, at Member 4's request (2026-10-22)
**Status:** **Request, not a result.** Gate 3 stays `CONDITIONALLY FEASIBLE`; gate 4
`NOT RUN`; the fixture stays `NOT FROZEN`. Nothing in this file is a pass, and no
oracle/manifest/frozen hash may change.
**Why you:** you own the only team guest, the snapshot/image evidence, and the isolation
wrapper (`jobwrap` / uid 1003 / netns). Member 4 has completed the Route A design and its
static tooling, but that tooling **cannot be validated on the host**: the project forbids host
ELF parsing/execution and the Lead's workspace host has no `D:\VMs`, so the guest is the only
place the tests and the candidate run. This is your existing handoff-11/12/14 role applied to
the Route A design that is now ready.

---

## 1. What Member 4 hands you (inputs)

| Item | Value |
|---|---|
| Branch | `member-4-routea-gate3` @ `7977bac` (base `origin/main` `33235f5`); not merged |
| Design doc | `docs/route-a/gate3-evidence-design.md` on that branch |
| Tooling | `routea/{byteaudit,manifest,audit,evidence,cave}.py`, `routea/README.md`, `scripts/routea_vm_check.sh` |
| Tests | `tests/test_routea_cave.py` (real ELF; guest only) and `tests/test_routea_manifest.py` (pure bytes) |
| Contract proposal | `fixtures/public/CWE121_src_char_declare_cpy_51b/contract.route-a-v1.json`, reviewed scope `ba33b4d070b8799b778a9ca1a257190079627bda72b5c42933edfebb0f5d8fc4` (pending M5 + Lead approval) |
| Frozen identity | original `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` (26,792 B); `valid.json` `17b2ee39…`; `invalid.json` `d493f370…`; manifest set `a564f039…` |
| Expected candidate | SHA-256 `f3cb9cbb503fb0d47ebebab7053fa2ed37b7876ffe5122157d31fefc783f9fa7` (26,792 B) |
| Host status of that tooling | only `py_compile` + the pure-bytes helper ran on the host; **no ELF parsed, no candidate executed, no test run on the host** |

---

## 2. What to run, in order

### A. Environment and eligibility (record raw output)

Guest fingerprint after revert, image chain manifest + its SHA-256, `pip freeze`, and versions
of `python3`, `pyelftools`, `capstone`, `readelf`, `objdump`. Also record `Seccomp:` from
`/proc/self/status` in the job context (the candidate uses an `exit_group` syscall; the writer
is libc `fprintf`, so seccomp is only for the termination path). If `readelf`/`objdump` is
missing, say so: the independent view becomes `not_run`, never assumed.

### B. Static half in the guest

```bash
git fetch <remote> member-4-routea-gate3
git checkout member-4-routea-gate3
bash scripts/routea_vm_check.sh
```

The script runs: environment check, frozen hashes, `pytest tests/test_routea_manifest.py
tests/test_routea_cave.py`, candidate build, full static audit, double-build reproducibility,
and the static evidence bundle. It **stops before executing the candidate**. Expected:
tests pass, candidate hash `f3cb9cbb…`, contract hash `ba33b4d0…`, bundle `SHA256SUMS` verifies.
If a test fails, deliver the full traceback plus `edit-manifest.json` and `audit.json`; do not
weaken or delete a test to get a green result.

### C. Runtime cave probe (inside the isolation controls)

On the built candidate: `0x401000`-`0x401fff` is mapped `r-xp`; memory at `0x4018e9` equals the
candidate file bytes; an instruction at the cave entry executes. Suggested breakpoints:
**`0x401304`** (site), **`0x4018e9`** (cave), **`0x401309`** (resume). Do **not** break at
`0x401308` — that is mid-instruction. Keep `info proc mappings`, `x/8i $pc`, and the file/memory
byte comparison with both hashes.

### D. Six frozen cases on the candidate (from a reverted snapshot, under the wrapper)

```bash
python3 routeb/run_manifest_repaired.py \
  --binary <job>/candidate.elf \
  --tests fixtures/public/CWE121_src_char_declare_cpy_51b/tests \
  --out var/jobs/m4-gate3/<run-id>/manifest-repaired.json
```

Record the candidate SHA-256 **before** and **after** the run. Expected per case:

| Case | argv[1] | rc | stdout | stderr |
|---|---|---|---|---|
| valid-empty | `""` | 0 | `"\n"` | empty |
| valid-smallest | `"A"` | 0 | `"A\n"` | empty |
| valid-typical | 10 × `A` | 0 | 10 × `A` + LF | empty |
| valid-maximum | 49 × `A` | 0 | 49 × `A` + LF | empty |
| invalid-first | 50 × `A` | 1 | empty | exactly `ERROR: input exceeds destination capacity\n` (42 bytes) |
| invalid-longer | 100 × `A` | 1 | empty | same 42 bytes |

Take `argv[1]` from the manifests, never retype it. A hash change during the run voids the run;
a crash is a failure, not the error path.

### E. Original V0 shape (same session)

Run `original.elf` on the same six cases through the same wrapper, after confirming its hash.
Expected documented shape: **4/6** (valid pass; invalid cases fail by design — the original
SIGSEGVs). This is V0 evidence, not a repaired-oracle pass.

### F. Evidence delivery

Keep raw logs, gdb output, per-case stdout/stderr/rc, wrapper attestation, and the snapshot
revert log under `var/jobs/`; deliver to Member 4 a hashed summary plus the bundle
`SHA256SUMS`/bundle hash. Do not report a gate label yourself: Member 4 verifies, Member 5
replays the build/hash commands, the Lead approves.

---

## 3. Hard isolation preconditions (handoff 10 §2, handoff 11 §2)

1. clean snapshot taken after the toolchain freeze, reverted before the run and between runs;
2. job-time egress blocked (netns created by the root wrapper before the uid drop);
3. unprivileged execution user (uid 1003), no passwordless sudo, `CapEff=0`,
   `NoNewPrivs=1`, evaluator unreadable; wrapper root-owned, fixed validated `execv` argv, no
   shell string, environment scrubbed.

If any of the three is missing, the six-case run is **NOT VERIFIED** even at 6/6. Your
install/isolation evidence package is due **2026-10-23 18:00** (handoff 11 §5); the Route A run
starts immediately after, or you report the concrete blocker before the deadline.

---

## 4. Boundaries (no exceptions)

- Never execute, parse, or build the candidate on the host; the guest only.
- Never change `valid.json`, `invalid.json`, the manifest set hash, or any oracle constant.
- Never relabel `not_run`/`NOT VERIFIED` as pass; the CI 6/6 on `origin/main` is supplementary,
  not gate 3.
- If the candidate hash differs from `f3cb9cbb…`, stop and report the difference; do not adjust
  the expected value.
- Do not overwrite `original.elf`; work on a copy inside the job directory.
- Snapshot-reset between runs so one run cannot alter a later oracle.

---

## 5. Report back (to Member 4, cc Lead)

Per item: `command` / `observed` / `raw evidence file` / `SHA-256` / `PASS` / `FAIL` /
`NOT VERIFIED`, with per-case rows rather than an aggregate. Sample header:

```text
guest fingerprint: <hash>   image chain: <manifest sha256>   snapshot: <name/id>
candidate sha256 before/after: f3cb9cbb… / f3cb9cbb…
static half: tests <n> passed, candidate f3cb9cbb…, bundle <sha256>
runtime probe: mapped <yes/no>, bytes match <yes/no>, cave executed <yes/no>
six cases: valid 4/4, invalid 2/2, byte-exact <yes/no>
isolation: revert <yes/no>, egress blocked <yes/no>, uid 1003 <yes/no>
blockers: <none or concrete fact>
```

---

## 6. Please confirm back

1. Guest access method for M4 (and M5 for gate 4): SSH/console, account, limits.
2. Snapshot name/id to be used and reverted to, and who resets it.
3. The wrapper's fixed invocation shape and whether it can host a `gdb` probe (if not, the
   equivalence path in handoff 12 §7.3 and the Lead's review).
4. Whether `pyelftools`, `capstone`, `readelf`, `objdump` are present in the guest; seccomp
   status.
5. The canonical `original.elf` source (`origin/main` blob vs the claimed `d1e0741`) and the
   path of the claimed "SHA256SUMS 24/24" file (currently not on `origin`).

**Confirmation log.** 2026-10-22 — Lead requests the guest-side Route A runs and evidence from
Member 3 at Member 4's request; nothing is relabelled; gate 3 stays `CONDITIONALLY FEASIBLE`,
gate 4 `NOT RUN`, fixture `NOT FROZEN`.
