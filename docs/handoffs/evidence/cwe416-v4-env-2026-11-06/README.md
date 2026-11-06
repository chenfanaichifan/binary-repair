# The interpreter behind the V4 evidence

This directory is the answer to one question: **what exactly produced
`docs/handoffs/evidence/cwe416-v4-2026-11-06/harness-output.json`, and can
someone else rebuild it?**

It holds three things — a provisioning recipe, a self-check that compares a
machine against the recorded environment, and the output of that self-check run
on the guest that produced the evidence. It holds no gate verdict.

## Measured environment

| | |
|---|---|
| OS | Ubuntu 24.04.5 LTS, kernel 6.8.0-147-generic, glibc 2.39, x86-64 |
| interpreter | CPython **3.12.3** at `/usr/bin/python3.12` (`python3.12` 3.12.3-1ubuntu0.17) |
| venv | `/opt/angr-venv`, made by `/usr/bin/python3 -m venv /opt/angr-venv` |
| angr | **10.0.4.post1** (archinfo / cle / pyvex 10.0.4) |
| z3 | z3-solver **5.1.0.0**, libz3 answers **5.1.0** |
| packages | 54 in `pip freeze`, 55 distributions counting pip **26.2.1** |
| dependency state | `pip check` clean |
| size | 650 MB |

`pyvenv.cfg` is copied verbatim into `01-selfcheck.txt`, including the `command`
line, so the venv's own record of how it was made is in the evidence rather than
in a claim about it.

## Recipe

```sh
sh provision_angr_venv.sh          # needs sudo and egress to PyPI, ~650 MB
/opt/angr-venv/bin/python selfcheck.py
```

The script is four steps and nothing else: `apt-get install python3.12
python3.12-venv`, `python3 -m venv /opt/angr-venv`, `pip install pip==26.2.1`,
`pip install -r requirements-angr-10.0.4.post1.txt`. The pins are not
hand-written — the file is `pip freeze` with a comment header, and
`04-pins-match.txt` shows the 54 lines diff clean against the live environment
(`d06f7765…` on both sides).

Two things the recipe deliberately does *not* do: substitute a pyenv/conda 3.12
(the wheel tags and the z3 build differ), and call the result a verification.
Rebuilding the interpreter is not rebuilding the verdict.

## Paths

Every row is a file the harness reads or writes; the sha256 is what this window
verified, not what was assumed.

| role | repository | guest | sha256 |
|---|---|---|---|
| harness | `docs/handoffs/evidence/cwe416-v4-2026-11-06/v4_harness.py` | `/home/lab/v4/v4_harness.py` | `986688bc…b863e` |
| candidate | `docs/handoffs/evidence/cwe416-candidate-2026-11-05/candidate.elf` | `/home/lab/cwe416-sync/candidate.elf` | `46d16e99…1fcd0` |
| original | `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/original.elf` | `…/kit/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/original.elf` | `c9c2632e…123c9` |
| contract | `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/contract.json` | same directory as above | `8a2b408c…e3c3b` |
| committed harness output | `docs/handoffs/evidence/cwe416-v4-2026-11-06/harness-output.json` | `/home/lab/v4-env/committed-harness-output.json` | `9c6eeda7…8ca8c` |

The guest `…/kit/` tree is the extraction of the fixture kit used in earlier
windows; it carries the same bytes as the repository paths, which is why the
hashes match rather than being restated from memory.

## Self-check

`01-selfcheck.txt` — 18 checks, all pass:

```
[ok] python version          3.12.3 (expected 3.12.3)
[ok] interpreter is the venv /opt/angr-venv
[ok] base interpreter        /usr
[ok] angr pinned / archinfo pinned / cle pinned / pyvex pinned   10.0.4(.post1)
[ok] z3-solver pinned        5.1.0.0 (expected 5.1.0.0)
[ok] libz3 version           5.1.0 (expected 5.1.0)
[ok] pip check               No broken requirements found.
[ok] z3 returns sat          x>1 and x<3
[ok] z3 returns unsat        x>2 and x<2
[ok] harness / candidate / original / contract sha256
[ok] target entry resolves   0x4012aa
verdict: 18/18 checks passed
```

