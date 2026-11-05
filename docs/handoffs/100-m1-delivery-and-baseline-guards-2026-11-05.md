# Shared delivery root, baseline guards, and what record 91 is not

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Base: `65aeb01`; ingest parity in `f11a165`
- Suite: `365 passed / 3 skipped / 1 failed` (host has no `readelf`/`objdump`)

## 1. delivery/ is now a tracked, shared root

`.gitignore` had `/delivery/`. On this host the directory did not even exist, so
every record that says "the bundle is in `delivery/`" (27, 30, 44, 47) describes
a file another member could not fetch. That is the same failure that blocked the
v2 gate-3 bundle and the transfer bundle: evidence that cannot be re-hashed by
the reader is not evidence.

Changes:

- removed the `/delivery/` rule and replaced it with a comment explaining why it
  must not come back;
- added `delivery/README.md` (rules: hash every artifact, no scratch, no
  secrets, one root per package);
- added `delivery/MANIFEST.md` listing both tracked roots (`delivery/` and the
  historical `dist/`), so a reader does not have to guess which one holds a
  package;
- `tests/test_delivery_visibility.py` fails if the ignore rule returns, if the
  README/MANIFEST leave the tree, or if a blanket `*.zip` / `*.bundle` rule is
  added.

Reading is only proven by a push. The branch still cannot be pushed without a
fresh token, so the "M4/M5 can read it" half is true of the repository rule and
not yet true of the remote. This is stated rather than assumed.

## 2. What the T6.0 baseline migration must keep

These are the guards that must stay green when this branch is rebased or the
baseline is re-cut. They are not incidental tests.

| Rule | Guard |
|---|---|
| V0 evidence is the artifact whose bytes equal `candidate_sha256`, never the first list entry | `test_v0_picks_candidate_not_first_artifact` |
| Candidate hashing applies to V0 only, not to V1-V5 | the `gate == "V0"` branch in `_legacy_payload` |
| A legacy package without `result-bundle.json` is all `not_run` | `test_legacy_without_result_bundle_is_all_not_run` |
| Prose in `handoff.json#notes` is never parsed into a gate | same test, which embeds "V2 16/16 passed; V3 6/6 repaired" |
| `result-bundle.json` must be in `handoff.json#files` | `test_legacy_result_bundle_must_be_in_sums` |
| `result-bundle.json` must also be in `SHA256SUMS` | `test_legacy_result_bundle_in_handoff_but_not_sums_is_rejected` |

The V0-only branch and the `_sums_names` check were added in `f11a165`; the
all-`not_run` behaviour comes from `3b4e492` and is unchanged.

## 3. Record 91 is a status record, not an acceptance record

`docs/handoffs/91-m5-completion-2026-11-05.md` states its own limits: "not
merged, no tag", M4's environment gaps are authoritative, and M4 "must not sign
a full pass from M5's local run alone". `42ee634` then appended the M4 verifier
row, but that row is scoped:

- host-side evidence only, no guest execution;
- no merge, tag, or live-success claim;
- the M4 verifier and the Lead are the same operator, so it is role-separated
  verification, not a two-person signature.

So this branch treats 91 as *implementation status plus a scoped verifier row*.
It is not a complete acceptance record, and no M1 document cites it as one. The
T8.3 line in record 96 quotes 91 only for "blocked", which is a status fact.

## 4. Controller / V3 / candidate binding / auth / data dir

No change this pass; the current state is:

| Area | Where |
|---|---|
| attempts + `attempt_id` | `GET /api/jobs/{id}/attempts`, `tests/integration/test_contract_gaps.py` |
| obligations scope | migration `006`, `app/domain/scopes.py` |
| V3 two kinds | `tests/integration/test_v3_kind_rows.py` (DB) |
| candidate binding | `app/domain/evidence.py::bind_candidate` |
| auth | `tests/integration/test_controller_auth.py` |
| single data dir | `tests/test_launch_config.py`, `delivery/` unrelated to runtime |

## Open

- Push still needs a token; until then `delivery/` is tracked locally but not
  yet fetched by anyone else.
- The `readelf`/`objdump` failure is environmental.
