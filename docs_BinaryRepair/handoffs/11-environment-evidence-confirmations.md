# 11 — Environment evidence confirmations and gate 3 pass criteria

**Recipient:** Member 3 (execution), Member 4 (verification), Member 5 (gate 3)
**From:** Lead
**Date:** 2026-10-22
**Answers:** (1) chained image manifest accepted with a canonical format; (2) root wrapper +
setuid 1003 accepted as the unprivileged execution user, under conditions; (3) gate 3 pass =
six items, not just 6/6 + mapping.

---

## 1. Image hash: "base + 3 deltas + vmsd" chain — ACCEPTED with a canonical manifest

A chain manifest is acceptable as the guest image identity. Conditions:

- hash the chain **powered off** at the named snapshot, never while running or paused;
- one line per artifact: role (`base`, `delta-1`, `delta-2`, `delta-3`, `vmsd`, `vmx`),
  relative filename, size, SHA-256, in chain order; record snapshot name/id, hypervisor
  name/version, creation time, and `df`/free space;
- write a `SHA256SUMS`-style file and record **its** SHA-256 as the manifest hash;
- **content identity = base + deltas**; `.vmsd` / `.vmx` are recorded metadata, not identity.
  A new snapshot rewrites them, so any new snapshot is a new image record;
- additionally record the **guest-visible fingerprint after revert**: `/etc/os-release`,
  `uname -a`, `pip freeze` (55 packages), every tool version, and the toolchain snapshot
  name. A reviewer must be able to verify a reverted guest without the hypervisor files;
- V5 wording must say "guest image chain hash + guest fingerprint", not a single image hash.

## 2. Root wrapper + setuid 1003 — ACCEPTED as "unprivileged execution user", with conditions

The requirement is about the **job process**, not about who spawns it. Accept the pattern
"root calls `jobwrap`, which drops to uid 1003", provided:

- **1003 cannot invoke the wrapper.** It is root-invoked only (root service/controller). A
  wrapper callable by 1003 with arguments is an escalation surface and is rejected;
- the wrapper is root-owned and not writable by 1003; it takes a **fixed invocation shape**
  with validated identifiers (job id, case id, ELF path under the job dir) and passes
  `argv[1]` from the frozen manifest as an `execv` array — no shell string, no
  user-controlled path, no arbitrary command;
- before `exec`: create/join the network namespace with no egress, `setgroups`/`initgroups`,
  set gid then uid 1003, `PR_SET_NO_NEW_PRIVS`, clear the capability bounding set, close
  inherited fds, set umask, set rlimits (CPU/AS/FSIZE/NPROC/NOFILE, core = 0), `chdir` to the
  job dir;
- scrub the environment: fixed `PATH`, no `LD_PRELOAD`, and **no secrets** (the DeepSeek API
  key must never reach the guest, the wrapper, or the job);
- verify from inside the job: `id` = 1003; `/proc/self/status` `Uid`/`Gid` = 1003,
  `CapEff` = 0, `NoNewPrivs` = 1; `ip addr` shows no usable interface; an egress attempt
  fails; `sudo -n true` fails; the evaluator directory is unreadable; a setuid-root binary is
  not reachable;
- host-side SSH/control still works from outside the job netns (control-plane check);
- record raw output for every check. If 1003 can call the wrapper, or the wrapper passes a
  shell string, the isolation claim is rejected.

## 3. Gate 3 pass criteria — six items, all required

`6/6 + segment mapping + file size + old/new hash audit` is necessary but **not sufficient**.
Gate 3 passes only when all six exist:

1. **Separate candidate copy.** Original untouched: `original.elf` SHA-256 still
   `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`; `valid.json` /
   `invalid.json` hashes unchanged.
2. **Candidate identity and reproducibility.** Candidate SHA-256 recorded; re-applying the
   recorded edit plan to the original produces identical candidate bytes (or the deviation is
   recorded); the edit manifest lists changed/added intervals, header fields, detour, and
   displaced bytes.
3. **Structural audit.** Cave mapped R-X by runtime probe; `p_filesz`/`p_memsz` extension
   page-congruent, no overlap, `< file size`, no other header changed; executable/read flags,
   NX, RELRO, canary, W^X preserved; independent `readelf -l` + LIEF views; no unresolved
   relocation, import, GOT/PLT edit, or permission broadening.
4. **Six-case run.** The frozen manifest's 4 valid + 2 invalid cases score 6/6: byte-exact
   stdout/stderr, exit codes 0 and 1, no crash, exact 42-byte stderr; run on the final
   candidate bytes whose SHA-256 is recorded **before** the run; run from a reverted snapshot.
5. **Isolation evidence for that run** (section 2 above).
6. **Evidence bundle.** Raw outputs plus hashes for every item above.

If any item is missing, gate 3 stays **CONDITIONALLY FEASIBLE** — in particular, a 6/6 run
without the three isolation preconditions is not gate-3 evidence, and a structurally
un-audited candidate is not a pass.

Boundaries:

- Gate 3 pass is a **feasibility proof for fixture selection**, not V0-V5 acceptance, not a
  V3 pass, and not repair proof. The acceptance pipeline still runs later.
- Extra exploratory inputs are allowed but do not count; only the frozen six cases count.
- If 6/6 fails, do **not** adjust the oracle: report the failing case and diagnose. If the
  failure is placement/encoding, report `unsupported` with the concrete fact.

## 4. V4 smoke status

`angr` loading `original.elf` and a 50-step exploration (`active = 0`, `deadend = 1`) is a
**smoke test only**. V4 stays `not_run` / `inconclusive` until a bounded-model exploration
with recorded entry preconditions, memory map, and exploration budget completes. Do not report
it as a pass; 50 steps is far below any meaningful bound.

## 5. Delivery checklist (Member 3, 2026-10-23 18:00)

1. install evidence: versions, `pip freeze` (55 packages), smoke raw output, image chain
   manifest + guest fingerprint, `df`;
2. snapshot revert test (take a `pre-reset-test` protection snapshot first, then revert and
   show the same chain hashes + guest fingerprint);
3. `jobwrap` verification: fixed argv + setuid 1003, no egress, host control-plane reachable,
   job uid = 1003, all raw logs;
4. 6/6 only after the three isolation preconditions hold; otherwise deliver
   `CONDITIONALLY FEASIBLE` and say exactly what is missing.

Any item failing is reported before the deadline; V4 stays `inconclusive`; no after-the-fact
backfill.

**Confirmation log.** 2026-10-22 — chained image manifest accepted with canonical format and
guest fingerprint; root wrapper + setuid 1003 accepted as the unprivileged execution user with
the listed conditions; gate 3 pass criteria defined as six required items; V4 smoke stays
`inconclusive`.
