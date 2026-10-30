# 50 — M4 → M3/VMer: request for one Gate 5 Route A runtime probe window

**FROM:** M4 (independent verifier)
**TO:** M3 (guest/VMer operator), cc Lead, M5
**TASK:** Gate 5 — Route A runtime placement proof (independent M4 probe; not M3's logs)
**STATUS:** requested — **no execution yet**; M4 cannot reach the guest from its host
**ARTIFACT:** this file + `scripts/m4_gate5_probe.py` (M4-authored, guest-only)
**SUBJECT:** candidate `routea/out/cave-probe.elf`, SHA-256
`c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`; original
`aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`; six frozen cases from
`fixtures/public/CWE121_src_char_declare_cpy_51b/tests/{valid,invalid}.json`.
**VALIDATOR/PRECONDITION:** M4 probe script exits `2` unless euid=1003 and hashes match; raw output only.
**REQUESTED:** one bounded guest window; run M4's script under jobwrap; return the whole work
directory + `SHA256SUMS` + its SHA-256; do not summarise as pass/fail.
**DEADLINE:** window requested by **2026-10-30 18:00** (Asia/Hong_Kong); if the guest is
unavailable, publish a blocked note with the exact external condition and who can clear it.
**NEXT:** M3/VMer confirms the window and executes; M4 fills record `51` with **PASS / FAIL /
NOT VERIFIED** only; Gate 5 stays **unsigned** until then.

## 1. Scope (do not widen it)

This is **Gate 5 Route A runtime placement only**. It is not Gate 4, not V3 acceptance, not V4
symbolic, and not a repair claim. Gate 4 is still `NOT RUN` (no `P4`, no M5 record, no real p2);
Gate 6 stays `partial`. The fixture stays `NOT FROZEN`.

M4 must not reuse M3's existing logs/claims for this probe. The point is a **new**, M4-defined
run whose raw bytes M4 can re-hash and inspect. If the window cannot be provided, the only
honest result is `NOT VERIFIED` (never a pass, never a static substitute).

## 2. Window requirements (all required; a missing item = NOT VERIFIED)

| # | Requirement | What to record |
|---|---|---|
| W1 | Disposable guest, clean snapshot reverted for this run | snapshot name/id + chain manifest SHA-256 + raw revert command/output + timestamp |
| W2 | Unprivileged runner | `uid=1003`, `CapEff=0`, `NoNewPrivs=1`, `sudo -n true` fails |
| W3 | Job-time egress blocked | netns/route evidence; an egress attempt fails with its exact error |
| W4 | Evaluator/source unreadable to the runner | raw `ls`/open denial evidence |
| W5 | Root-started jobwrap drops privileges (no host execution) | exact jobwrap path + SHA-256, invocation, fixed `execv` argv |
| W6 | Tools | `gdb` (15.x), `python3`, `sha256sum`; record versions |
| W7 | Writable work dir | `/var/tmp/m4-gate5-<UTC>` (or equivalent), owned by the run user |
| W8 | Operator | VMer/M3 operates the VM console; M4 observes/verifies; no one runs the candidate on the host |

## 3. Exact execution (M3/VMer)

1. Fetch the repo state that contains `scripts/m4_gate5_probe.py` (this handoff and the script are
   on branch `lead/consolidation-verified-64c6f3eb`; see the transfer note / Lead). If M3 cannot
   fetch GitHub, use the copy the Lead provides and hash it.
2. Verify the script hash against the envelope/BOARD and the candidate/original hashes above.
3. Run from the guest, root-started jobwrap dropping to uid 1003:

```bash
jobwrap ... -- /path/to/repo/scripts/m4_gate5_probe.py /path/to/repo /var/tmp/m4-gate5-$(date -u +%Y%m%dT%H%M%SZ)
```

If the local jobwrap interface differs, run the equivalent hardened invocation (same controls)
and record the **exact** command; the script itself refuses to run unless euid=1003.

4. Return the **entire work directory**, including:
   - `environment.txt`, `gdb-probe.log`, `gdb-probe.rc`, `cave-memory.bin`, `cave-file.bin`,
     `cave-memory.sha256`, `cave-file.sha256`, `six-cases.json`, `case-*.{rc,stdout.bin,stderr.bin}`,
     `probe-summary.json`, `SHA256SUMS`;
   - the SHA-256 of `SHA256SUMS` (the evidence-manifest hash);
   - the exact command(s), UTC start/end, and the W1–W8 evidence;
   - the candidate hash **before** and **after** the run (the script records both).
5. Do not edit the script, the results, or the hashes; do not add a pass/fail conclusion of your
   own. Raw output + hashes only.

### 3a. Invocation status — M5 wrapper delivered, M4 fixed launcher provided (2026-10-29 18:30)

M5 published the Gate 5 wrapper on `origin/main` (`docs/handoffs/44-t5.1-ratified-execution-invocations.md`);
the reported wrapper hash is `routeb/jobwrap_gate5.sh` SHA-256 `859ac8fe…`. M4 provides the fixed
launcher `scripts/m4_gate5_fixed.sh`, SHA-256
`B751BB7FB0A03596C750E8BFD8F43EF4B87FB68A96E2A65F62B2BB8F66E313C5` (it `exec`s the M4 probe).
Exact invocation:

```bash
GATE5_SCRIPT=/path/to/repo/scripts/m4_gate5_fixed.sh \
  jobwrap gate5 -- <repo>/routeb/jobwrap_gate5.sh <repo> /var/tmp/gate5-work
```

Preconditions before running: verify both hashes against this file/`51`; `chmod +x` the launcher
in the guest copy; M3/VMer confirms `jobwrap gate5` has the same uid 1003 / netns / no_new_privs /
caps / rlimit controls (otherwise use the documented equivalent and record it). **Residual
fixed-argv risk:** the wrapper takes `GATE5_SCRIPT` from the environment; M5 must hard-code or
hash-validate it before the run, otherwise do not treat the run as fully fixed.

**Do not run the probe directly or via `sudo -u 1003`/an ad-hoc shell.** If no `gate5` mode or
equivalent controlled invocation exists, publish a blocked package naming M5 and keep Gate 5
Route A `NOT VERIFIED` (`51` unsigned); never write PASS/FAIL from an unisolated run.

## 4. What M4 will check and report

M4 will independently re-hash the returned files and check (record `51`):

| ID | M4 check | PASS requires |
|---|---|---|
| R1 | identity | candidate `c4a159…` and original `aa428157…` from delivered bytes; script hash matches |
| R2 | runtime mapping | a mapping line covering `0x401000–0x401fff` with `r-xp` (`info proc mappings`) |
| R3 | memory = file | cave memory dump `0x4018e9–0x401fff` byte-equal to the candidate's file bytes at the same range; both SHA-256 recorded |
| R4 | breakpoints / execution | `SITE 0x401304`, `CAVE 0x4018e9`, `AFTER 0x401309`, `RET 0x401317` reached; cave entry decodes; no crash before entry |
| R5 | six frozen cases | per-case rc/stdout/stderr byte-exact to the frozen manifests on this candidate (6/6) |
| R6 | isolation | W1–W5 evidenced for the same session, raw output present |
| R7 | candidate stable | candidate hash before = after the run |
| R8 | evidence manifest | returned `SHA256SUMS` verifies every file; its own SHA-256 recorded |

**Result vocabulary is exactly PASS / FAIL / NOT VERIFIED.** Gate 5 remains **unsigned** and
stays `pending` until M4's verifier row is complete and the Lead approves; no "probably",
"should pass", or static/CI substitute.

## 5. Custody and boundaries

- The probe is M4-authored and M3/VMer-executed in the guest. M4 does not run the candidate on
  its host; M3/VMer does not decide the verdict.
- Raw evidence stays under `var/jobs/m4-gate5/<run-id>/` on the executing side and is cited by
  filename + SHA-256; the committed record is `docs/handoffs/51-m4-gate5-runtime-record.md`
  (created unsigned with this request).
- If a control (W1–W5) is missing, the run is `NOT VERIFIED` even if R2–R5 look correct.

## 6. Escalation

- No window by 2026-10-30 18:00 → publish a blocked note (exact error, who can unblock) and
  keep Gate 5 `pending`; do not retry the same blocked action more than twice.
- Gate 4 JOIN-1 is separate: it keeps waiting for `P4` + M5's record + a real p2 exit 0; this
  Gate 5 request does not change it.

**Signature/envelope status:** request only; no result. M4 verifier row in `51` stays blank.
