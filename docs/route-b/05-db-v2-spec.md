# DB v2 (002) interface decisions

**Status:** 2026-10-20, 002 + 003 implemented and merged into the shared tree (`member-5/acceptance-verdict`).
**Baseline:** `app/db/schema.sql` on main (jobs + artifacts) is recorded as v1; 002 is recorded as v2.
**Principle:** only creating a new database from the v1 baseline is supported; detecting the old 001 fails immediately; no silent mixing, no automatic data deletion.

---

## 1. canonical serialization: a single implementation in `app/domain/contracts.py`

The controller **may only** call the four entry points below, and must not write its own `json.dumps` / sorting:

```python
from app.domain.contracts import SecurityContract

SecurityContract.from_dict(data: dict[str, Any]) -> SecurityContract
contract.canonical_payload() -> dict[str, Any]
contract.canonical_json() -> str
contract.sha256() -> str

# for callers that only have a dict (controller/approval):
canonical_contract_json(data: dict[str, Any]) -> str
contract_sha256(data: dict[str, Any]) -> str
```

Rules:

- `canonical_json()` fixes:
  `json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
- the four list fields are sorted first: `authorized_edits`, `allowed_calls`,
  `environment_assumptions`, `required_obligations` (order carries no semantics).
- text allows only printable ASCII (plus `\n`/`\t`).
- when storing:
  - `contracts.body_json = contract.canonical_json()` (exactly this text, do not pretty-print it again)
  - `contracts.sha256 = contract.sha256()`
- when reading:
  ```python
  stored = SecurityContract.from_dict(json.loads(row["body_json"]))
  assert stored.sha256() == row["sha256"]
  ```
  If they disagree, reject; do not "compute a new one and overwrite the old value".
- `reviewed_scope_sha256` now equals `contracts.sha256`; `runs.manifest_sha256` is bound separately.
  Both are written at approval time, and the acceptance engine only checks that they are non-empty.

**Forbidden:** a second `sorted(...)` or `json.dumps(..., sort_keys=True)` appearing in the controller.

---

## 2. Handling the old 001: fail, do not migrate

The v1 baseline is `app/db/schema.sql`, recorded as:

```text
schema_migrations(version=1, name='base')
```

002 is recorded as `version=2, name='ai_tables'`.

**When 001 is detected: raise `LegacySchemaError`, execute no DDL, drop no tables, perform no automatic conversion.**

Detection order (`connection.init_db()` is called once at application startup):

1. open the connection, `PRAGMA foreign_keys=ON`;
2. `CREATE TABLE IF NOT EXISTS schema_migrations`;
3. **check for legacy first** (before any `schema.sql`/002):
   - `PRAGMA table_info(jobs)` contains `fixture_id` → old 001;
   - or `schema_migrations` has `version=1` and `name <> 'base'` → old 001;
   - or `schema_migrations` has `version=2` but no `version=1` → corrupt;
   - on a hit → raise, with a message that states exactly:
     `legacy 001 schema detected; delete var/app.db and recreate; no automatic migration`
4. execute `schema.sql` (`CREATE TABLE IF NOT EXISTS`, idempotent);
5. insert `(1,'base')` (if absent);
6. artifacts duplicate pre-check (see §3);
7. apply `002_ai_tables.sql`;
8. optionally `PRAGMA user_version=2`.

**No 001→002 migration script is provided.** 001 never entered main; if a development database has run 001, delete and recreate it.

---

## 3. Duplicate artifacts: fail and list them, do not clean up automatically

002 adds:

```sql
ALTER TABLE artifacts ADD COLUMN attempt_id TEXT REFERENCES attempts(id);
ALTER TABLE artifacts ADD COLUMN media_type TEXT NOT NULL
    DEFAULT 'application/octet-stream';
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifacts_job_path
    ON artifacts(job_id, relative_path);
