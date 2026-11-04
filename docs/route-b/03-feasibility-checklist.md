# Route B real-sample feasibility checklist

**Status:** waiting for Member 3 to freeze the public sample (`route-a/docs/05-sample-analysis.md` is currently all TBD).
**Purpose:** once the sample arrives, reach a **PASS / FAIL / UNSUPPORTED** verdict across G0–G9 within 1–2 hours,
instead of going by "it feels like it runs".

> Right now all we can do is rehearse: run the flow itself against `routeb/fixture/vuln` (currently 6/6).
> For the real sample, the round trip is recorded as `not_run` until G0 passes; it must not be written up as "verified".

---

## 0. Inputs required from Member 3

If any item is missing, record the corresponding gate as `not_run`; do not fill it in with a guessed value.

| # | Input | Where to get it | Consequence if missing |
|---|---|---|---|
| 1 | ELF path + SHA-256 | `route-a/docs/05-sample-analysis.md` | Cannot bind identity; every gate is blocked |
| 2 | Build command, compiler/version, date, builder | same as above | Cannot tell where the "recompile difference" comes from |
| 3 | Vulnerable function name, entry address, function byte size | Ghidra / `nm` | Cannot export and replace |
| 4 | Valid/invalid input domains, expected return value/output | contract (reviewed by Member 4) | Cannot judge whether the round trip preserves behavior |
| 5 | Known trigger input (length/content) | reproduction record | Cannot prove the defect still reproduces (G5) |
| 6 | Binary-level observable effect (crash/overwrite/exit code) | reproduction record | Cannot establish a baseline |
| 7 | Allowed edit scope and forbidden items | contract | Cannot judge whether a candidate goes out of scope |
| 8 | Who reviewed the above | review record | The conclusion cannot be used for acceptance |

---

## 1. G0 — identity and provenance (do this first)

```bash
SAMPLE=fixtures/public/<sample>
FUNC=<vulnerable_function>
sha256sum "$SAMPLE"
file "$SAMPLE"
readelf -h "$SAMPLE" | sed -n '1,20p'
```

- [ ] hash matches what Member 3 recorded exactly (write it into the experiment log)
- [ ] `ELF 64-bit LSB executable, x86-64`, `ET_EXEC` (non-PIE), not stripped or symbols available
- [ ] the function name can be found in the symbol table: `nm "$SAMPLE" | grep " $FUNC$"`
- [ ] the sample is outside the client data scope (public/synthetic) and may be sent externally

Failure: `UNSUPPORTED` (profile mismatch) or `ERROR` (identity does not match, stop).

## 2. G1 — supported profile

- [ ] single process, single thread
- [ ] no packed / self-modifying code
- [ ] the repair region does not depend on TLS, C++ exceptions, or special unwinding
- [ ] no unresolved indirect jump enters the bytes that will be overwritten
- [ ] no new external library dependencies

If any item fails: `UNSUPPORTED`, and state which one.

## 3. G2 — Ghidra export

```bash
./routeb/ghidra/export.sh "$SAMPLE" "$FUNC"
cat routeb/out/$FUNC.c.meta.txt
```

- [ ] function found, `size_bytes` reasonable (tens to a few hundred bytes)
- [ ] record `callees=`: empty = simple relocation; libc calls present = PLT resolution needed, risk goes up
- [ ] raw output saved unmodified
- [ ] record Ghidra version, JDK version

Failure: `UNSUPPORTED` (function too large/indirect calls/no symbols); keep the logs.

## 4. G3 — normalization

Create `routeb/out/$FUNC.normalized.c`, changing only types and names:

- [ ] every edit has a one-line reason (diff list)
- [ ] control flow, array indices, and check logic **unchanged**
- [ ] compiles standalone: `cc -O0 -g0 -fno-stack-protector -fno-builtin -c routeb/out/$FUNC.normalized.c -o /tmp/$FUNC.o`
- [ ] signature matches the binary (argument count/width/return type)

Failure: go back to G2 or `UNSUPPORTED` (for example `code *` or struct return appears).

## 5. G4 — unchanged round trip (core gate)

```bash
python routeb/probe_patcherex2.py \
  --binary "$SAMPLE" --func "$FUNC" \
  --mode roundtrip \
  --c-source "routeb/out/$FUNC.normalized.c" \
  --out "routeb/out/${FUNC}_roundtrip" \
  --skip-verify
```

> A real sample cannot use `routeb/verify.py`: that is the oracle written for this repository's synthetic fixture.
> After backfilling, validate with the team's frozen test checklist (Members 4/1), and record the command in the experiment log.

- [ ] the backfilled ELF starts
- [ ] all team valid-input cases pass, output/return values identical to the original
- [ ] the known trigger input still triggers (the defect was not "fixed by the way")
- [ ] `readelf -lW` shows no unexpected change in segment count/permissions; record any added segment
- [ ] the changed byte range is explainable (function body ± relocations)
- [ ] Patcherex2 version, compiler version, command recorded

