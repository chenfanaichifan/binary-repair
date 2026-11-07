# Handover: M3 role, for whoever picks this up next

- Written: 2026-11-07 10:25 local
- By: M3 (guest execution and evidence), for the next agent taking that role
- Branch at time of writing: `m3/cwe416-v3-noinput` @ `dd2d926`, 110 commits ahead of `origin/main`
- Read this before writing anything into the repository. Then read `AGENTS.md`.

This is not a status summary. It is the things that cost time to learn and are not
written down anywhere else: where the bodies are buried, which "obvious" checks lie,
and what you are not allowed to do however reasonable it feels.

---

## 1. The 60-second version

The project repairs one known vulnerability in a Linux x86-64 ELF without source,
through two routes, and proves the result with deterministic gates V0–V5. It is a
five-person course project; you are **M3**: you run things on the guest VM and you
produce evidence. You do not write product code, and you do not decide verdicts.

The current goal is **T8.3**: show the workflow handles a *second defect class*
(CWE-416, use-after-free) differently from the first (CWE-121, stack overflow), with
the same acceptance ladder.

**State: T8.3 is blocked.** Not "nearly done" — blocked, on one thing that is not
yours (M4's replay marker) and one thing that is now unblocked (guest access).

```
V0 passed   V1 passed   V2 passed 5/5   V3 passed 1/1   V4 not_run   V5 passed
```

If you remember one sentence: **everything M3 could do alone is done, and doing more
of it will not move the gate.**

---

## 2. Your boundaries, before anything else

These are not suggestions. Violating them invalidates other people's work.

| You may | You may not |
|---|---|
| run things on the guest, collect output | write `verified_by` in any file, in any spelling |
| build evidence packages with hashes | decide that a gate passed |
| measure, reproduce, disprove | modify `fixtures/` content, `contract.json`, or a candidate |
| write records and proposals | patch `app/`, `routeb/`, `routeb/attempt_writer.py`, `app/domain/v4.py` |
| point at a defect in someone else's file | fix that file silently |
| say "this fails" | weaken a check so it passes |

The reason `verified_by` is absolute: the producer of evidence cannot also be the
verifier of it. If you write it, the whole T8.3 claim collapses, and it collapses
in a way nobody can detect later.

If you find yourself thinking "but it obviously passes, I'll just record it" — that
instinct is the defect. Write the measurement, and let the person who owns the
verdict write the verdict.

---

## 3. Environment

### The VM

```sh
"D:/VMware/vmrun.exe" -T ws start "D:/VMs/binrepair-u2404-x64-01/BinRepair-Lab.vmx"
"D:/VMware/vmrun.exe" -T ws list          # is it running?
ssh -i .tmp/ssh/id_ed25519 lab@192.168.30.128
```

Ubuntu 24.04, gcc 13.3, glibc 2.39. `lab` is uid 1000 and has passwordless sudo —
it is your hands on the machine. Guest address `192.168.30.128` on VMnet8.

**The VM may be powered off when you arrive.** That is normal and it is not a
network fault; start it before diagnosing anything.

### Reaching it from outside the host

`192.168.30.128` is a **VMnet8 NAT address**. Nothing outside this host can route to
it. A port forward exists:

```
host <WLAN-address>:2222  ->  192.168.30.128:22
```

```powershell
netsh interface portproxy show all
Get-NetIPAddress -AddressFamily IPv4 | ? InterfaceAlias -eq WLAN    # current address
```

The WLAN address is **DHCP and has already changed once** (`192.168.43.11` →
`10.11.0.132`). Always read it; never quote it from a document, including this one.

### Accounts on the guest

| account | uid | purpose | sudo | password | ssh keys |
|---|---|---|---|---|---|
| `lab` | 1000 | your hands; the only human entry | yes, NOPASSWD | locked | `t7WYc2…` |
| `ubuntu` | 1001 | distro default | in sudo group | locked | **empty file** |
| `repair` | 1002 | unclear, probably superseded | no | locked | none |
| `runner` | 1003 | job runner / executor (**this is the one**) | no | locked | **none** |
| `m4verify` | 1004 | M4's replay only | no | locked | 2 (M5 + M4) |
| `m5verify` | 1005 | M5's collaboration access | no | locked | 1 |

`m4verify` is **not** an executor account. Never run a job as `m4verify`: it exists
so that M4's replay is M4's, and reusing it makes the independence claim false.
`repair` vs `runner` is unresolved — see §7.

### The venv

```
/opt/angr-venv/bin/python     angr 10.0.4.post1, z3 5.1.0, CPython 3.12.3
```

Built by `docs/handoffs/evidence/cwe416-v4-env-2026-11-06/provision_angr_venv.sh`.
Self-check: `selfcheck.py` in the same directory, 18 checks, exit 0/1/2.

**`import claripy` fails on angr 10.** Use `angr.claripy`. This cost an hour once.

---

## 4. Repository map

```
fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/   the frozen T8.3 sample (14 files)
docs/handoffs/                      104 task records, numbered; read 139, 145 first
docs/handoffs/evidence/             12 evidence directories, each with its own SHA256SUMS
T8.3-evidence-2026-11-06/           the T8.3 bundle: fixture/, candidate/, v4/, gates/, logs/
T8.3-refresh-2026-11-06/            V0/V1/V5 re-derived in a later window + the V2/V4 wiring proposal
T8.3-supplement-2026-11-06/         hooks audit + property mapping (read these before defending the property)
M4-v4-handoff-2026-11-06/           the runnable package M4 executes
dist/                               zips and their .sha256 (not tracked by git)
delivery/                           the separate delivery branch is checked out elsewhere; see §7
```

Everything is in the repository **on this branch**. `origin/main` has none of it.

### The numbers you will need constantly

```
original.elf    c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9   25,344 B
candidate.elf   46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0   25,344 B
contract.json   8a2b408c…e3c3b (file)    c1684f15…b4f7c (canonical, via SecurityContract)
original.c      fa84a6bb…7f42e (CRLF, 110 lines — do not normalise it)
harness output  9c6eeda7684f2e405fbceb83fec4a3962687559b1d35e738431c631b7d58ca8c
replay digest   cb2137a20d838e3f48e02f2d38f258487ddc3a588a371970d9ef41b63304cb14
```

The candidate is five bytes: `call free@plt` → five `nop` at offset 4869. That is
`authorized_edits[0]`, "drop the free() and accept the leak". The contract says so
verbatim; the leak is in scope, and the pointer-flow property holds *because*
nothing is freed on that path. Do not let anyone describe that unsat as "the solver
proved it" — it is the empty-disjunction case and the evidence says so.

---

## 5. What is done

Everything below is committed and pushed. Do not redo it; verify it if you doubt it.

- **The frozen sample**: fixture, v3 no-input contract, candidate, and V0/V1/V2/V3/V5
  evidence. V2 is a real 5/5 measurement (`gates/v2_interface.py`).
- **V4 producer**: `v4_harness.py` asks, at every `printLine`, whether the argument
  is a pointer freed earlier on that path. Candidate `holds` (unsat=1), original
  `violated` (sat=1). That is the negative control and it is why the result means
  anything.
- **V4 product evidence**: `v4-symbolic.json`, produced by M1's adapter at `c41de41`,
  validating with hashes bound. It is *not* a gate result.
- **Access**: M4's own key installed and verified; the port forward open and proven
  by an actual login; the guest's sshd log showing that no outside client had ever
  arrived before.
- **Two review findings reproduced**: the planner cannot distinguish the two classes
  (`app/domain/assistant.py:84` takes a `context` and never reads it), and the V4
  adapter trusts a `replay.identical` that its own digests contradict
  (`app/domain/v4.py:287`). Both have scripts, not summaries:
  `evidence/t83-review-findings-2026-11-07/`.

---

## 6. What is blocked, and on whom

| blocker | owner | what "done" looks like |
|---|---|---|
| V4 `not_run` | **M4** | they run the harness, reproduce the digest, write their own marker |
| where the marker goes | **M1** | one canonical ingest path, tested from bundle to persisted verdict |
| planner distinguishes classes | **M5** | `01-reproduce.py --expect-distinct` exits 0 |
| adapter rejects contradictory replay | **M1** | four-line fix in `app/domain/v4.py`, proposed in the evidence |
| GUI shows V4 scope, invalid = N/A | **M2** | nothing renders a verdict it did not receive |
| merge 110 commits into main | **Lead** | after T8.3 closes, not before |
| `repair` vs `runner` | **Lead / VMer** | one executor account, the other retired, recorded in record 88 |

Nothing on that list is M3's. When you are asked "what is left", that table is the
answer, and it is more useful than another paragraph of evidence.

---

## 7. Ten traps that cost real time

Read these. Each one produced a wrong conclusion at least once.

**1. A 502 can hide a non-fast-forward.** `CONNECT tunnel failed, response 502` was
read as "network down, retry later" for two days. When the tunnel came back the same
push failed differently: `non-fast-forward`, because the branch was cut before ten
commits landed upstream. *A transport error says nothing about repository state.*
When a push fails, get the server to answer before concluding anything about the
network.

**2. `core.autocrlf=true` rewrites `.sha256` files, so `sha256sum -c` fails on a
fresh clone.** The manifest looks fine locally and reports "FAILED open or read" for
everything after checkout. `.gitattributes` now pins `docs/handoffs/evidence/**`,
`M4-v4-handoff-2026-11-06/**`, `T8.3-*` with `-text`. Add the same for any new
hash-bound directory.

**3. `Path.write_text()` on Windows writes CRLF.** Any self-authored JSON or text you
generate with Python needs `p.write_text(s, encoding="utf-8", newline="")`, then a
CRLF check, then a manifest rebuild. This bit three separate times.

**4. Blanket LF normalisation destroys upstream sources and changes their hashes.**
`fixture/original.c` is CRLF and its digest `fa84a6bb…` is frozen. A "tidy up the line
endings" pass silently broke it. **Always re-hash after any bulk text operation**;
never trust "that should not have changed anything".

**5. `sha256sum -c` resolves paths relative to the current directory.** Run it from
*outside* the directory and every row reports "No such file" — which looks like a
corrupt package and is not. `cd` in first.

**6. `git add -A docs/handoffs` will commit other people's uncommitted work.** It
happened: three of M1's files got swept into an M3 commit. Add exact paths. If you
already committed it, `git reset --soft HEAD~1` then `git restore --staged <their
files>`.

**7. Record numbers are taken, not raced.** Three collisions in one afternoon, plus
`133`/`137` still outstanding between this branch and `delivery/t83-2026-11-06`
(theirs landed first, so **ours must move**). Check `git ls-tree` on the delivery
branch before claiming a number, and renumber in one pass — a half-finished rename
is worse than a known collision.

**8. A verification that cannot fail is not a verification.** An early self-check
ended with `sh script.sh; echo "exit=$?"` — it printed the status and then exited 0
unconditionally. Keep the status, stop on failure, and exit with the comparison's
result.

**9. Record only what you measured, and say which run it came from.** Re-executing a
"before" step after the change produces a different number and reads as a
contradiction. Quote the output of the run that actually happened, and label it.

**10. Changing the guest's network mode would invalidate the evidence chain.**
Bridged networking would make access easier and would change `192.168.30.128`, which
every window record from 118 onward describes. Port forwarding touches nothing inside
the guest, which is exactly why it was chosen. Prefer the change that leaves the
measured thing alone.

Two smaller ones: on Windows, calling `powershell` from Bash is blocked by policy (use
the PowerShell tool), and the word itself inside a heredoc can trip the same check.
And `git diff 584b912 HEAD -- fixtures` being **empty** is the way to prove you did
not touch a frozen fixture — better than saying so.

---

## 8. How evidence is done here

- **A file with a hash next to it is not evidence.** Show the command, its output,
  and the timestamp. A number without a command is a claim.
- **Every evidence directory carries its own `SHA256SUMS`.** Rebuild it with
  `find . -type f | sort` before hashing — unsorted manifests fail on another machine
  and look like corruption.
- **A package must not contain its own hash.** Put the archive's digest in a
  `.sha256` file *beside* the archive, never inside it.
- **Never ship a private key in a package.** M4's and M5's private halves never touch
  this host; you install public keys and nothing else. If a package you inherited
  contains one, say so loudly.
- **State what a measurement does not establish.** Every one of these records has a
  "what this does not establish" section, and that is the part reviewers actually
  read.
- **Self-correction is expected.** If you previously wrote something wrong, add a
  new record that corrects it and keep the old one. Do not rewrite history to look
  prescient — the record of how a wrong conclusion was reached is part of the
  evidence that you can find wrong conclusions.

---

## 9. If you have one window

1. `git log --oneline -1`; confirm you are on `m3/cwe416-v3-noinput` and it matches
   `origin`.
2. Start the VM. `ssh -i .tmp/ssh/id_ed25519 lab@192.168.30.128 'uptime; ss -ltn | grep :22'`
3. Check whether M4 has connected since last time:
   `sudo journalctl -u ssh | grep -c 'Accepted publickey for m4verify'`
4. Read `docs/handoffs/139-m3-to-m4-2026-11-07.md` and `145-m3-to-m4-key-installed-2026-11-07.md`.
5. If M4's marker now exists somewhere, the gate may have moved — verify it, do not
   assume it. If it does not exist, **say so plainly and stop**; do not manufacture
   progress.

Then, and only then, consider the outstanding M3 item: renumbering `133-m3-*` and
`137-m3-*` and every reference to them.

---

## 10. How to check this document instead of trusting it

Everything above is falsifiable in a few commands:

```sh
git log --oneline -1                                   # the commit named in the header
git rev-list --count origin/main..HEAD                 # 110
ls docs/handoffs/*.md | wc -l                          # 105 — 104 records plus this file,
                                                       # which is why a handover cannot be
                                                       # exact about its own directory
sha256sum fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/original.elf
python -c "import json;d=json.load(open('T8.3-evidence-2026-11-06/gates/gate-index.json'));print({g['gate']:g['state'] for g in d['gates']})"
grep -c context app/domain/assistant.py                # 1 — the signature, and nothing else
grep -rnE '"verified_by"[[:space:]]*:[[:space:]]*"' --include=*.json . | grep -v dist
```

If any of those disagree with what is written here, **this document is stale and the
repository is right**. Numbers in a handover rot faster than anything else in a
project; treat this file as a snapshot with a date, not as truth.
