# M4 — V4 replay status lock (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** status lock only. No new symbolic run, no gate promotion, no merge,
no tag.

---

## 0. Status

| Item | Status |
|---|---|
| Adapter replay | **PASS** — regenerated `v4-symbolic.json` is identical to the shipped file |
| Symbolic replay (`v4_harness.py`) | **NOT RUN** — environment unreachable |
| V4 | **`not_run`** — stays so until the independent symbolic replay completes |
| 124 (current-code ingest view) | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED (rebuild evidence package)** — independent of T8.3 |
| T8.3 | **BLOCKED** |

The distinction is the whole record:

```text
adapter replay : PASS   (angr-free; conversion is reproducible)
symbolic replay: NOT RUN (no angr; guest unreachable)
```

---

## 1. What was recorded

**Adapter replay — PASS**

```text
$ python tools/v4_harness_to_evidence.py \
    --input harness-output.json --output /tmp/v4-replayed.json
exit=0
$ diff <(json.tool /tmp/v4-replayed.json) <(json.tool v4-symbolic.json)
IDENTICAL
```

`validate_v4_evidence(v4-symbolic.json)` → OK. The product file is exactly what
the committed adapter produces from the measurement.

**Symbolic replay — NOT RUN**

```text
python3 -c 'import angr'                    -> ModuleNotFoundError
role5-kit/.venv/bin/python -c 'import angr' -> ModuleNotFoundError
~/anaconda3/pkgs / pip cache               -> no angr
docker / vmrun                             -> not available
ping 192.168.30.128                        -> 100% packet loss
ssh lab@192.168.30.128                     -> connect timeout
```

The recorded `harness-output.json` says candidate → `unsat`, original → `sat`,
two digests `cb2137a2…` identical. That is the **producer's** measurement; M4 did
not execute angr, so it is not an independent replay.

---

## 2. What unblocks the symbolic replay

Any one of the **A/B/C** environments (as named by the Lead) must provide:

| Requirement | Value |
|---|---|
| angr | `10.0.4.post1` |
| z3 | `5.1.0` |
| Python | `3.12.x` (the guest recorded `3.12.3`) |
| inputs | candidate `46d16e99…fcd0`, original `c9c2632e…23c9`, contract file `8a2b408c…e3c3b` |
| command | `python v4_harness.py --candidate … --original … --contract … --out … --replay-runs 2` |

M4 will then independently compare:

1. candidate → **unsat** (the empty-disjunction case, `free_calls=0`);
2. original → **sat** (the same symbolic pointer reaches `free()` and `printLine()`);
3. the two replay digests are identical;
4. the resulting `v4-symbolic.json` still validates with `property_kind=pointer-flow`,
   `calibration 1/1`, `known_bad_rejected=True`, exploration/solver complete,
   `claimed_scope=model`, and the empty-disjunction disclosure.

Only after that may V4 leave `not_run`. No environment is available today.

---

## 3. 124

Operative current-code view (V2 scored 5/5, V4 not_run):

```text
V0 passed, V1 passed, V2 passed, V3 passed, V4 not_run, V5 passed
outcome = inconclusive
reason  = required_check_not_run
failing = symbolic
```

The **shipped 124 bundle** still carries its old `gate-index.json` with V2/V4
`not_run`; read as-is it would fail `interface` first. Re-ingesting with the
current code gives the `symbolic` view above. In both cases V4 stays `not_run`
because the symbolic replay is missing.

---

## 4. Record 118 and T8.3

`118 = VERIFIED (rebuild evidence package)` remains independent: it does not
promote V0–V5, does not produce a candidate, and does not relieve T8.3.
T8.3 stays **BLOCKED**.

---

## 5. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 6. Evidence

| File | Content |
|---|---|
| `M4-v4-replay-124-final-evidence-2026-11-06.txt` | angr/guest checks, adapter replay diff, product validation, harness output, 124 gate index and test |
| `v4-symbolic.json` | the product claim under review |
| `harness-output.json` | the producer measurement re-adaptered |
| `_m4-verify/c41de41/` | the product schema/adapter used |
