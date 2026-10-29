# INTERFACE v1 — M3 ↔ M5 handoff

**Status:** frozen 2026-10-29. Version bumps require a changelog line + notify
M3/M4/Lead in the same commit.

## 1. Attempt bundle (worker input)

Path:

```text
<data>/jobs/<job>/runs/<run>/attempts/<attempt>.json
```

Schema:

```json
{
  "route": "route_a | route_b",
  "candidate_sha256": "<64 lowercase hex>",
  "results": {"V0": "passed|failed|unknown|timed_out|not_run", "V1": "..."},
  "evidence": {"V0": "<artifact id>", "V1": "..."},
  "details": {"V0": "why"}
}
```

Rules:

- `V0..V5` always present; absent means `not_run`, never `passed`.
- A `passed` gate must have an artifact id in `evidence` that exists in
  `artifacts` for that job/attempt.
- The UI never computes an outcome; it reads the acceptance engine verdict.
- Route A adapter registers evidence files and writes artifact ids.
- Route B adapter uses `routeb/attempt_writer.py`; static bundles keep
  V2/V4/V5 `not_run` and can only produce `inconclusive`.

## 2. Evidence package (M3 → M5)

Directory:

```text
<package>/
  handoff.json
  SHA256SUMS
  <raw files...>
```

`handoff.json`:

```json
{
  "id": "P4",
  "from": "M3",
  "to": "M5",
  "route": "gate4 | route_a | route_b",
  "created_at": "2026-10-29T12:00:00+08:00",
  "files": ["gate4-status.json", "case-01.json"],
  "notes": "human-readable status only"
}
```

Rules:

- `id`, `from`, `to`, `route`, `created_at`, `files` required.
- `files` are relative paths, no `./`, no absolute paths, no `..`.
- `SHA256SUMS` is standard `sha256sum` format:
  `<64 lowercase hex>  <relative path>`, one per file, sorted by path
  (`LC_ALL=C`), `SHA256SUMS` itself excluded.
- `evidence-manifest-sha256` = SHA-256 of the `SHA256SUMS` file bytes.
- `SHA256SUMS` must list every file except itself and `handoff.json` is **not**
  implicitly trusted; include it explicitly if it is part of the evidence set.
- Missing file, extra unhashed file, wrong hash, unsorted lines, `./` prefix,
  uppercase hash or filename-first format = FAIL.

## 3. Naming / hashes

- Package id: `P4`, `P3A`, `P3B` for M3 packages; no spaces.
- Candidate/contract hashes lowercase hex, exactly 64 chars.
- Never merge two evidence sets. v1/support/v2/v3 are separate historical sets.
- Never rename or re-hash a delivered file; a corrected package gets a new id/hash.

## 4. Provisional handoff converter

A package with `package_id` instead of `id`, no `files`, or unsorted
`SHA256SUMS` is not accepted directly. Convert mechanically:

```bash
python scripts/normalize_handoff.py <provisional-package> --out <new-package>
```

The converter:

- requires `from`, `to`, `route`, `created_at`, and `id` or `package_id`;
- refuses missing/declared-but-absent files;
- sets `schema_version=1`, `id`, and `files` over the actual payload;
- regenerates `SHA256SUMS` sorted by path;
- runs `check_handoff.py`; success requires checker PASS.

It does **not** relax the checker or add evidence bytes. Missing evidence still
fails the checker/adapter.

## 5. Adapters

```bash
# checker first
python scripts/check_handoff.py <package> --expect-from M3 --expect-to M5

# Route A: M3 gates.V0..V5 -> worker attempt JSON; registers evidence artifacts
python tools/routea_bundle_to_attempt.py \
  <result-bundle.json> \
  --data-dir var --job-id <job> --attempt-id <attempt> \
  --out var/jobs/<job>/runs/<run>/attempts/<attempt>.json

# Route B static bundle -> worker attempt JSON
python -m routeb.attempt_writer \
  --bundle <routeb-bundle> --data-dir var --job <job> --run <run> --attempt <attempt>
```

## 6. Versioning

Any schema/naming/hash-rule change = `INTERFACE-v2` plus a one-line changelog
entry in this file and a notification to M3/M4/Lead. Adapters must reject
unknown schema versions rather than silently coerce.

## 7. Self-test

```bash
python scripts/check_handoff.py --self-test
```

must print `PASS: self-test` and exit 0.
