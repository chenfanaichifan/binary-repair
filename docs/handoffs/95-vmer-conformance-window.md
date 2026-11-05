# 95 — VMer conformance window (task-15)

**Renumbered 89 → 95 on 2026-11-05.** The sequence `89` is used by
`89-status-reconciliation-2026-11-05.md`; any earlier reference to
`89-vmer-conformance-window` means this file.


**Owner:** VMer (M3兼任) · **Date:** 2026-11-05 (window executed) · **Status:**
procedure + harness shipped, and the window has **run once in the guest** —
**verdict `pass`, 10/10 cases**. Evidence: `docs/handoffs/evidence/T15/`.

This record defines the conformance window: a bounded, repeatable guest session
in which the fixed-argv executor is checked against a declared matrix, and the
result is recorded as machine-checkable evidence rather than a claim.

## 1. What "conformance" means here

The executor (`jobwrap-gate5`, and any successor carrying the `routea` mode)
accepts only fixed argv forms and must isolate the child. Conformance is the
demonstration of two things at once:

| Axis | What must hold |
|---|---|
| **Contract** | Every documented argv form is accepted; every malformed form is refused **with the documented exit code and a matching stderr substring** |
| **Isolation** | Every successful run attests `uid=1003`, `gid=1003`, `CapEff=0`, `NoNewPrivs=1`, a private netns, and no default route |

A run that exits 0 without attesting isolation is **not** conformant. This is
the same rule Nick's audit demanded of the acceptance layer: the artefact must
carry the fact, not the narrative.

## 2. The matrix

Defined in `workers/broker/conformance.py` as `CONFORMANCE_MATRIX`, so the
runner and the judge share one source of truth (10 cases):

**Positive (must exit 0 and attest isolation)**

| id | argv |
|---|---|
| `pos-gate5-routea-probe` | `probe m4-gate5 -- <repo> <work>` |
| `pos-gate5-routeb-probe` | `probe m4-gate5b -- <repo> <work>` |
| `pos-routea-exec` | `routea demo` *(requires `routea` mode)* |

**Negative (must refuse with the exact code)**

| id | argv | rc | stderr must contain |
|---|---|---:|---|
| `neg-non-root` | `routea demo` (as non-root) | 1 | `must run as root` |
| `neg-wrong-argc` | `probe m4-gate5` | 2 | `usage:` |
| `neg-path-traversal-job-id` | `routea ../etc` | 2 | `usage:` |
| `neg-unknown-job` | `routea missing` | 3 | `unknown job` |
| `neg-candidate-hash-mismatch` | `routea demo` (tampered candidate) | 4 | `hash mismatch` |
| `neg-unknown-mode` | `probe not-a-mode -- /repo /work` | 2 | `usage:` |
| `neg-relative-path` | `probe m4-gate5 -- repo work` | 1 | `absolute` |

Exit codes 2/3/4 come from `workers/route_a/JOBWRAP_ROUTEA.md`; the gate5
forms come from `route-a/jobwrap-gate5/README.md`.

## 3. Window procedure

One window = one snapshot → one run → reset. Never reuse a window for two
builds, because a stale binary hash in the evidence is indistinguishable from a
correct one after the fact.

```text
 1. VM off; record `.vmsd` snapshot.current
 2. revertToSnapshot <target>            # uid 11 gate4-harness for gate5 cases
 3. boot; record `id -u`, `uname -a`, `sha256sum` of the executor
 4. python3 workers/broker/guest_conformance.py \
        --executor /usr/local/sbin/jobwrap-gate5 \
        --repo /srv/binrepair --work /var/tmp/conformance \
        --snapshot-uid 11 --snapshot-name gate4-harness \
        --out /var/tmp/conformance/evidence.json --guest-ack
 5. copy evidence.json out; `sha256sum` it
 6. shutdown clean; confirm no `.lck` under the VM directory
 7. reset: revertToSnapshot <target> again (leave the guest clean)
```

