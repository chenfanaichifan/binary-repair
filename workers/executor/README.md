# Guest executor (T6.2)

Status: **COMPLETE for T6.2 guest executor and executor-account isolation**
(2026-11-07). A synthetic Route B screening run passed through the installed
`/usr/local/sbin/jobwrap-executor` with uid 1003, `CapEff=0`, `NoNewPrivs=1`,
`seccomp=2`, a separate netns and no default route; 18/18 output sums. The
`repair` account (uid 1002) was retired. Evidence:
`docs/development/handoffs/evidence/t62-guest-executor-conformance-2026-11-07/`.

`run_job.py` is guest-only. It refuses the host, refuses root, and refuses any
account other than the fixed unprivileged executor uid (`1003`). A non-plan run
also refuses unless its own pid has a root-owned wrapper attestation at
`/run/binrepair/executor/attest-<pid>.json`; setting `BINARYREPAIR_JOBWRAP`
alone is not enough. `--plan-only` verifies the package without running
anything. `--allow-unattested` exists only for synthetic smoke tests and must
never be used for a real candidate.

## Account isolation

The guest has `runner` (uid 1003), no sudo, a locked password, and no SSH keys.
The executor accepts that account and nothing else:

| euid | result |
|---|---|
| 1003 (`runner`) | accepted |
| 0 (`root`/`lab` with sudo) | refused: `root_forbidden` |
| 1000 (`lab`) | refused: `uid_mismatch` |
| 1002 (`repair`) | retired 2026-11-07; `no such user` |
| 1004 (`m4verify`) | refused: `uid_mismatch` |
| 1005 (`m5verify`) | refused: `uid_mismatch` |

`repair` was retired with `userdel -r`; its home is archived root-only at
`/var/backups/repair-home-20261107.tar.gz`. `runner` still exists with uid/gid
1003 and no sudo/SSH.

`isolation.json` records `uid/euid/gid`, `CapEff`, `NoNewPrivs`, `Seccomp`, the
network namespace, kernel and the wrapper attestation path. When the wrapper is
used it also records `jobwrap_attested: true`, `jobwrap_pid` and
`jobwrap_path`, and `claimed_scope` says the wrapper enforced account, netns,
capabilities, NNP and seccomp. Without the wrapper it claims **account only**;
the Python process does not create the netns or drop capabilities itself.

## Package

```text
package/
  package.json
  original.elf
  contract.json
  tests/valid.json
  tests/invalid.json          # route_a only
  candidate.elf               # required unless route_b builds from c_source
  replacement.c               # optional route_b source
  edit-manifest.json          # optional route_a static evidence
  audit.json                  # optional route_a static evidence
  readelf-audit.txt           # optional route_a static evidence
  evidence/                   # optional route_a typed evidence
  SHA256SUMS                  # every other file, sorted
```

`package.json`:

```json
{
  "schema_version": 1,
  "job_id": "job-1",
  "route": "route_b",
  "purpose": "repair",
  "func": "badSink",
  "mode": "fixed",
  "input_mode": "none",
  "run_manifest": true,
  "original": "original.elf",
  "contract": "contract.json",
  "tests": "tests",
  "candidate": "candidate.elf",
  "expected": {
    "original_sha256": "<64 lowercase hex>",
    "candidate_sha256": "<64 lowercase hex>",
    "contract_sha256": "<64 lowercase hex>"
  }
}
```

Rules:

- every path is package-relative; absolute paths, `..`, `.` components, and
  symlinks are rejected;
- `SHA256SUMS` must list **every** file except itself, exactly once;
- each file is limited to 64 MiB and the package to 256 MiB;
- on POSIX, group/world-writable package entries are rejected;
- `original_sha256` is mandatory; `candidate_sha256` is mandatory when a
  candidate is present; `contract_sha256` is the contract **file** hash;
- `route_a` also requires `tests/invalid.json`; `route_b` supports the no-input
  case with only `tests/valid.json`;
- `purpose: screening` defaults to `mode: roundtrip` and no runtime manifest;
  `purpose: repair` defaults to `mode: fixed` with `--run-manifest`. An explicit
  `run_manifest` overrides the default.

## Commands

Guest, through the installed fixed wrapper (setuid root; caller stays `lab`):

