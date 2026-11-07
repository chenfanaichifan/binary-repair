# Two review findings, reproduced — and whose file each one is

The 2026-11-06 review reported two defects in the T8.3 path. Both were reproduced
here against the actual code, because a finding accepted on trust is not evidence
of anything, and a finding repeated without a reproduction is just a rumour with a
citation.

Neither reproduction changes a gate. `V4` is still `not_run`, T8.3 is still
blocked, and nothing here writes a `verified_by`.

| file | what it is |
|---|---|
| `01-reproduce.py` | calls the planner twice through `generate_plan` and compares |
| `02-planner-output.txt` | its output: the two plans are identical |
| `03-expect-distinct-today.txt` | the same script in `--expect-distinct` mode; exits 1 today |
| `04-replay-contradiction.py` | asks whether the V4 adapter believes a claim its digests deny |
| `05-replay-contradiction.txt` | its output: the producer cannot lie, the adapter believes it anyway |

## Finding 1 — the planner cannot tell the two classes apart

The claim: called with a CWE-121/`argv` context and a CWE-416/`none` context, the
deterministic planner returns the same plan.

Confirmed, and the mechanism is one line of code:

```
app/domain/assistant.py:84
    def deterministic_plan(description: str, context: dict | None = None) -> AssistantPlan:
```

`context` appears exactly once in that module — in the signature. The body never
reads it. `app/services/assistant.py:163` dutifully passes a context (and builds one
from the job when only a `job_id` is given), and the domain function drops it on the
floor.

Stripping the random `plan_id`, the two plans are equal field for field, including
the `valid_tests` default `"valid: hello"` — a default that makes sense for a stdin
program and no sense for a binary that reads nothing at all.

What that costs: two saved plans from this planner would be one document with two
ids. Presenting them as the class contrast the task asks for would be presenting an
id as a difference. The fix is not mine — it is the planner's owner's — but the
reproduction, the regression gate and the statement of what "different in
substance" has to mean are here so that the fix can be checked rather than
believed.

`--expect-distinct` is the checkable half. It exits 1 today. The day the planner
learns the difference, this script starts passing and can move into the test suite
as a regression guard.

## Finding 2 — the V4 adapter trusts a claim its own data contradicts

The claim: feeding the converter two different replay digests together with
`identical: true` was accepted.

Confirmed — and the two halves of that path are not equally at fault, which matters
for who fixes it.

**The producer is sound.** In `v4_harness.py`, `Replay.identical` is a `@property`
computed from the digests:

```python
@property
def identical(self) -> bool:
    return len(self.digests) >= 2 and len(set(self.digests)) == 1
```

No setter, so no caller can assert identity; the value written into JSON is derived.
The harness also exits non-zero if the digests differ, which is how the very first
attempt failed back in record 127.

**The adapter is not.** `app/domain/v4.py:287-289`:

```python
identical = bool(
    replay.get("identical", runs >= 2 and len(set(digests)) == 1)
)
```

The default is only evaluated when the key is absent, so a present-but-wrong
`identical` wins over the digests it contradicts. Fed `["a"*64, "b"*64]` with
`identical: true`, `from_v4_harness` returns evidence reporting identity, and reuses
the first digest as `evidence_sha256`.

Scope, stated as narrowly as it deserves: this is not a gate bypass. The adapter
adds no `verified_by`, so a bundle built from such evidence still reads V4 `not_run`
(record 126), and the required-and-missing obligation still makes the attempt
`inconclusive`. What it is, is a converter that can carry a claim its own data
denies — which means a future replay marker could one day rest on a self-declared
field instead of on two matching digests. That is worth closing before it matters,
not after.

The fix is four lines in the file that owns it, written out in `05` so it can be
argued with rather than adopted blindly:

```python
derived = runs >= 2 and len(set(digests)) == 1
declared = replay.get("identical", derived)
if bool(declared) != derived:
    raise V4EvidenceError(f"replay.identical={declared} contradicts digests={digests}")
identical = derived
```

Rejecting a contradiction beats defaulting: after this, a producer that says `true`
is either redundant or wrong, and never believed.

## What M3 does next, and what M3 cannot do

The review's division of labour puts M3 with M4 on guest access and replay. Both
halves are outside M3's hands in a way worth naming precisely:

- the guest is reachable from this host and `m4verify` now holds M4's key
  (`../m4-key-install-2026-11-06/`), but `192.168.30.128` is a VMnet8 address that
  nothing outside this host can route to, and the forwarding rule needs an
  administrator prompt this environment does not have;
- the replay itself needs M4's private half and M4's own record. Running it here and
  labelling it a replay would be the one thing the role forbids.

So: if the guest path opens, M4 replays and V4 leaves `not_run` on their signature.
If it does not, V4 stays `not_run` and T8.3 stays blocked — and the honest move,
per the review, is to defer T8.3 explicitly rather than let a blocked gate quietly
become a forgotten one.