Step 4 is the only step that runs a binary, and it runs **inside the guest**.
The host evaluates the resulting JSON with
`workers.broker.conformance.evaluate(payload)`; the host never executes.

## 4. How the verdict is computed (fail-closed)

| Situation | Verdict |
|---|---|
| Every case present and matching | `pass` |
| Any case contradicts the matrix (wrong rc, wrong stderr, isolation gap) | `fail` |
| A required case has no record | `not_run` |
| A case could not run (missing mode, timeout, skip) | `inconclusive` |
| Evidence fails schema validation | `fail` |

Two rules are worth stating explicitly because they are the honesty core:

- **An absent attestation is `inconclusive`, never inferred.** `jobwrap-gate5`
  prints nothing on success — it only reports errors via `die()`. The runner
  therefore reads an attestation file the probe writes and records "absent"
  when there is none. Tests assert this.
- **A mode the binary does not ship is `inconclusive`, not `fail`.** The
  runner records `available_modes` by probing the binary's own usage text; a
  `routea` case against a gate5-only binary is marked inconclusive rather than
  pretending the executor is broken.

## 5. Files

| File | Role |
|---|---|
| `workers/broker/conformance.py` | Matrix + fail-closed evaluator (host) |
| `workers/broker/guest_conformance.py` | Runner (guest only; refuses non-Linux / non-root / no `--guest-ack`) |
| `tests/unit/test_broker_conformance.py` | 21 tests over the verdict rules |

Host-refusal was verified on 2026-11-05 (Windows host): without `--guest-ack`
it exits 2 with a refusal; with `--guest-ack` it still exits 2 because the
platform is not Linux. Both refusals are real, not asserted.

## 6. Status — measured 2026-11-05

| Item | Status |
|---|---|
| Matrix + evaluator + runner | **implemented**, 33 source/unit tests pass |
| Host refusal | **measured** (Windows, exit 2 both paths) |
| `routea` mode | **written + compiled + executed**. `gcc -O2 -Wall -Wextra -Werror -static` exit 0, no warnings, in the guest |
| Window run | **`pass`** — 10/10 cases, `docs/handoffs/evidence/T15/` |
| Executor hash | `293df727636e800d1735443e9ca82cf62add85ccd52d6c93c482b29dd6c128bc` (built to `/var/tmp`, Gate 4 and Gate 5 binaries untouched) |
| Isolation attestation | **measured from inside the sandbox**: uid 1003, gid 1003, `CapEff=0`, `NoNewPrivs=1`, private netns, no default route |

### Bugs this window found (all fixed, each a real defect)

Running the matrix was not a formality — four defects surfaced that no static
check would have caught:

1. **Sample config doubled the path.** `work-dir` was written as `…/demo/route_a`
   while the wrapper appends `/route_a/candidate.elf`, giving
   `…/route_a/route_a/candidate.elf`. Fixed in `routea.conf.sample`.
2. **No `chdir` before exec.** The worker takes relative paths; without a
   `chdir` to the work-dir it read the wrong files.
3. **`chdir` was EPERM after isolation.** The seccomp allow-list deliberately
   excludes `chdir`, so it must run *before* `enter_isolation()`.
4. **The sandbox could not write its own attestation.** `/var/lib/binrepair` is
   `0700`, so uid 1003 cannot create a file there. The child now measures and
   pipes the values to the root supervisor, which writes the file — measurement
   stays inside the sandbox, the file stays root-owned.

Two matrix bugs were also found by running it: `neg-path-traversal-job-id`
expected a bare `usage:` line the wrapper never prints, and
`neg-candidate-hash-mismatch` reused the *good* job (which correctly exits 0).
Both fixed; the hash case now uses a dedicated `demo-badhash` config line.

### What this does not establish

The window checks the **executor**, not a patch. Route A behaviour verification
(the original 50-byte `guard=CORRUPT` → patched `exit 1` comparison) remains a
separate `not_run` obligation.
