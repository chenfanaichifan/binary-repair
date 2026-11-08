# 197 — M5 clarification: kind/verdict and null outputs

Date: 2026-11-08

## Canonical v1.1.2 rule

```text
kind = known_good | known_bad | valid | invalid
kind = unknown -> invalid whole artifact (no guessing)

verdict = same | different | not_run
verdict = unknown -> invalid whole artifact (no guessing)
```

`not_run` still requires both `original` and `candidate` objects. Their runtime
fields may be null:

```text
returncode       int | null
stdout_sha256    64 hex | null
stderr_sha256    64 hex | null
timed_out        bool (required, never null)
detail           string (required; null is invalid)
```

`same`/`different` require both sides' `returncode`, stdout and stderr hashes to be
non-null.

## Endpoint behavior

```text
not_provided -> 200
available    -> 200
invalid      -> 200
job missing  -> 404
no session   -> 401
```

## Tests

```text
tests/test_gui_comparison_route.py
  valid
  hash mismatch
  bad JSON
  not_run with null runtime fields
  kind=unknown -> invalid
  verdict=unknown -> invalid
```

v1.1.1 unchanged; target v1.1.2.
