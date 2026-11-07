# T6.2 guest executor - formal conformance, 2026-11-07

Status: **complete for T6.2 guest executor and executor-account isolation.**
This is a conformance evidence bundle, not a V0-V5 gate bundle and not a repair
verdict. It records one synthetic Route B static screening run under the fixed
wrapper. No manifest was executed, no gate was promoted, and no `verified_by`
was written.

## 1. What was installed on the guest

| item | value |
|---|---|
| wrapper | `/usr/local/sbin/jobwrap-executor`, `04750 root:lab` (setuid; only lab may execute) |
| wrapper sha256 | `85be8aefea123c3825b807899486914c149cc371b95ce9ce88af1d8aeb1b2f60` |
| executor repo | `/opt/binrepair/executor-repo`, `root:root`, no group/other write |
| `run_job.py` sha256 | `1176b03ac04001af262d75e885c66ec24ff69ddff49cc4da316fc8ba622e9a72` |
| wrapper source sha256 | `6a8b8a5707ec843bbde692e4e76820a0ca07fa5d117b3c150bc8e893fd47c309` |
| executor account | `runner` uid/gid 1003, unchanged |
| retired account | `repair` uid/gid 1002 removed; group removed; home archived root-only |

`/usr/local/sbin/jobwrap` is **unchanged**. It still carries the Gate 3/4
binding (`b232d60b...`). `jobwrap-executor` is a new, separate binary; it does
not replace the old wrapper or re-sign any Gate 4 evidence. Its executable
group is `lab`, so the untrusted `runner` account cannot invoke it.

The wrapper source is in `workers/executor/jobwrap_executor.c` and was compiled
**inside the guest** with:

```sh
gcc -O2 -Wall -Wextra -Werror -o /tmp/jobwrap-executor workers/executor/jobwrap_executor.c
install -o root -g lab -m 4750 /tmp/jobwrap-executor /usr/local/sbin/jobwrap-executor
```

`run_job.py` now refuses a non-plan run unless it can read the wrapper's
root-owned attestation at `/run/binrepair/executor/attest-<pid>.json`, for its
own pid, with `uid=euid=gid=egid=1003`, `CapEff=0`, `NoNewPrivs=1`,
`Seccomp=2`, a netns different from the host netns, and no default route.
Setting `BINARYREPAIR_JOBWRAP` alone is not enough.

## 2. The conformance run

Command, executed as `lab`:

```sh
/usr/local/sbin/jobwrap-executor executor \
  /opt/binrepair/executor-repo \
  /var/lib/binrepair/jobs/t62-conformance-20261107/staging/pkg \
  /var/lib/binrepair/jobs/t62-conformance-20261107/runs/run5
```

Package: synthetic Route B screening package, `run_manifest: false`; it reads
the public CWE-416 fixture bytes but executes no manifest and no candidate. The
package hashes are the same as record 151's screening package
(`original c9c2632e...23c9`, `candidate 46d16e99...fcd0`, `contract 8a2b408c...e3c3b`).

Observed result:

```text
ok: true
route: route_b, purpose: screening
bundle_sha256: 9f4d9ac804099b0f00765765113ce2406074f608b4455519c7362ca34b24ed4c
gates: V0 passed, V1 passed, V2 not_run, V3 not_run, V4 not_run, V5 not_run
verified_files: 5
sha256sum -c SHA256SUMS -> 18/18 OK
```

`run/isolation.json` measured inside the sandbox:

```json
{
  "uid": 1003, "euid": 1003, "gid": 1003, "egid": 1003, "groups": [],
  "cap_eff": "0000000000000000",
  "no_new_privs": "1",
  "seccomp": "2",
  "netns": "net:[4026532221]",
  "jobwrap_attested": true,
  "jobwrap_pid": 16505,
  "jobwrap_path": "/usr/local/sbin/jobwrap-executor",
  "claimed_scope": "wrapper-enforced uid 1003, no-egress netns, CapEff=0, NoNewPrivs=1 and seccomp filter; values measured here"
}
```

The wrapper's own attestation (`jobwrap-attestation.json`) additionally records
`host_netns: net:[4026531840]` and `default_route: ""`. The two netns identities
differ, so this is not the host network namespace.

## 3. Negative checks

| check | observed |
|---|---|
| `runner` invokes the wrapper directly | `Permission denied` (mode 04750 root:lab), rc 1 |
| `run_job.py` as `runner` with an old attestation path | `refusing: jobwrap attestation is for a different pid`, rc 2 |
| `run_job.py` as `runner` with a fake env path | `refusing: jobwrap attestation missing: /tmp/fake-attest.json`, rc 2 |
| `jobwrap-executor` with a different repo | `repo-root must be exactly /opt/binrepair/executor-repo`, rc 2 |
| `jobwrap-executor` with an existing out dir | `out already exists`, rc 2 |
| `jobwrap-executor` with a package outside the jobs root | `package must be under /var/lib/binrepair/jobs/`, rc 2 |
| `id repair` after retirement | `no such user`; `getent group repair` empty |
| `sudo -u runner id` after retirement | `uid=1003(runner) gid=1003(runner)` |
| wrapper run after retirement (`run5`) | rc 0, same isolation |

The full account list and the direct-run refusals are in `accounts.txt` and
`negative.txt`.

## 4. What this proves, and what it does not

Proves:

- a non-plan executor run can only occur under the fixed wrapper, because the
  wrapper is the only process that creates the root-owned pid-bound attestation;
- the wrapper enforces uid/gid 1003, an empty supplementary-group set,
  `CapEff=0`, `NoNewPrivs=1`, a seccomp filter, a no-egress netns and no default
  route;
- the executor's existing package/gate behavior still holds: V0/V1 passed,
  V2/V3/V4/V5 `not_run`, 18/18 output sums, no promotion;
- the old `repair` account is gone and `runner` still works.

Does not prove:

- a real repair manifest under the wrapper (this run set `run_manifest: false`);
- V2 or V4 acceptance; both stay `not_run`;
- any T8.3 verdict; T8.3 stays blocked on M4/Lead;
- any `verified_by` value. None is written here.

## 5. Boundaries

- No T8.3 producer marker, `V2-interface.json`, `V4-not-run.json`, candidate,
  contract or fixture byte was edited. The CWE-416 fixture was read only as
  package input.
- The old `/usr/local/sbin/jobwrap` was not modified.
- `repair`'s home was archived at `/var/backups/repair-home-20261107.tar.gz`
  (`0600 root:root`, sha256 `b0ce3cdbce56cccf08089bcb659e58855cf85b551dc0c1511349ae619f2a7b1e`)
  before `userdel -r`.
- No gate was moved up. The only account change is the approved retirement of
  `repair`. `/var/lib/binrepair` changed from `0700` to `0711` (traverse-only) so
  uid 1003 can reach `/var/lib/binrepair/jobs`; `evidence/` stays `0700`.

## 6. Files

- `run/` - full executor output (`isolation.json`, `bundle.json`,
  `result-bundle.json`, `run.log`, `SHA256SUMS`, independent views).
- `jobwrap-attestation.json` - wrapper attestation for pid 16505.
- `accounts.txt` - account list after retirement and `runner` check.
- `negative.txt` - direct-run refusals and runner/wrapper denial.
- `wrapper.txt` - installed wrapper/run_job hashes, permissions, kernel.
- `package.json`, `package-SHA256SUMS` - synthetic package metadata.
- `conformance.txt` - command/output transcript.
- `SHA256SUMS`, `bundle-sha256.txt` - this evidence bundle's own manifest.
