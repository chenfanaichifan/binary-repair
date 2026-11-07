# 152 — T6.2 complete: jobwrap-executor conformance and repair retirement

- Date: 2026-11-07
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput`
- Supersedes the open items in record 151.
- Status: **T6.2 guest executor and executor-account isolation complete.**
  T8.3 stays blocked; V2/V4 stay `not_run`; no `verified_by` is written.

## 1. What changed

| change | detail |
|---|---|
| new wrapper | `/usr/local/sbin/jobwrap-executor`, `04750 root:lab`, source `workers/executor/jobwrap_executor.c` |
| old wrapper | `/usr/local/sbin/jobwrap` untouched; it remains the Gate 3/4 binary bound to `b232d60b…` |
| fixed repo | `/opt/binrepair/executor-repo`, `root:root`, group/other write removed |
| executor code | `workers/executor/run_job.py` now validates a root-owned, pid-bound attestation; env presence alone is refused |
| account | `repair` (uid/gid 1002) removed with `userdel -r`; `runner` uid/gid 1003 retained |
| evidence | `docs/handoffs/evidence/t62-guest-executor-conformance-2026-11-07/` |

The wrapper is a new binary, not a reconstruction of the lost `jobwrap_v3.c` and
not a replacement for the old `jobwrap`. Gate 4 evidence still binds the old
binary.

## 2. Wrapper contract

```text
jobwrap-executor executor <repo-root> <package> <out>
```

- `<repo-root>` must resolve to exactly `/opt/binrepair/executor-repo`.
- `<package>` must be under `/var/lib/binrepair/jobs/`; symlinks and
  non-root-owned or group/other-writable entries are rejected.
- `<out>` must not exist; the wrapper creates it `runner:runner 0750`.
- The wrapper refuses non-root euid, wrong argv, wrong repo, existing out and
  packages outside the jobs root.
- It unshares net/mount/uts namespaces, remounts `/proc`, installs a seccomp
  denylist for network syscalls, sets `NoNewPrivs=1`, drops groups/gid/uid to
  1003, applies rlimits, clears the environment and writes
  `/run/binrepair/executor/attest-<pid>.json` root-owned `0444` (written after
  the drop, `fchmod` done while still root).
- It execs the fixed absolute path
  `/opt/binrepair/executor-repo/workers/executor/run_job.py` with fixed argv
  `--package <package> --out <out> --guest-ack --repo-root <repo>`.

`run_job.py` verifies the attestation's path, root ownership, mode, pid,
uid/euid/gid/egid, `CapEff=0`, `NoNewPrivs=1`, `Seccomp=2`, a netns different
from the wrapper-recorded host netns, no default route, the fixed wrapper path,
and matching repo/package/out. Direct `runner` runs with a stale or fake
attestation are refused.

Build/install (guest only):

```sh
gcc -O2 -Wall -Wextra -Werror -o /tmp/jobwrap-executor workers/executor/jobwrap_executor.c
install -o root -g lab -m 4750 /tmp/jobwrap-executor /usr/local/sbin/jobwrap-executor
install -o root -g root -m 0644 workers/executor/run_job.py \
  /opt/binrepair/executor-repo/workers/executor/run_job.py
```

## 3. Account retirement

Before deletion: `repair:x:1002:1002::/home/repair:/bin/bash`; no `repair`
processes. Home was archived first:

```text
/var/backups/repair-home-20261107.tar.gz
0600 root:root
sha256 b0ce3cdbce56cccf08089bcb659e58855cf85b551dc0c1511349ae619f2a7b1e
```

`userdel -r repair` returned 0 (mail spool absent). After: `getent passwd repair`
empty, `id repair` -> `no such user`, group `repair` absent, `runner` still
`uid=1003(runner) gid=1003(runner)` and the wrapper still succeeds.

One access-mode change was required for the executor path: `/var/lib/binrepair`
was `0700`; it is now `0711` (traverse-only) so uid 1003 can reach
`/var/lib/binrepair/jobs` (`0755`). The evidence subtree
`/var/lib/binrepair/evidence` stays `0700`. The archive and old evidence remain
root-only.

## 4. Conformance evidence

Synthetic Route B screening package, `run_manifest: false`; no manifest or
candidate was executed. The package reuses the public CWE-416 fixture hashes
(`original c9c2632e…23c9`, `candidate 46d16e99…fcd0`, `contract 8a2b408c…e3c3b`)
without modifying T8.3.

```text
command: /usr/local/sbin/jobwrap-executor executor \
           /opt/binrepair/executor-repo \
           /var/lib/binrepair/jobs/t62-conformance-20261107/staging/pkg \
           /var/lib/binrepair/jobs/t62-conformance-20261107/runs/run5
