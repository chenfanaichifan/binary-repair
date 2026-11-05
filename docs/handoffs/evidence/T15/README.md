# T15 — conformance window evidence (2026-11-05)

**Verdict: `pass` (10/10 cases).** Measured in the disposable Ubuntu guest, not
asserted. Judge it yourself with the command in §3.

This package answers task-15: run the fixed-argv executor against the declared
conformance matrix inside a bounded guest session and record what happened.

## 1. What was run

| Item | Value |
|---|---|
| Executor | `/var/tmp/conformance/jobwrap-gate5`, sha256 `293df727636e800d1735443e9ca82cf62add85ccd52d6c93c482b29dd6c128bc` |
| Source | `route-a/jobwrap-gate5/jobwrap_gate5.c` (with the new `routea` mode) |
| Build | `gcc -O2 -Wall -Wextra -Werror -static` — exit 0, no warnings, **in the guest** |
| Window | snapshot `11` / `gate4-harness`, Ubuntu 24.04.5, kernel 6.8.0-147 |
| Runner | `workers/broker/guest_conformance.py` (stdlib only, refuses non-Linux/non-root) |
| Judge | `workers.broker.conformance.evaluate` on the host |

Neither `/usr/local/sbin/jobwrap` (`b232d60b…`) nor `/usr/local/sbin/jobwrap-gate5`
(`0066973d…`) was replaced: the conformance build lives under `/var/tmp`.

## 2. Results

| Case | Kind | Expected | Measured |
|---|---|---|---|
| `pos-gate5-routea-probe` | positive | rc 0 + isolation | rc 0, uid 1003 / cap 0 / nnp 1 / no route |
| `pos-gate5-routeb-probe` | positive | rc 0 + isolation | rc 0, uid 1003 / cap 0 / nnp 1 / no route |
| `pos-routea-exec` | positive | rc 0 + isolation | rc 0, worker ran, candidate `c4a159…aa82` |
| `neg-non-root` | negative | rc 1 `must run as root` | rc 1 (run as uid 1000) |
| `neg-wrong-argc` | negative | rc 2 `usage:` | rc 2 |
| `neg-path-traversal-job-id` | negative | rc 2 `bad job id` | rc 2 (`../etc` refused before any privilege check) |
| `neg-unknown-job` | negative | rc 3 `unknown job` | rc 3 |
| `neg-candidate-hash-mismatch` | negative | rc 4 `hash mismatch` | rc 4 |
| `neg-unknown-mode` | negative | rc 2 `usage:` | rc 2 |
| `neg-relative-path` | negative | rc 1 `absolute` | rc 1 |

The two probe cases ran against the **real** pinned blobs
(`f39a0302…`, `05d9a2cd…`), so their success exercises the fail-closed hash
check rather than a stub.

### Isolation, as attested from inside the sandbox

```json
{"uid":1003,"gid":1003,"cap_eff":"0","no_new_privs":1,
 "netns":"net:[4026532221]","default_route":"","rlimit_cpu":300}
```

The two probe cases reported **different** netns handles (`4026532221`,
`4026532279`) — each run builds its own namespace, which is what real isolation
looks like. Nothing here was inferred from "the wrapper is supposed to isolate".

## 3. Re-judge it

```bash
# from the repo root, with the project venv that has pydantic
python -c "import json; from workers.broker.conformance import evaluate; \
  print(evaluate(json.load(open('docs/handoffs/evidence/T15/evidence.json'))).model_dump_json(indent=2))"
```

The verdict is computed from `evidence.json` alone. `verdict.json` is the
recorded output of exactly that call.

## 4. Files

| File | Content |
|---|---|
| `evidence.json` | Raw runner output: every case's rc, stderr, attestation, argv |
| `verdict.json` | Host verdict (`pass`, 10/10) with per-case detail |
| `environment.txt` | Measured host/guest/binaries/config/hashes |
| `SHA256SUMS` | Hashes of the above |

## 5. What this does and does not establish

**Does:** the executor conforms to its documented fixed-argv contract, refuses
malformed input with the documented codes, and isolates the child (uid 1003, no
capabilities, `no_new_privs`, private netns, no egress) on the real binaries.

**Does not:** establish anything about repair correctness. This window checks
the *executor*, not a patch. Route A behaviour verification (the original
50-byte `guard=CORRUPT` → patched `exit 1` comparison) is a separate obligation
and remains `not_run`.

**One limitation worth stating:** the worker is invoked with relative paths from
the job work-dir, and that directory is world-writable in this demo job so uid
1003 can write its output. A production job directory should be group-owned by
1003 instead; that hardening is not part of this window.