Failure handling: see §10.

## 6. G5 — defect still reproducible

- [ ] with the trigger input from Member 3, the round-trip binary shows the same observable effect as the original
- [ ] if the defect disappears: that is **not a successful repair**, it is a behavior change; record round-trip FAIL

## 7. G6 — layout and compatibility audit

```bash
readelf -lW "$SAMPLE" > /tmp/before.segments
readelf -lW "routeb/out/${FUNC}_roundtrip" > /tmp/after.segments
diff -u /tmp/before.segments /tmp/after.segments
```

- [ ] entry address, load segments, permissions conform to the contract
- [ ] no overlapping writes, no unresolved relocations
- [ ] does not silently disable NX/RELRO/stack protection
- [ ] record the two numbers, changed / added bytes

## 8. G7 — model candidate (DeepSeek)

Prerequisite: G4/G5 pass.

```bash
# CONTRACT = the contract text file reviewed by Member 4 (not a PRD excerpt)
CONTRACT=docs/route-b/contracts/<sample>.txt

python scripts/demo_candidate.py \
  --binary "$SAMPLE" \
  --function "$FUNC" \
  --recovered "routeb/out/$FUNC.normalized.c" \
  --signature "<signature copied from the meta file>" \
  --contract "$CONTRACT" \
  --allowed-calls "<comma-separated, leave empty if none>" \
  --out-c "routeb/out/$FUNC.model.c"
```

`--allowed-calls` is the intersection of G2's `callees=` and the contract; empty means only pure functions are allowed.

- [ ] candidate passes schema + scope validation (`accepted_for_validation`)
- [ ] only the allowed scope was changed; `expected_effects` match the contract
- [ ] no added calls/headers/attributes
- [ ] record prompt hash, model, tokens, cost

Failure: `REJECTED` (format/out of scope) or `ERROR` (provider); keep the diagnostics.

## 9. G8 — repair-candidate validation

```bash
python routeb/probe_patcherex2.py \
  --binary "$SAMPLE" --func "$FUNC" \
  --mode fixed \
  --c-source "routeb/out/$FUNC.model.c" \
  --out "routeb/out/${FUNC}_fixed" \
  --skip-verify
# then run the team test checklist against the final ELF
```

- [ ] on the repaired ELF, the trigger input no longer goes out of bounds/crashes
- [ ] invalid input follows the error path specified by the contract
- [ ] valid input passes 100%
- [ ] the bounded symbolic check (Member 4) completed on the final ELF, and is not unknown/timeout
- [ ] the changed region matches the G6 audit

## 10. G9 — evidence and reproduction

- [ ] original/candidate hash, contract hash, test-checklist hash
- [ ] the three C files raw / normalized / model, plus their diffs
- [ ] tool versions, commands, environment
- [ ] failed/not-run items explicitly marked, not filled in with "should"
- [ ] another member can re-run it following the record

---

## 11. Failure handling matrix

| Symptom | Conclusion | Action |
|---|---|---|
| hash/profile mismatch | `UNSUPPORTED` | stop; go back to Member 3 for another sample or more information |
| Ghidra export fails/function too large | `UNSUPPORTED` | record the reason, do not force edits |
| normalization does not compile | `UNSUPPORTED` / `ERROR` | keep the diff, assess whether to switch functions |
| does not start after backfill | `ERROR` | check relocations/segment permissions; do not continue before locating it |
| valid-input behavior changes | `REJECTED` (round trip) | go back to G3 and diff line by line |
| trigger input no longer goes out of bounds | `REJECTED` (behavior change) | not a repair; investigate compiler differences |
| model candidate format/out of scope | `REJECTED` | keep the candidate and reason_code |
| provider timeout/quota/empty | `ERROR` | record as a typed failure, do not fabricate a candidate |
| symbolic check unknown/timeout | `INCONCLUSIVE` | must not be displayed as success |

---

## 12. Time box (after the sample arrives)

| Stage | Limit | Action on timeout |
|---|---|---|
| G0–G2 | 30 min | record the blocker, ask Member 3 first |
| G3 | 30 min | still not compiling after 2 hours → `UNSUPPORTED` |
| G4–G6 | 45 min | record the failure, do not grind on it the same day |
| G7–G8 | 45 min | run the candidate only once, no unbounded retries |

---

## 13. Record template

```markdown
### Route B feasibility — <sample> — <date>

- sample sha256:
- func / entry / size:
- build: <cmd>, compiler <version>
- Ghidra/JDK:
- callees:
- normalization edits:
- Patcherex2 version:
- G4 round trip: PASS / FAIL / UNSUPPORTED
- G5 defect still observable: yes / no
- G6 segments changed: yes / no (details)
- G7 candidate: accepted / rejected:<reason>
- G8 fixed: pass / fail:<case>
- evidence paths:
- blockers:
```
