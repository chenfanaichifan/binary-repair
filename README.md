# BinaryRepair MVP

Repair one public stack-buffer-overflow vulnerability in a single Linux x86-64 ELF
through two independent AI-assisted routes — direct machine-instruction patch
(Route A) and recovered-C round trip (Route B) — and compare the validation
evidence in a local browser interface.

**Status: pre-freeze.** Nothing is verified end to end. See
`docs_BinaryRepair/fixture-freeze-record.md` for what is done, what is open, and
who still has to sign.

## Layout

| Path | Contents |
|---|---|
| `agent_docs/` | Design contracts: project brief, tech stack, code patterns, testing |
| `docs_BinaryRepair/` | Member 3 records: oracle freeze, fixture freeze, VM profile, environment baseline, replies to Member 4 |
| `fixtures/public/<fixture-id>/` | The frozen public fixture: `original.elf`, `provenance.md`, `build/`, `tests/`, `evidence/` |
| `route-a/` | Member 3 work items 1–7: `docs/` decisions and `scripts/` helpers |
| `worklogs/` | Local session records — **not committed** |

## Evidence

All command output lives with the fixture it belongs to:

```
fixtures/public/<fixture-id>/evidence/NN-<topic>.txt
```

Keep the command on the first line of each file so the result can be replayed.
`route-a/docs/` points at these files; it does not copy their contents.

## Not committed

`worklogs/`, `.tmp/`, `dist/`, `.dsh-acl-recovery/`, VM files, and personal
handover notes — see `.gitignore`.

## Boundaries

- No evaluator source, reference fix, evaluator annotations, or hidden tests in
  this repository.
- Binaries are built and executed only inside the disposable Ubuntu guest.
- SHA-256 establishes identity, never correctness.
