# T8.3 supplement — the two questions a verifier asks first

Companion to `T8.3-evidence-2026-11-06/`, which is sealed and stays sealed. This
directory adds reading, not new measurements: it does not change the candidate,
the fixture, the contract, or any gate result.

Two files answer the two questions M4 is most likely to open with.

| file | the question it answers |
|---|---|
| `hooks-audit.md` | "are the five hooks so approximate that they assumed the answer?" |
| `property-mapping.md` | "is the query the harness asks the same thing as the contract's `forbidden_behavior`?" |
| `check_mapping.py` | the mechanical half of both: nine field-level assertions, exit 0/1 |

## Why these two

A symbolic result is only as good as its two weakest links: what the model
replaced with stubs, and whether the property it proved is the property the
contract forbids. Neither is visible from `v4-symbolic.json` — that file reports
`calibration 1/1` either way — so both need to be argued in prose and pinned by a
check that fails when fields drift apart.

The audit's honesty list includes two places where the harness's own documentation
is out of date:

- the module docstring still says output is written through `write_v4_evidence`,
  which stopped being true in record 128;
- `HOOKS[3].why` says the state is terminated after observing `printLine`, which
  the code does not do.

Neither is patched. The harness bytes are what records 128, 129 and 133 vouch for,
and a comment edit would invalidate three delivered records to fix a sentence. The
audit says which part to trust; the code is the authority.

## Run it

```sh
python3 check_mapping.py                          # defaults to ../T8.3-evidence-2026-11-06
python3 check_mapping.py --bundle /path/to/T8.3-evidence-2026-11-06
```

Nine checks, all passing on the delivered bundle:

```
target_entry matches · input_mode none on both sides · property is pointer-flow
hooks == allowed_calls · known_good holds with unsat · known_bad violated with sat
scope model + empty disjunction disclosed · forbidden_behavior names free() and stdout
required_obligations are the six gates
```

It refuses to pass if the harness starts asking about a different function, if a
hook appears that the contract does not allow, if the calibration stops
distinguishing the two binaries, or if the model-scope disclosure disappears.

## What this supplement does not do

- It does not score V4. `gate-index.json` in the evidence bundle still reads
  `not_run`, and no `verified_by` value exists here either.
- It does not close T8.3. One sample, one mechanism; M4 replays and the Lead
  decides.
- It does not re-measure anything. If a number here disagrees with the bundle,
  the bundle is right and this file is wrong — `check_mapping.py` reads the
  bundle's files, so it will fail loudly rather than disagree quietly.
