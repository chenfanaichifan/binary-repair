# Direct ELF AI review experiment — 2026-11-12

## Question

Does a read-only model review add anything to the deterministic verification of
a direct ELF repair, without changing the acceptance decision?

This is an **experiment record**, not a new acceptance authority and not broad
ELF coverage.

## Baseline

Code commit (feature + experiment script):

```text
df82b6c40d78b5eb643a16e0123e10a76b44475a
docs(evidence): record direct-ELF AI review experiment
```

The feature itself landed in `be9564f`; `df82b6c` adds the reproducible
experiment script and the first evidence record. Ubuntu 24.04 non-browser
verification of `df82b6c`:

```text
run:      https://github.com/chenfanaichifan/binary-repair/actions/runs/43248205593
job:      https://github.com/chenfanaichifan/binary-repair/actions/runs/43248205593/job/131286534110
head:     df82b6c40d78b5eb643a16e0123e10a76b44475a
result:   completed / success
command:  python -m pytest -q --ignore=tests/e2e
```

The workflow ran the targeted fixture-staging regression first and the full
non-browser suite with `if: always()`. The macOS host still shows the known
`readelf` Route B view-count failure; Ubuntu is the canonical baseline.

Local suite before the AI experiment:

```text
1 failed, 878 passed, 4 skipped
```

The only failure is `tests/test_routeb_executor.py::test_static_routeb_bundle`
on macOS because GNU `readelf` is absent; Ubuntu installs `binutils` and the
same test passes there.

## Cases

| case | input | gate | why |
|---|---|---|---|
| `strict_ok` | `artifacts/vuln-elf/vuln.elf` | `success_within_scope` | reviewed strict template, four Unicorn boundary cases |
| `unsupported` | `fixtures/pe/cli-64.exe` | `unsupported` | PE, outside the direct ELF profile; no candidate |
| `missing_evidence` | `vuln.elf` with runtime summary temporarily unavailable | `inconclusive` | candidate bytes exist, required runtime evidence does not |

The missing-evidence case is a controlled simulation: the demo/test temporarily
replaces `binary_repair_engine._runtime_summary` with an unavailable result and
restores it afterwards. The artifact labels this as `evidence_gap: true`.

## Method

For every case:

1. Run the deterministic baseline with no review.
2. Run the same case with the configured reviewer (`--provider real`).
3. Run a **scripted `accept`** control to prove a failed gate cannot be promoted.
4. For the passing case, run a **scripted `hold`** control to prove a review can
   veto a success.

The model receives
[`verification.packet`](../../app/services/binary_verification.py), the same
packet the UI renders: scope, candidate hashes, patch scope, runtime cases,
checks, missing checks and limitations. It does not receive binary bytes,
source, file paths or provider credentials.

The model returns only `recommendation`, `summary`, `concerns`,
`missing_evidence` and `further_checks`. The deterministic gate remains the
authority.

## Result

Artifact:
[`artifacts/binary-ai-review-2026-11-12/`](../../artifacts/binary-ai-review-2026-11-12/README.md).

Provider:

```text
requested model: deepseek-chat
returned model:  deepseek-flash
calls:           3 (one per case)
tokens:          4,432 prompt / 716 completion / 5,148 total
latency:         ~2.0–2.3 s per call
```

| case | gate | no AI | with AI | AI called | recommendation | changed |
|---|---|---|---|---|---|---|
| `strict_ok` | `success_within_scope` | success | success | yes | `accept` | no |
| `unsupported` | `unsupported` | unsupported | unsupported | yes | `hold` | no |
| `missing_evidence` | `inconclusive` | inconclusive | inconclusive | yes | `hold` | no |

Scripted controls:

```text
strict_ok + scripted hold    -> rejected (scripted_veto)
unsupported + scripted accept -> unsupported (review_accept_cannot_promote_gate)
missing_evidence + scripted accept -> inconclusive (review_accept_cannot_promote_gate)
```

## What the AI added in this run

### `strict_ok` — accept, no decision change

The model agreed that all 10 required checks passed. It added three concrete
follow-up checks, all already implied by the report's limitations:

- Unicorn emulation is not a host-kernel run; a native run would strengthen
  confidence.
- Coverage is four input sizes around capacity 16; partial reads, larger inputs
  and other architectures are untested.
- No independent guest replay of the reviewed template hash.

### `unsupported` — hold, no decision change

The model restated the gate's failed/missing checks (format, candidate presence,
patched identity, patch scope, runtime evidence) and recommended re-running on a
supported ELF. It added no new check category.

### `missing_evidence` — hold, no decision change

The model restated the four missing runtime checks and recommended re-running
with emulation, host-kernel confirmation, partial reads and wider input
coverage. It added no new check category.

## Honest conclusion

In this single run, **the model did not catch a new verification gap that the
deterministic report did not already expose**. It agreed with the passing gate,
held the two non-successful cases, and rephrased known limitations as concrete
follow-up checks. It changed no decision.

What the experiment does demonstrate:

- the model was actually called, with model identity and token usage recorded;
- it received the same structured packet a human sees, not the binary;
- a model `accept` could not promote the unsupported or missing-evidence cases;
- a model `hold` could veto the passing case (shown by the scripted control);
- the final decision remained the deterministic gate's.

The `new_*` counts in `run.json` are a wording heuristic; read the lists in the
artifact, not only the counts.

## Reproduction

```bash
# full non-browser suite (Ubuntu is canonical)
python -m pytest -q --ignore=tests/e2e

# scripted contract control (no provider call)
python scripts/demo_binary_ai_review.py --provider scripted \
  --out /tmp/binary-ai-review-scripted

# real review (requires BINARYREPAIR_ASSISTANT_PROVIDER_KEY)
python scripts/demo_binary_ai_review.py --provider real \
  --out artifacts/binary-ai-review-2026-11-12 --force
```

## Limitations

- One checked-in fixture family; not broad ELF coverage.
- Runtime evidence is Unicorn emulation with modeled syscalls, not a host-kernel
  run or an isolated guest.
- One model run per case; model output is non-deterministic.
- The missing-evidence case is deliberate and simulated; it is not evidence that
  a real deployment lost runtime evidence.
- The model's follow-up checks overlap with the report's limitations; no
  measured precision/recall claim is made.
