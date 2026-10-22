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
| z3 | 5.1.0 (venv) / 5.3.1 (system python) |
| unicorn | 2.1.4 |

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

## 4. Snapshots

| uid | name | taken | power state |
|---|---|---|---|
| 4 | `clean-toolchain` | 2026-10-20 11:57 | off |
| 5 | `job-isolation` | 2026-10-22 16:50 | running (includes memory) |
| 6 | `clean-baseline` | 2026-10-22 16:54 | off |

Disk state is a chain, no single-file identity:

| file | bytes | SHA-256 |
|---|---:|---|
| `disk.vmdk` | 6,792,544,256 | `7dec112509c833a66b44c2e1aebdc607d33b323ca61351d7cfe0c83886101468` |
| `disk-000001.vmdk` | 33,882,112 | `28451ed9fcf8f54f6fbe0c337c9fe8f6e4823dba08e242daae52855b4647bd92` |
| `disk-000002.vmdk` | 12,320,768 | `b501715b37e954e1ea509ab138d03bb34e45d5672a5b5192dc28dc72bd37100c` |

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
