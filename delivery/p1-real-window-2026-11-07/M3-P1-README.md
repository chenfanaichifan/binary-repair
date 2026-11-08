# P1 real guest window - evidence (2026-11-07)

One real Route B repair attempt executed inside the disposable guest through the
installed fixed wrapper. Nothing in this directory is synthetic: the package was
built from the frozen CWE-416 no-input fixture and its recorded candidate.

## 1. Input identity

| file | sha256 |
|---|---|
| original.elf | `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9` |
| candidate.elf | `46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0` |
| contract.json | `8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b` |
| package.json | see [package/SHA256SUMS](package/SHA256SUMS) |

`purpose: repair`, `route: route_b`, `mode: fixed`, `input_mode: none`,
`run_manifest: true`, function
`CWE416_Use_After_Free__malloc_free_char_01_bad`.

Plan-only verification passed before the run with 5 verified files and
`sha256sums_sha256 = 9268b953319662fd4e7c8b5b5b4c7b39d4392c4a2253995ca1404711bfdfd931`.

## 2. Invocation and result

```text
/usr/local/sbin/jobwrap-executor executor \
  /opt/binrepair/executor-repo \
  /var/lib/binrepair/jobs/p1-cwe416-noinput-20261107/staging/a1 \
  /var/lib/binrepair/jobs/p1-cwe416-noinput-20261107/runs/run1/attempts/a1.routeb
```

- wrapper exit code: `0`
- `bundle_sha256` (sha256 of the output `SHA256SUMS`): `dbc032fb5a1a846b9a23ec3e379442b8f97ba431b61f00aa9794f75d87973b2f`
- output files: 19, rehashed on the host with 0 mismatches
  ([bundle/a1.routeb/SHA256SUMS](bundle/a1.routeb/SHA256SUMS))

| gate | status | source |
|---|---|---|
| V0 | passed | package hashes match the emitted artifacts |
| V1 | passed | `audit.json#pass` |
| V2 | not_run | no guest-side V2 gate |
| V3 | passed | `manifest-repaired.json#repaired_pass` (1/1) |
| V4 | not_run | independent verifier owns it |
| V5 | not_run | build-twice not measured |

V3 detail: candidate stdout was 99 `A` bytes + `\n`, exit 0, matching the one
frozen no-input case. See
[bundle/a1.routeb/manifest-repaired.json](bundle/a1.routeb/manifest-repaired.json).

## 3. Isolation

Measured inside the run ([bundle/a1.routeb/isolation.json](bundle/a1.routeb/isolation.json)):

- uid/euid 1003, gid/egid 1003, groups `[]`
- `CapEff = 0000000000000000`
- `NoNewPrivs = 1`, `Seccomp = 2`
- netns `net:[4026532218]`, host netns `net:[4026531840]`, empty default route
- root-owned pid-bound attestation `/run/binrepair/executor/attest-1882.json`
  ([host/attest-1882.txt](host/attest-1882.txt))
- wrapper `85be8aefea123c3825b807899486914c149cc371b95ce9ce88af1d8aeb1b2f60`

## 4. Reset

See [host/reset.txt](host/reset.txt). Short form: pre-window snapshot
`p1-prewindow-20261107` (vmsd uid 15), artifacts copied out, `stop soft` rc 0,
`revertToSnapshot` rc 0, `snapshot.current = 15`, the job directory is absent on
the next boot, and the final host state is powered off with no `.lck` and no
`vmware-vmx` process.

## 5. Host ingest

The guest executor writes `bundle.json` with `gates`; `tools/host_importer.py`
requires `results`. The projection
[ingest-bundle.json](../../../outputs/p1-guest-window-20261107/ingest-bundle.json)
was accepted by the importer and written atomically
([host/ingest-check.txt](host/ingest-check.txt)). Triggering the worker then
failed at evidence binding:

```text
attempt ... failed: V0 evidence artifact is not part of job ...: original.elf
outcome=error reason=tool_failed
```

So the real bundle is transport-complete, but the host-side driver must register
the bundle's evidence artifacts before a trigger. The current path also labels a
missing/foreign artifact as `error / tool_failed`, not as an evidence rejection.

## 6. Not claimed

- No complete `success_within_scope`: V2, V4 and V5 are `not_run`.
- No outcome and no `verified_by` were written by the guest.
- This window used a controller-independent job id; it is not a controller job,
  and no p2 acceptance was run against it.
- The pre-existing `t62-conformance-20261107` job directory was left untouched.

## 7. Reproduction

Raw console captures: [host/pre-window.txt](host/pre-window.txt),
[host/window-run.txt](host/window-run.txt). The package used is under
[package/](package/). The wrapper accepts only a package under
`/var/lib/binrepair/jobs/`, root-owned and not group/world writable; the ELF
inputs were staged `0755 root:root`, JSON `0644 root:root`, and the output path
did not exist.