The timeout probe prints the solver's own answer (`unknown` at a 1 ms budget) and
is labelled informational. It is not a check, because a 1 ms budget is not a
property of the environment.

## End-to-end

`03-rerun.txt` — the environment was asked to reproduce the committed evidence,
not just to report versions:

```
$ /opt/angr-venv/bin/python /home/lab/v4/v4_harness.py … --out rerun.json
  exit 0 in 5251 ms
9c6eeda7… rerun.json
9c6eeda7… committed-harness-output.json
byte-identical
```

Same measurements as record 128: `known_good` holds with `eval=1 unsat=1` in
11/64 steps, `known_bad` violated with `eval=1 sat=1` in 14/64 steps,
`complete=True unexplored=[]`, replay 2 runs identical, `claimed_scope=model`.

## What was not done

**The provisioning script was not executed.** The guest has no egress in this
window — `curl https://pypi.org/simple/` returns nothing and `ping
192.168.30.1` gets no reply — so `pip install` of 54 distributions could not run
there. `00-window-host.txt` records that, and the reason the window still worked
(IPv6 link-local, EUI-64 from the VM MAC).

What that leaves unproven is narrow and should be said plainly: the recipe's
*install* half is untested here. Its *verification* half is tested twice — the
self-check against the live venv, and the rerun that reproduced the committed
bytes. The nearest thing to a dry run available without egress is
`05-pypi-pins.txt`: all five packages that decide behaviour exist on PyPI with a
linux x86-64 CPython 3.12 wheel, each with its sha256, so the pins are real
artifacts rather than remembered numbers. A window with egress can close the rest
by running `provision_angr_venv.sh` with `VENV=/opt/angr-venv-rebuild`, then
`selfcheck.py` under that interpreter, and diffing the two freezes.

**No gate was touched.** `gate-index.json` in the 124 bundle still reads V4
`not_run`; `v4-symbolic.json` in the 128 evidence directory is unchanged. An
environment that can run a producer does not certify what the producer emits —
that is a replay, per `docs/handoffs/62 §1`.

**No `verified_by` field was written anywhere.** This delivery is M3: it hands
over an environment and a check that the environment is the recorded one. The
field belongs to whoever replays, and writing it here would be the same mistake
as self-issuing a gate result.

T8.3 stays blocked: one sample, one repair, one observation. No second sample is
described here, and none is implied.

## Files

| file | what it is |
|---|---|
| `provision_angr_venv.sh` | the recipe; four steps, sudo and egress required |
| `requirements-angr-10.0.4.post1.txt` | `pip freeze` + comment header, 54 pins |
| `selfcheck.py` | compares a machine against the recorded environment, exit 0/1/2 |
| `run_selfcheck.sh` | `selfcheck.py` plus the command line, → `01-selfcheck.txt` |
| `run_freeze.sh` | freeze + pip's own version + `pip check`, → `02-pip-freeze.txt` |
| `run_e2e.sh` | harness rerun and byte comparison, → `03-rerun.txt` |
| `summarize_output.py` | one-screen summary of a harness output file |
| `check_pypi_pins.py` | names the wheel each decided pin would fetch; downloads nothing |
| `00-window-host.txt` | host side: how the guest was reached, and what that rules out |
| `01-selfcheck.txt` | 18/18, the output of the self-check on the guest |
| `02-pip-freeze.txt` | the 54 pins as they are installed today |
| `03-rerun.txt` | rerun of the harness; byte-identical to the committed output |
| `04-pins-match.txt` | the shipped pins diff clean against the live freeze |
| `05-pypi-pins.txt` | the five deciding pins exist upstream, with wheel hashes |
