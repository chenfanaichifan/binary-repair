# State change — 2026-10-22

This note records changes made after `provenance.md` was frozen and is not
part of the frozen artifact set (`fixtures/.../SHA256SUMS`). It supersedes
`provenance.md` §13.1–13.2 **on these specific points only**; the frozen file
is intentionally left unedited so its hash stays valid.

## 1. Toolchain completed

Installed and smoke-tested in the guest:

| Tool | Version |
|---|---|
| clang / lld | 18.1.3 |
| Ghidra | 12.1.4 PUBLIC (build 2026-09-21) |
| OpenJDK | 21.0.12.1 |
| LIEF | 1.0.0 |
| angr | 10.0.4.post1 (bundles claripy as `angr.rustylib.claripy`) |
| z3 | z3-solver 5.1.0.0 — the **only** z3 in the guest; the system-python 5.3.1 copy was removed on purpose |
| unicorn | 2.1.4 |
| Patcherex2 | 0.2.14 (purseclab/Patcherex2) |
| keystone-engine | 0.9.2 |
| capstone | 5.0.9 |
| intelhex | 2.3.0 |
| pypcode | 4.0.1 |
| requests | 2.34.2 (+ urllib3, certifi, idna, charset-normalizer) |
| pyelftools (venv) | 0.33 |

Patcherex2 and its declared runtime set live in `/opt/angr-venv` (55 packages;
full lock is `pip freeze` from that venv).

**Interpreter split — the broker must pin one interpreter per operation.** The
V4/Patcherex2 stack is in `/opt/angr-venv`; `pwntools 4.15.0` is installed only
in the system `python3` (99 packages) and is **not importable from the venv**.
Calling `pwntools` through `/opt/angr-venv/bin/python` raises
`ModuleNotFoundError`. Either install it into the venv or record "pwntools only
via system python3"; whichever is chosen, each operation must name the
interpreter it used.

**capstone version discrepancy.** The system-python `capstone` package is 5.0.9
while its module reports `__version__ = 5.0.7`; the venv copy reports 5.0.9
consistently. Record both numbers, not one — otherwise a replay that reads the
other number looks like a misinstall.

Smoke tests: angr loads `original.elf` (AMD64, entry 0x401170); Ghidra
`analyzeHeadless` completes an import and full analysis; `python3 -c "import
lief, z3"` succeeds.

Consequence: `provenance.md` §13.1 ("V4 is blocked" for lack of tools) is
**superseded** — the missing tools are now present. The V4 *verdict* is still
Member 4's to make; tool availability is not a V4 result.

## 2. Execution user

`runner` (uid 1003) exists, has no sudo, and cannot read `~/evaluator`.

## 3. Job-time network

`/opt/binrepair/run-isolated.sh` runs a command as `runner` inside an empty
network namespace. Measured 2026-10-22:

- `ip -brief addr` → only `lo DOWN`;
- `curl https://example.com` → `Could not resolve host` after a 15 s DNS timeout;
- the guest itself still reaches the internet (`http=200`);
- the host's SSH session is unaffected.

Not yet wired into any broker path, so this is a capability, not an enforced rule.

### Test-only wrapper: `/usr/local/bin/jobwrap`

`/usr/local/bin/jobwrap` is a test-only isolation wrapper (91-byte shell
script, `root:root 0755`, sha256 `877dd4c4…a1d3`, identical content and hash to
`/opt/binrepair/run-isolated.sh`, which was created at 16:44). Invoked by the
operator as root; it creates an empty network namespace and drops to uid 1003
before `exec`'ing the target. It performs no argument validation, writes no
evidence, enforces no whitelist or resource limit, and is **not** the product
broker.

```sh
#!/bin/sh
exec unshare --net --fork --pid --mount-proc --setuid=1003 --setgid=1003 -- "$@"
```

Provenance and status, stated plainly so the record is not read as more than it
is:

| Item | Fact |
|---|---|
| Created | 2026-10-22 17:17, by the operator, for this isolation check |
| Origin | copied from `/opt/binrepair/run-isolated.sh` (created 16:44, same hash) |
| Does | empty netns → `setuid`/`setgid` 1003 → `exec` the passed argv |
| Does not | write logs or evidence, validate argv, apply a whitelist, or cap resources |
| Ownership | test scaffolding, not a product component; the product counterpart is the broker |
| Snapshot status | **in no snapshot** — created 17:17, after `toolchain-v4-ready` (17:14), so it exists only in the active layer `disk-000004` and disappears on rollback |

## 4. Snapshots

Four snapshots exist (2026-10-22). `BinRepair-Lab.vmsd` carries
`snapshot.numSnapshots = "4"`, current uid `7`, chain `4 → 5 → 6 → 7`.

| uid | name | taken | power state |
|---|---|---|---|
| 4 | `clean-toolchain` | 2026-10-20 11:57 | off |
| 5 | `job-isolation` | 2026-10-22 16:50 | running (includes memory) |
| 6 | `clean-baseline` | 2026-10-22 16:54 | off |
| 7 | `toolchain-v4-ready` | 2026-10-22 17:14 | off (28,062-byte `.vmsn`) |

### Snapshot chain (2026-10-22, VM shut down)

| layer | bytes | SHA-256 | snapshot |
|---|---:|---|---|
| `disk.vmdk` | 6,792,544,256 | `7dec112509c833a66b44c2e1aebdc607d33b323ca61351d7cfe0c83886101468` | clean-toolchain (uid 4) |
| `disk-000001.vmdk` | 33,882,112 | `28451ed9fcf8f54f6fbe0c337c9fe8f6e4823dba08e242daae52855b4647bd92` | job-isolation (uid 5, memory) |
| `disk-000002.vmdk` | 12,320,768 | `b501715b37e954e1ea509ab138d03bb34e45d5672a5b5192dc28dc72bd37100c` | clean-baseline (uid 6) |
| `disk-000003.vmdk` | 75,890,688 | `1759a66ffd0a0d7eda06e2f676b0e9134682d1fb670099de6ffb98675c2fb300` | toolchain-v4-ready (uid 7) |
| `BinRepair-Lab.vmsd` | 1,609 | `ba9b9bee8397ddd20d2d5e50eaf8bd550e59d7ebed35bad02b0b6febb50dfd97` | tree definition |

`disk-000004.vmdk` is the active write layer and belongs to no snapshot; it is
held open while the guest runs, so it has no stable hash.

`job-isolation` was taken while running and includes memory; it is not a reset
baseline. A reset to `toolchain-v4-ready` discards `disk-000004.vmdk`, which is
where `jobwrap` (17:17) lives.

`provenance.md` §13.2 item 1 ("zero snapshots") is **superseded** by this table.

## 5. What still stands from provenance §13.2

- `lab` still has passwordless sudo — jobs are unprivileged only when invoked
  through the wrapper;
- no hypervisor-level egress block;
- tools are not on a read-only mount;
- V4 has not been run.

## 6. When `provenance.md` may be edited

Only when the team decides to **re-freeze**. That is a three-step procedure, not
a one-step edit:

1. publish a new `provenance.md` **and** a `SHA256SUMS.v2`;
2. keep the existing `SHA256SUMS` (v1) as history — do not overwrite it;
3. record in the freeze record that v2 supersedes v1 and that v1's hashes can
   still be checked in the older record.

That keeps old and new evidence both verifiable, instead of leaving a hash
mismatch with no explanation.
