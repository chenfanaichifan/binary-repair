# Guest broker — host-safe executor (T6.2, M3 task-11)

Status: **host-safe part implemented**. The guest-side `jobwrap` binary and the
actual VM execution are owned by VMer and remain `not_run` until the
conformance window is provided.

## What this is

The host side of the narrow VM task protocol. It turns the six fixed operations
(`analyze`, `assemble`, `compile`, `apply`, `test`, `verify`) into typed
manifests and wraps them in a typed `TaskRequest` the guest broker can enforce.
It validates and plans only.

Hard boundaries this module enforces (and never violates):

| Rule | How it is enforced |
|---|---|
| No shell string | Operations carry typed fields only; there is no string-to-exec path. |
| No arbitrary path | Artifacts are referenced by `artifact_id` + `sha256`, never a filesystem path. |
| No argv array | Test arguments live inside the frozen test manifest, not here. |
| No binary execution on the host | Nothing in this module spawns a process or loads an ELF. |
| Fail closed | A missing hash, a hash mismatch, an unregistered id, or a missing `scope_authorized` rejects the request before it reaches the guest. |
| Scope gate | `apply` carries `scope_authorized`; without it the request is refused. |

## Operations

```python
from workers.broker import validate_operation

op = validate_operation({
    "kind": "verify",
    "candidate": {"artifact_id": "cand-1", "sha256": "<64 hex>"},
    "obligation": "behaviour",
    "evidence_artifact_id": "ev-1",
})
```

Six closed operations, each a Pydantic model with `extra="forbid"`:
`AnalyzeOp`, `AssembleOp`, `CompileOp`, `ApplyOp`, `TestOp`, `VerifyOp`.

## Task request

```python
from workers.broker import build_task_request

req = build_task_request(
    job_id="job-1",
    run_id="run-1",
    idempotency_key="run-1-route-a-0001",
    operations=[{"kind": "verify", "candidate": {...}, "obligation": "behaviour",
                 "evidence_artifact_id": "ev-1"}],
    allowed_artifact_ids=frozenset({"cand-1", "ev-1"}),
)
```

`build_task_request` raises `ValueError` if an operation references an
artifact id outside `allowed_artifact_ids`. The caller must resolve that set
against the artifact store and confirm each `sha256` matches the recorded
identity; this builder enforces membership and structure, not byte identity.

## Resource limits

`ResourceLimits` carries the operational defaults from `tech_stack.md`
(CPU 300 s, address space 4 GiB, nofile 1024, fsize 256 MiB). They are enforced
here at planning time and re-enforced by `jobwrap` inside the guest.

## Conformance window (VMer task-15)

`conformance.py` declares the fixed-argv matrix (3 positive cases that must
exit 0 **and** attest isolation, 7 negative cases that must refuse with the
documented code) and `evaluate(payload)` judges an evidence file fail-closed:
a missing case is `not_run`, an isolation gap is `fail`, and an absent
attestation is `inconclusive` — never inferred.

`guest_conformance.py` is the guest-only runner. It refuses to start without
`--guest-ack`, on any non-Linux platform, and as non-root, because the host
must never execute a binary.

Window procedure and current status: `docs/handoffs/95-vmer-conformance-window.md`.

## What is still missing (not claimed as done)

- The guest-side `jobwrap routea` mode is **not compiled** (see
  `workers/route_a/JOBWRAP_ROUTEA.md` and record `88` §4.3); until it is, the
  `apply`/`test`/`verify` operations and the four `routea` conformance cases are
  `not_run` / `inconclusive` end to end.
- The artifact-store resolution that feeds `allowed_artifact_ids` and confirms
  hashes is the job controller's responsibility and is not implemented here.
- No conformance window has been executed; the record explicitly does not claim
  a pass.
