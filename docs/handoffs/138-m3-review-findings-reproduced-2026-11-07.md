# 138 — two review findings reproduced, one debt closed, and what M3 still cannot do

- Date: 2026-11-07 (09:40–10:00 local)
- Owner: Member 3 (guest execution / evidence)
- Gate status assigned here: **none.** No `verified_by`, V4 still `not_run`, T8.3
  still blocked.

## 1. Transport recovered; the two branches are on the remote

Yesterday's repeated 502 was the proxy's `github.com:443` upstream, not this host
(record 136 §10). It cleared overnight, and both outstanding pushes landed on the
first attempt:

```
52ffecd..79cd4f9  m3/cwe122-fixture-build -> m3/cwe122-fixture-build
3e2c108..71ae90e  m3/cwe416-v3-noinput     -> m3/cwe416-v3-noinput
```

`79cd4f9` is the rebased CWE122 build fix; `71ae90e` carries the key install and
the reachability evidence. The CWE122 branch is now level with its remote, which it
had not been since the rebase — the earlier non-fast-forward is gone rather than
hidden.

## 2. The key debt is closed, not just disclosed

Record 136 §6 said the installed M4 key matched the text and the two digests in the
request, and explicitly did **not** claim it matched the branch, because five
fetches had failed. That was the weaker claim, and it was labelled as such.

This window the branch could be read:

```
$ git fetch origin delivery/t83-2026-11-06          -> new branch
$ git cat-file -t f46c626c…   commit
$ git cat-file -t df99853b…   commit
$ git show origin/delivery/t83-2026-11-06:m4_guest_key.pub | sha256sum
  ab8fbd7dc23bf900dc1597da8025a689feed55f77275c87869e55fa4dca5a703
$ cmp <branch copy> <installed copy>                byte-identical
```

So the stronger statement holds: the key on `m4verify` is what the branch holds.
Nothing needs replacing. Evidence: `evidence/m4-key-install-2026-11-06/04-verified-against-the-branch.txt`;
`02` keeps the five failed fetches so the order stays visible — text first,
verification second.

## 3. The review's two findings, reproduced against the code

Both are in `evidence/t83-review-findings-2026-11-07/`, with the scripts that
produce the output rather than a summary of it.

### 3.1 The planner returns one plan for both classes

Claim confirmed. `app/domain/assistant.py:84` accepts a `context` argument and never
reads it — `context` appears once in that module, in the signature.
`app/services/assistant.py:163` passes a real context in, and it is dropped.

Removing the random `plan_id`, the CWE-121/`argv` plan and the CWE-416/`none` plan
are equal field for field, down to `valid_tests` defaulting to `"valid: hello"`,
which is a stdin-program default offered to a binary that reads nothing.

`01-reproduce.py --expect-distinct` exits 1 today. That is deliberate: the script is
the regression gate for whoever fixes the planner, and the day it passes is the day
the class contrast exists. What "different in substance" must mean is written into
its output, so the fix can be checked rather than believed.

This is M5's file, not M3's. What M3 can contribute is the reproduction, the gate,
and the statement of the target.

### 3.2 The V4 adapter believes a replay claim its digests deny

Claim confirmed, and the fault is asymmetric in a way that matters for who fixes it.

**The producer is sound.** `Replay.identical` in `v4_harness.py` is a read-only
`@property` computed from the digests, and the harness exits non-zero when they
differ — which is how the first attempt failed in record 127. It is structurally
incapable of emitting `identical: true` with two different digests.

**The adapter is not.** `app/domain/v4.py:287-289` reads `replay["identical"]` when
present and only derives the value when the key is absent, so a wrong claim beats
the digests it contradicts. Fed `["a"*64, "b"*64]` with `identical: true`,
`from_v4_harness` returns evidence reporting identity.

Narrow scope, stated in the evidence too: this is not a gate bypass. The adapter
writes no `verified_by`, so a bundle built from such evidence still reads V4
`not_run` and still lands `inconclusive` on the missing required obligation
(record 126). What it is, is a converter able to carry a claim its own data denies —
the kind of thing that should be closed before a replay marker depends on it.

The four-line fix (derive, compare, reject on contradiction) is written out in `05`
as a proposal, in the file that owns it. M3 did not patch `app/domain/v4.py`.

## 4. On the scope decision the review raises

Checked rather than assumed: the fixture contract authorises the repair that was
applied. `authorized_edits[0]` reads

> Move the read of the block before free(), or drop the free() and accept the leak;
> no other behaviour may change.

The shipped candidate takes the second branch — five `nop` over `call free@plt` — so
the leak is inside the contract, and the pointer-flow property holds because nothing
is freed on that path. That supports a fixture-scoped result, which is what the
evidence claims.

The follow-up the review suggests (move cleanup after the final use, then check that
the block is released as well as never read after release) is a **different
contract**, not a better candidate for this one. Changing it now would re-open the
frozen sample that records 121, 133 and 4 independently reviewed packages vouch for.
It belongs in a new sample with its own contract and its own acceptance run.

## 5. What M3 does not do, and the deferral condition

- The replay needs M4: their private half, their guest session, their record. Running
  it here and calling it a replay is the one thing this role forbids.
- The guest path needs a port-forwarding rule that requires an administrator prompt
  this environment does not have (`evidence/m4-key-install-2026-11-06/03-network-path.txt`).
  The key is installed; the route is not open from outside this host.
- V2/V4 ingestion belongs to M1, who has already re-scored V2 at 5/5 through the
  controller path (record 129). Record 137's proposal stands as a proposal; the
  review is right that implementing V2 a second time from an older status would be
  wasted work.

**Deferral condition, written down so it is not a mood:** if the guest route is still
closed at the next window, T8.3 is recorded as deferred — not "in progress", not
"nearly done" — and M3's next contribution is to keep the evidence coherent rather
than to accumulate more of it. A blocked gate that nobody names has a way of
becoming a forgotten one.

## 6. What this record does not do

It does not accept the review's integrity checks as M3's own — they were run
externally (39 V4 schema/adapter tests, 12/12 replay package, 29/29 T8.3 evidence,
381/381 delivery manifest) and are cited, not re-performed. It does not close
anything, does not move a gate, and does not add a sample.