```sh
/usr/local/sbin/jobwrap-executor executor \
  /opt/binrepair/executor-repo \
  /var/lib/binrepair/jobs/<job>/staging/<attempt> \
  /var/lib/binrepair/jobs/<job>/runs/<run>/attempts/<attempt>.routeb
```

The wrapper creates `<out>` as `runner:runner 0750`, drops to uid 1003, writes
`/run/binrepair/executor/attest-<pid>.json`, and execs the fixed absolute path
`/opt/binrepair/executor-repo/workers/executor/run_job.py`. It accepts only
`/opt/binrepair/executor-repo` as `<repo-root>`, only packages under
`/var/lib/binrepair/jobs/`, and only a non-existent `<out>`.

Build and install — **inside the guest only**:

```sh
gcc -O2 -Wall -Wextra -Werror -o /tmp/jobwrap-executor workers/executor/jobwrap_executor.c
install -o root -g lab -m 4750 /tmp/jobwrap-executor /usr/local/sbin/jobwrap-executor
install -o root -g root -m 0644 workers/executor/run_job.py \
  /opt/binrepair/executor-repo/workers/executor/run_job.py
```

Host-safe package check:

```sh
/opt/angr-venv/bin/python workers/executor/run_job.py \
  --package <package> --out <out> --guest-ack --plan-only
```

Synthetic smoke test as `runner`, with no real candidate and no wrapper:

```sh
sudo -u runner /opt/angr-venv/bin/python workers/executor/run_job.py \
  --package <synthetic-package> --out <out> --guest-ack --allow-unattested
```

That run records `jobwrap_attested: false` and `claimed_scope` account-only; it
is not isolation conformance. A direct non-plan run without a valid wrapper
attestation is refused, even if `BINARYREPAIR_JOBWRAP` is set by hand.

`run_job.sh` remains a small pre-Python `id -u` check; it is not the production
isolation path. Use `jobwrap-executor` for a real run.

## Output

```text
bundle.json          route_a/route_b + gate status + artifact names (host ingest)
result-bundle.json   legacy V0-V5 shape (worker adapter)
isolation.json       account/kernel/capability/netns and wrapper-attestation state
run.log              commands and return codes; stdout/stderr under logs/
SHA256SUMS           all output files except itself
bundle-sha256.txt    sha256 of SHA256SUMS
```

Gate derivation is deliberately conservative:

| gate | source | not promoted when |
|---|---|---|
| V0 | package hashes and `edit-manifest.json` | any hash differs |
| V1 | `audit.json#pass` | audit missing or false |
| V2 | never | always `not_run` (producer measurement only) |
| V3 | `manifest-repaired.json#repaired_pass` | missing, false, or only a round-trip comparison |
| V4 | never | always `not_run` (independent verifier owns it) |
| V5 | `reproducibility.json` measured+pass | missing or not measured |

No outcome, `verified_by`, or gate verdict is written. V2/V4 stay `not_run`.
The existing T8.3 producer markers are read-only inputs and are not modified.

## Wrapper (installed)

`/usr/local/sbin/jobwrap-executor` is a new binary, separate from the Gate 3/4
`/usr/local/sbin/jobwrap` (which remains `0700 root:root` and is unchanged).
It is installed `04750 root:lab` (only `lab` may execute it), source `workers/executor/jobwrap_executor.c`,
sha256 `85be8aefea123c3825b807899486914c149cc371b95ce9ce88af1d8aeb1b2f60`.
It accepts exactly:

```text
jobwrap-executor executor <repo-root> <package> <out>
```

and refuses any other repo, a package outside `/var/lib/binrepair/jobs/`, an
existing out directory, symlinks in the package/repo trees, or non-root-owned /
group-writable package/repo entries. It creates the no-egress netns + mount/uts
namespaces, remounts `/proc`, installs a seccomp denylist, sets `NoNewPrivs`,
drops groups/gid/uid to 1003, applies rlimits, clears the environment, writes
the root-owned pid-bound attestation, and execs the fixed Python path and argv.

The formal conformance run (synthetic Route B screening, `run_manifest: false`)
and the negative checks are recorded in
`docs/development/handoffs/evidence/t62-guest-executor-conformance-2026-11-07/`. V2 and V4
stay `not_run`; no `verified_by` is written.