```

SQLite cannot `ALTER TABLE ... ADD UNIQUE`, so a unique index is used instead.

**Pre-migration check** (in `migrate.py`, before executing 002):

```sql
SELECT job_id, relative_path, COUNT(*) AS n
FROM artifacts
GROUP BY job_id, relative_path
HAVING n > 1;
```

- rows present → raise `DuplicateArtifactsError`, with the full `(job_id, relative_path, n)` list in the message;
  the migration aborts and none of 002's statements are executed.
- no rows → continue; the unique index is the second line of defense.
- **never automatically delete or merge rows**: artifact rows are evidence, and silently deleting data is worse than a failed migration.

Operator handling: decide by hand, using `sha256`/`role`, which row to keep, delete the extra rows, then re-run the migration.

**Order:** create `attempts` first, then `ALTER artifacts ... REFERENCES attempts(id)`, otherwise the foreign key cannot find the table.

---

## 4. Key constraints of 002

| Table | Constraints |
|---|---|
| `contracts` | `UNIQUE(job_id, revision)`, `UNIQUE(job_id, id)`; `body_json` is canonical text |
| `runs` | `UNIQUE(job_id, idempotency_key)`; `FOREIGN KEY (job_id, contract_id) REFERENCES contracts(job_id, id)` |
| `attempts` | `UNIQUE(run_id, route, sequence)`; `route IN ('route_a','route_b')`; outcome has six values |
| `obligations` | `result IN ('passed','failed','not_run','unknown','timed_out')`; `passed` requires `evidence_artifact_id` |
| `model_calls` | `estimated_cost_usd IS NULL OR >= 0`; `usage_json IS NULL OR json_valid` |
| `events` | `sequence INTEGER PRIMARY KEY AUTOINCREMENT` |

Vocabulary notes:

- `unknown` / `timed_out` are kept separate, not flattened into `failed`;
- route-level `unsupported` is stored in `attempts.outcome`, not stuffed into obligations;
- a skipped check is recorded as `not_run` + detail, not as `passed`.

`attempts` is pre-created by the controller when the run starts (one row each for route_a/route_b, `sequence=1`,
`phase='queued'`, `outcome=NULL`); a retry is `sequence+1`. `/api/attempts/{id}/evidence`
therefore has an id from the first second.

---

## 5. Division of work

| Work | Write | review |
|---|---|---|
| `002_ai_tables.sql` | Member 5 | Member 1 (jobs/artifacts compatibility), Member 4 (obligations vocabulary) |
| `migrate.py`: baseline v1, legacy detection, artifacts pre-check | Member 5 | Member 1 |
| the `connection.init_db()` startup call | Member 1 | Member 5 |
| attempts creation/retry | Member 1 | Member 4 |

After 002 merges, Member 1 then changes `jobs.py` / `controller_api.py` / `connection.py`, and reports
the real pytest counts for identity / controller API / attempts.

---

## 6. SecurityContract v2: capacity and invalid paths become numeric fields

The plain-text `valid_domain` / `invalid_input_response` are only for humans; gate 3/5 and acceptance need
machine-readable values, so `SecurityContract` moves up to **schema_version=2** with new required fields:

```python
dest_capacity_bytes: int          # 50
max_valid_input_bytes: int        # 49
capacity_includes_terminator: bool# True (strcpy's NUL counts toward the 50)
invalid_exit_code: int            # 1
invalid_stdout: str               # "" (the empty string is a legal value, do not strip)
invalid_stderr: str               # "ERROR: input exceeds destination capacity\n"
```

Constraints:

- `dest_capacity_bytes >= 1`;
- when `capacity_includes_terminator=True`, `max_valid_input_bytes < dest_capacity_bytes`;
- when `False`, `max_valid_input_bytes <= dest_capacity_bytes`;
- `invalid_exit_code` is within `0..255`;
- `invalid_stdout` / `invalid_stderr` preserve the exact byte text (no strip, no newline folding), allow only
  printable ASCII + `\n`/`\t`, and permit the empty string.

fixture values:

```json
{"dest_capacity_bytes":50,
 "max_valid_input_bytes":49,
 "capacity_includes_terminator":true,
 "invalid_exit_code":1,
 "invalid_stdout":"",
 "invalid_stderr":"ERROR: input exceeds destination capacity\n"}
```

gate 3's guard reads `max_valid_input_bytes` directly (`len > 49` → invalid), it does not
regex-parse 50/49 out of the text. `valid_domain` still keeps a human-readable description, and the two must agree (checked at review).

`schema_version` goes from 1 to 2; `from_dict` stays strict, so an old body that lacks a field is rejected rather than
silently defaulted.

---

## 7. `runs.manifest_sha256`: a canonical index, not a rearrangement of test cases

The manifest files (`valid.json` / `invalid.json`) are frozen byte for byte as artifacts; `manifest_sha256`
is the hash of this small index:

```json
{"case_id":"CWE121_src_char_declare_cpy_51b",
 "manifests":[{"name":"invalid.json","sha256":"<file sha>"},
              {"name":"valid.json","sha256":"<file sha>"}],
 "original_sha256":"aa4281...",
 "schema_version":1}
