# M1 close-out against the review list

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Suite: `357 passed / 3 skipped / 1 failed` (the failure is the host missing
  `readelf`/`objdump`)

The pasted review list was written against an older baseline. Items 3, 4 and 5
of the M1 section were already implemented in `316ce1b`; this record states what
was already true, what was wrong in the repo, and what was genuinely missing.

## Item 1 - attempt list endpoint (was missing)

```
GET /api/jobs/{job_id}/attempts
{"attempts": [{"id", "run_id", "route", "attempt_no", "status", "outcome",
               "reason", "candidate_sha256", "started_at", "finished_at"}]}
```

Field mapping is explicit because the table names differ from the client
contract: `attempt_no` is `attempts.sequence`, `status` is `attempts.phase`, and
`reason` is the renamed `reason_code` from migration 003. Ordering is by run
start then attempt sequence, so retry history reads oldest first.

`GET /api/jobs/{id}` now carries `routes.A.attempt_id` / `routes.B.attempt_id`.
Without it the GUI could show obligations but not open their evidence.

Verified: every returned id is accepted by `/api/attempts/{id}/evidence`
(`test_attempts_endpoint_exposes_ids_that_open_evidence`).

## Item 2 - obligation scope (was missing)

- `app/db/migrations/005_obligation_scope.sql` adds `obligations.scope` and
  backfills existing rows.
- `app/domain/scopes.py` is the single mapping:

| gate | kind | scope |
|---|---|---|
| V0 | identity | metadata |
| V1 | structure | binary |
| V2 | interface | binary |
| V3 | behaviour | replay |
| V4 | symbolic | model |
| V5 | reproducibility | replay |

- `persist_obligations` writes the scope at insert time (and on conflict), so the
  stored value is the host's decision, not a render-time guess.
- `GET /api/jobs/{id}/obligations` returns it per row; `list_obligations` falls
  back to the mapping only for a database that predates the migration.

Verified both through the API and directly with SQL, for both routes.

The scope is deliberately conservative: V4 stays `model` even when it passes.
That is the structural reason a passing V4 cannot be read as machine-level proof.

## Item 3 - V3 split (already done)

`attempt_writer.py` registers `routeb_manifest_compare` as `round_trip` (no V3
credit) and `routeb_manifest_repaired` as `repaired_behaviour` (credit only when
the repaired run passed). `GET /api/jobs/{id}/v3` reports both kinds with
`v3_credit`. Covered by `tests/integration/test_m3_package_intake.py`.

## Item 4 - auth (partly already done, two gaps closed)

Already in `316ce1b`: non-loopback `Origin` and `Sec-Fetch-Site: cross-site`
rejected on `POST/PUT/PATCH/DELETE`, optional `BINARYREPAIR_CONTROLLER_TOKEN`
compared with `hmac.compare_digest`.

Closed in this pass:

- `/api/runs/{run_id}/attempts/retry` is now proven guarded before any lookup
  (`test_retry_is_guarded_before_any_lookup`).
- `POST /api/jobs` rejects a non-ELF body with 400. Previously any bytes were
  accepted and stored as `original.bin`; a shell script would have entered every
  later hash comparison and route.

The `Host` check the list mentions was already there; it is not authentication,
which is why the Origin/token layer exists on top of it.

## Item 5 - artifact role table (existed, but was wrong)

`docs/interfaces/artifact-roles-v1.md` existed and did **not** match the code:

- it listed `route_a_evidence` / `route_b_evidence`, which are never written;
- the ingest adapter writes `f"{gate.lower()}_evidence"`, i.e. `v0_evidence` ...
  `v5_evidence`;
- `legacy_artifact` (used for every file in an INTERFACE-v1 bundle) was missing.

Fixed, and a test now enforces it: every `role` present in `artifacts` after a
real ingest must appear as a first-column row in the table
(`test_every_ingested_artifact_role_is_documented`).

## Item 6 - structured ai_usage (was a string)

Shape is now `{"input_tokens": int, "output_tokens": int}` or `null`. A partial
record is `null` rather than zero-padded.

Sources removed:

| File | Before |
|---|---|
| `app/controller_api.py` | `"unavailable"` |
| `app/backend.py` | `"unavailable"` |
| `app/visuals.py` | `"12.4k input / 1.6k output tokens"` (invented) |
| `app/demo.py` | `"unavailable"` and an invented pair |
| `tools/controller_service.py` | `"unavailable"` |

Data comes from the latest `assistant_plans.usage_json`; nothing else records
tokens today (`model_calls` exists in the v2 schema comments but is not written
by any live path - that is M5 item 15, not M1).

UI: `poll.js` formats `null` as the localized "not provided" label; the
three templates use the same fallback instead of rendering `null` or an object.

## Not M1, untouched

M3 items 7-8, M4 items 9-12, M5 items 13-15, Lead items 16-19. Two notes:

- M5 item 13 is the same defect as M1 item 3 and is already satisfied on this
  branch; the writer has one path, not two.
- Lead item 17 is partly done (all runtime entry points default to `var`); the
  `roundtrip.elf` duplicate paths are outside this branch.

T8.3 remains blocked per M5's record 91.

## Branch

`m1/t6-host-backend` is ahead of `canonical/m1-m5-integration`; the canonical
branch still needs a push with a fresh token.
