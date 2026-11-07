# M4 — V4 version self-check failed; replay stopped (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** handoff 131 version self-check only. No replay, no marker, no gate
promotion, no merge, no tag.

---

## 0. Verdict

The handoff says: run the version self-check first; on mismatch, **stop**. The
self-check did not pass — the environment binary is absent — so the replay was
not started and the marker was not written.

| Step | Result |
|---|---|
| Version self-check | **FAILED** — `/opt/angr-venv/bin/python` does not exist (exit 127) |
| Independent candidate/original run | **NOT RUN** — stopped at the gate |
| Two replays | **NOT RUN** |
| Five acceptance criteria | **NOT CHECKED** |
| `replay.verified_by="m4"` | **NOT WRITTEN** |
| V4 | **`not_run`** |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |

---

## 1. The self-check, exactly as handed off

Expected:

```sh
/opt/angr-venv/bin/python -c "import sys, angr, z3; \
  print(sys.version.split()[0], angr.__version__, z3.get_version_string())"
# expected: 3.12.3  10.0.4.post1  5.1.0
```

Actual:

```text
$ ls -l /opt/angr-venv/bin/python
ls: /opt/angr-venv/bin/python: No such file or directory

$ /opt/angr-venv/bin/python -c "..."
bash: /opt/angr-venv/bin/python: No such file or directory
exit=127

$ which -a python3.12
(no python3.12)

$ python3 -c 'import angr'
ModuleNotFoundError: No module named 'angr'

$ ping 192.168.30.128       -> 100% packet loss
$ ssh lab@192.168.30.128    -> connect timeout
```

The contract's four requirements (Python 3.12.x, angr 10.0.4.post1, z3 5.1.0,
inputs reachable) are **not met**. Per handoff 131, that is a stop, not a reason
to relax the version check.

---

## 2. Five criteria — not checked

These are the criteria recorded in handoff 131 §3; none was evaluated because
there is no run:

| # | Criterion | Status |
|---|---|---|
| 1 | `state: passed`, `ran: true`, `scope: model` | **NOT CHECKED** |
| 2 | `replay.runs=2`, `replay.identical=true`, digest `cb2137a2…cb14` | **NOT CHECKED** |
| 3 | calibration: `known_good` holds, `known_bad` violated (1 passed / 1 failed) | **NOT CHECKED** |
| 4 | candidate `unsat` is the empty-disjunction case (`free_calls=0`), disclosed | **NOT CHECKED** |
| 5 | property text matches contract `forbidden_behavior`; hooks do not over-approve | **NOT CHECKED** |

A different digest, if a later run produces one, is a finding to report — not a
number to adjust. None of that applies today.

---

## 3. 124

```text
V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The current-code ingest view (V2 scored 5/5) is also
`inconclusive / required_check_not_run / symbolic`; the bundle's own
`gate-index.json` still shows V2/V4 `not_run`. Either way V4 stays `not_run`.

---

## 4. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 5. Boundaries

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
| `M4-v4-version-selfcheck-evidence-2026-11-06.txt` | exact self-check commands, exit 127, missing python3.12/angr, guest timeout, 124 gate index |
| `131-lead-verified-by-gate-blocker-2026-11-06.md` | the handoff environment contract and five criteria |
| `_m4-verify/3f21d31/` | the current product tree (unchanged by this pass) |