```

canonical rules:

- top-level keys sorted; compact separator `(",", ":")`; UTF-8; `ensure_ascii=False`;
- `manifests` **sorted by name**; names must be unique, relative POSIX paths, containing no `..`;
- each `sha256` is the SHA-256 (lowercase hex) of that file's **original bytes**;
- the case order, indentation, and newlines inside a file all affect the file hash; reordering/formatting after freezing = a new manifest.

Single implementation (the controller calls it directly, do not assemble the JSON yourself):

```python
from app.domain.manifests import (
    ManifestEntry, manifest_entries_from_files,
    manifest_set_json, manifest_set_sha256,
)

entries = manifest_entries_from_files([valid_path, invalid_path], root=fixtures_dir)
manifest_json = manifest_set_json(case_id=..., original_sha256=..., entries=entries)
manifest_sha = manifest_set_sha256(case_id=..., original_sha256=..., entries=entries)
```

Where to store it:

- `runs.manifest_sha256` = the `manifest_sha` above;
- `manifest_json` is saved as an artifact (role `test_manifest`), or recomputed and verified by the controller;
- the two JSON files themselves are also saved as artifacts, with their paths/hashes in `artifacts`.

Approval binding:

```text
jobs.original_sha256
+ contracts.sha256
+ runs.manifest_sha256
```

When a run is created, all three are copied/verified together; `reviewed_scope_sha256` still equals `contracts.sha256`,
and the manifest is bound separately instead of being put into the contract body, which avoids a circular hash.

---

## 8. attempts retry semantics

| Concept | Meaning |
|---|---|
| run | one execution: a frozen `(job, contract, manifest)` + one `idempotency_key` |
| attempt | one attempt at one route inside a run; `sequence` starts at 1 and increments |

Rules:

1. **the same idempotency key is reused**: return the existing run (HTTP 200) and its attempts;
   create neither a new run nor a new attempt.
2. if the key is the same but `job_id` / `contract_id` / `manifest_sha256` differ from the stored run:
   **409 conflict**, no overwrite, no new creation.
3. **retrying one route**: go through the explicit retry endpoint, create a new attempt under the **same run**
   with `sequence+1`; the old attempt is kept.
4. **a new run** is created only in these cases:
   - a new idempotency key;
   - a new execution after the contract was re-reviewed (new `contracts.sha256`) or the manifest was re-frozen (new
     `runs.manifest_sha256`);
   - the operator explicitly "rerun"s (generating a new key).
5. a transport retry inside the provider does not create a new attempt; it is one
   `model_calls` record within the same attempt. Only regenerating after a candidate was rejected creates a new attempt.
6. after a run reaches a terminal state, no attempt may be appended; to run again you must use a new key (rule 4).

`attempts` is pre-created with two rows (route_a/route_b) when the run starts, `sequence=1`, `phase='queued'`,
`outcome=NULL`; the retry endpoint appends more. That way `/api/attempts/{id}/evidence` has an id
while generation is still in progress.


---

## 9. Acceptance Verdict persisted verbatim (003)

001's obligations/outcomes columns **cannot** carry the acceptance engine's four fields; 001 is retired and not used.
002 created outcome, but the reason was still called `reason_code`, and `failing_obligation`/`detail` were missing.
003 fills them in, so `Verdict` persists verbatim and the controller does not need a second mapping layer:

```sql
ALTER TABLE attempts RENAME COLUMN reason_code TO reason;
ALTER TABLE attempts ADD COLUMN failing_obligation TEXT;
ALTER TABLE attempts ADD COLUMN detail TEXT;

ALTER TABLE runs ADD COLUMN reason TEXT;
ALTER TABLE runs ADD COLUMN failing_obligation TEXT;
ALTER TABLE runs ADD COLUMN detail TEXT;
```

Mapping:

| `Verdict` | `runs` / `attempts` |
|---|---|
| `outcome` | `outcome` |
| `reason` | `reason` |
| `failing_obligation` | `failing_obligation` (stores the obligations.id or kind, verbatim) |
| `detail` | `detail` |

Individual check results are still stored in `obligations.result` (passed/failed/not_run/unknown/timed_out) +
`obligations.detail`. Do not split these four fields into a separate set of reason enums.

Migration versions: `(1,'base') → (2,'ai_tables') → (3,'acceptance_verdict')`; upgrades are applied
automatically by `app/db/migrate.py`, with no need to delete the database (001 is still rejected).