exit: 0
bundle_sha256: 9f4d9ac804099b0f00765765113ce2406074f608b4455519c7362ca34b24ed4c
gates: V0 passed, V1 passed, V2 not_run, V3 not_run, V4 not_run, V5 not_run
outputs: 18/18 SHA256SUMS OK
```

Measured isolation:

```text
uid/euid/gid/egid = 1003, supplementary groups = []
CapEff = 0000000000000000
NoNewPrivs = 1
Seccomp = 2
netns = net:[4026532221], host_netns = net:[4026531840], default route = none
jobwrap_attested = true, jobwrap_pid = 16505
```

Hashes:

| item | sha256 |
|---|---|
| wrapper binary | `85be8aefea123c3825b807899486914c149cc371b95ce9ce88af1d8aeb1b2f60` |
| `run_job.py` (installed = host) | `1176b03ac04001af262d75e885c66ec24ff69ddff49cc4da316fc8ba622e9a72` |
| wrapper source | `6a8b8a5707ec843bbde692e4e76820a0ca07fa5d117b3c150bc8e893fd47c309` |
| evidence `SHA256SUMS` | `213c572dc64e56f5934137e5a1812bf2643358707546c8f68cac2ae617a23049` |

## 5. Negative checks

```text
runner invokes wrapper directly         -> Permission denied (mode 04750 root:lab, rc 1)
run_job.py as runner, old attestation pid -> refusing: jobwrap attestation is for a different pid (rc 2)
run_job.py as runner, fake env path     -> refusing: jobwrap attestation missing: /tmp/fake-attest.json (rc 2)
wrong repo                              -> repo-root must be exactly /opt/binrepair/executor-repo (rc 2)
existing out                            -> out already exists (rc 2)
package outside jobs root               -> package must be under /var/lib/binrepair/jobs/ (rc 2)
id repair                               -> no such user
sudo -u runner id                       -> uid=1003(runner) gid=1003(runner)
```

## 6. Host-safe checks

```text
python workers/executor/self_test.py
guest executor self-test: 9/9 passed

uv run --no-project --with pytest --python 3.12 python -m pytest tests/test_guest_executor.py -q
9 passed
```

## 7. Boundaries and rollback

- No T8.3 producer marker, `V2-interface.json`, `V4-not-run.json`, candidate,
  contract or fixture byte was edited. The CWE-416 fixture was read as package
  input only.
- The old `/usr/local/sbin/jobwrap` is untouched; Gate 3/4 evidence is unchanged.
- No host compile occurred. The wrapper was compiled inside the guest.
- No `verified_by` and no gate promotion. The delivery zip referenced in the handoff note transports this evidence; it is not a new verdict.
- Rollback: remove `/usr/local/sbin/jobwrap-executor` and
  `/opt/binrepair/executor-repo`; restore `repair` only from the root-only
  archive if the Lead explicitly reverses the access decision. Old `jobwrap`
  needs no rollback.
- `repair` retirement is an access change; it was explicitly approved by the
  VMer in this task.

## 8. Not claimed

- This is not a real repair run; the conformance package is synthetic and its
  `run_manifest` is false.
- V2 and V4 remain `not_run`; T8.3 remains blocked on M4/Lead.
- No V0–V5 verdict or `verified_by` is created here.
