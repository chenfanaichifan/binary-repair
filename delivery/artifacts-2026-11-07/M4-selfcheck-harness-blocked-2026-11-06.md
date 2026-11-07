# M4 — selfcheck/V4 replay blocked; T8.3 second class still blocked (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** attempted environment/selfcheck/V4 replay and T8.3 second-class check.
No marker, no gate promotion, no merge, no tag.

---

## 0. Verdict

| Item | Result |
|---|---|
| `selfcheck` 18/18 | **NOT RUN** — `/opt/angr-venv` absent; scripts not delivered |
| V4 harness ×2 | **NOT RUN** — no angr, guest unreachable |
| Five criteria | **NOT CHECKED** |
| `replay.verified_by="m4"` | **NOT WRITTEN** |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| T8.3 second-class sample | **CWE122 candidate; PIE/non-PIE decision outstanding; T8.3 BLOCKED** |
| 118 | **VERIFIED** — independent of T8.3 |

Writing the marker without the run would be a false verifier statement, so it
was not written.

---

## 1. Environment / selfcheck

```text
$ ls -l /opt/angr-venv/bin/python
ls: /opt/angr-venv/bin/python: No such file or directory

$ /opt/angr-venv/bin/python -c 'import sys,angr,z3; ...'
bash: /opt/angr-venv/bin/python: No such file or directory
exit=127

$ which -a python3.12
(no python3.12)

$ python3 -c 'import angr'
ModuleNotFoundError: No module named 'angr'

$ ping 192.168.30.128
1 packets transmitted, 0 received, 100.0% packet loss

$ ssh lab@192.168.30.128
connect timeout

$ find . -name selfcheck.py -o -name run_selfcheck.sh
(no selfcheck scripts in the workspace)
```

So the 18-check selfcheck cannot be run here, and the harness has no angr
runtime. There is no honest way to produce `18/18` or two replay digests from
this host.

---

## 2. What is required to unblock

1. Provide `/opt/angr-venv` (Python 3.12.3, angr 10.0.4.post1, z3 5.1.0) **or**
   reachable guest access;
2. deliver `run_selfcheck.sh` / `selfcheck.py` and the
   `cwe416-v4-env-2026-11-06/` evidence directory;
3. run `selfcheck` → **18/18, exit 0**;
4. run `v4_harness.py` twice on candidate `46d16e99…fcd0` / original
   `c9c2632e…` / contract `8a2b408c…`;
5. check the five criteria: candidate **unsat** (empty-disjunction,
   `free_calls=0`), original **sat**, two digests identical and equal to
   `cb2137a2…cb14`, calibration (one known-good pass / one known-bad rejected),
   property/hook match;
6. only then write `replay.verified_by="m4"`.

---

## 3. T8.3 second-class sample

The candidate is **CWE122 heap_out_of_bounds_write** (the honest option in
record 106, since SARD 112 has no CWE787 directory). Record 117 reports:

- fixture passes intake (`OK`, 0 findings);
- six cases measured (valid 0/1/5/9, invalid 10/100; all exit 0, 52 bytes);
- **one blocking question:** the prescribed gcc command produces **PIE**
  (`DYN`), while the contract/task require **non-PIE** (`EXEC`). The fixture
  currently pins a non-PIE build (`c9ddb9c2…`), flagged for a Lead decision.

So there is **no accepted second-class sample** yet: the CWE122 candidate is
built and measured, but its ELF-type decision is unresolved, and T8.3 remains
**BLOCKED**. This is the same status as records 106/117/135; nothing in this
attempt changed it.

---

## 4. 124

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The V4 gate stays `not_run`; no marker means no upgrade.

---

## 5. Record 118 and boundaries

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 6. Evidence

| File | Content |
|---|---|
| `M4-selfcheck-harness-blocked-evidence-2026-11-06.txt` | angr/guest absence, no selfcheck scripts, T8.3 record lines, 124 gate index |
| `129-m3-cwe416-v4-environment-2026-11-06.md` | the environment recipe, not a run |
| `_m3-run/docs/handoffs/106-…` | second-class decision record |
| `_m3-run/docs/handoffs/117-…` | CWE122 build and PIE/non-PIE blocker |
