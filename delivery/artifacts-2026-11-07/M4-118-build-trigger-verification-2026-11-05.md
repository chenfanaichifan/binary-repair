# M4 — record 118 build/trigger verification (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** build/trigger identity only. No guest access, no host execution, no
contract/V0–V5 verification, no repair verdict.

---

## 0. Lead ruling (2026-11-05 22:07) — binding on this record

1. **118 stays `REPORTED, NOT VERIFIED`** until the evidence directory is
   readable in this workspace.
2. **Upgrade gate = five items**, in this order: dual manifests (`06-SHA256SUMS`
   + `SHA256SUMS`), `02-build.txt`, `04-trigger.txt`,
   `01-window-and-isolation.txt`, `07-rebuild.json`.
3. **`c9c2632e…23c9` is the target hash, not this rebuild's output.** It becomes
   output evidence only when `02-build.txt` (or a shipped rebuilt binary with its
   own measured hash) shows *this run* produced it.
4. **Two decisions must stay separate:** the 116 synthetic **Fix A/B** is a
   build-shape choice; the **T8.3 no-input contract** is a contract-model choice.
   A/B is not the gate for V0–V5. See
   `M4-decision-separation-116-t83-2026-11-05.md`.
5. Record 91 unchanged; same operator; review items 9–12 separate; no merge, no
   tag, no live success.

**Standing order (restated 2026-11-05 22:09).** The status stays locked until
**all five** gates pass. Gates **2–4 are the substantive ones**: a manifest-only
delivery — even with every hash correct — cannot close them, because hashes
prove integrity, not that a build ran, that a trigger ran 251 times, or that a
window was baseline-clean. The target-hash rule and the A/B-vs-no-input
separation are **invariants** of this record, not per-round choices.

---

## 1. Requested checks — result

| # | Requested check | M4 result |
|---|---|---|
| 1 | `original.elf` = `c9c2632e…23c9` | **TARGET HASH CONFIRMED; THIS RUN'S OUTPUT NOT VERIFIED** |
| 2 | 251 deterministic runs | **NOT VERIFIED** |
| 3 | baseline-clean window | **NOT VERIFIED** |

Reason for all three: **record 118's evidence directory is not present in this
workspace.** Only its `README.md` and the record's prose are here.

---

## 2. What was available

| Artifact | Present? | What it can support |
|---|---|---|
| `118-m3-t30-baseline-rebuild-2026-11-05.md` | yes | a *report* of the rebuild |
| `README.md` (rebuild dir README, at workspace root) | yes | a *description* of the evidence directory |
| `M3-T30-CWE416-fixture.zip` (first build, uid 14) | yes | the committed `original.elf` and its 50-run trigger |
| `01-window-and-isolation.txt` | **no** | baseline-clean proof |
| `02-build.txt` | **no** | `sh build.sh` exit status and output hash |
| `03-readelf.txt` | **no** | machine-check re-derivation |
| `04-trigger.txt` | **no** | the 251-run claim |
| `05-asan.txt` | **no** | ASan diagnostic |
| `06-SHA256SUMS` | **no** | guest transport digests |
| `07-rebuild.json` | **no** | 12/13 field comparison |
| `collect.sh` | **no** | reproducibility of the collection |
| `SHA256SUMS` | **no** | integrity root for the directory |

A README that names ten files is not ten files. M4 cannot hash a description.

---

## 3. Check 1 — `original.elf` = `c9c2632e…23c9`

**What is verified.** The committed T30 binary — the **target** of the rebuild —
hashes exactly:

```text
c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9  T30/original.elf
```

**What is not verified.** That the record-118 run *produced* those bytes. The
rebuild output is not shipped, and `02-build.txt` (the transcript that would show
`exit=0` plus the printed hash) is absent.

> **Rule.** The committed hash is the target. It is **not** evidence that this
> rebuild reproduced it. Only a build transcript or a shipped rebuilt binary can
> close that gap. M4 keeps the two apart.

**Status:** target hash **CONFIRMED**; this run's output **NOT VERIFIED**.

---

## 4. Check 2 — 251 deterministic runs

Record 118 describes the run as `--repeat 50` (§0) and later as
`--repeat 50` + `--repeat 200` (§5); `1 + 50 + 200 = 251`, and the README repeats
"251". The arithmetic is consistent.

What is missing is the measurement. The only trigger transcript in this
workspace is the **first build's** `T30/trigger-observation.txt`, which documents:

```text
single run                : 1
50 consecutive runs       : 50x 05040a
10 ASLR-on contrast runs  : 10 distinct values
```

That is a 50-run determinism claim, not 251, and it belongs to the uid-14 window.
`04-trigger.txt` — the file that would carry the 251 runs — is absent.

**Status: NOT VERIFIED.**

A secondary narrative inconsistency worth fixing: §0's "return summary" shows
only `--repeat 50`, while §5 adds `--repeat 200`. A reader taking §0 as the
complete run would count 51, not 251.

---

## 5. Check 3 — baseline-clean window

Record 118 §2 makes the right kind of claim: `snapshot.current = "11"`, 0 `.lck`,
boot 21:43, `~/cwe416` absent, home = `D evaluator repair-input route-a`. Those
are exactly the observations that would distinguish a reset from a resumed
session.

None of them is evidenced here. `01-window-and-isolation.txt` is absent, and the
first build's `T30/isolation-reset.txt` documents the **opposite** window
(uid 14, `t15-t6-work`, reset open, 12 `.lck`). It cannot corroborate the
baseline claim.

**Status: NOT VERIFIED.**

This is the check with the highest evidential value: the whole point of the
second window is that the same bytes came out of a *different, clean* snapshot.
Without `01`, that point is asserted rather than shown.

---

## 6. Upgrade gate — the five items, and what each proves

118 moves to **VERIFIED (rebuild)** only when all five are readable and pass.

| # | Item | What M4 checks | What it proves |
|---|---|---|---|
| 1 | **Dual manifests**: `06-SHA256SUMS` (guest, over `01`–`05`) + `SHA256SUMS` (host, whole dir) | re-hash every file; assert full coverage in both | the package is intact and no file is unbound |
| 2 | **`02-build.txt`** | `exit=0`; printed `sha256=c9c2632e…23c9`; `size=25344`; the `-Wuse-after-free` lines present | **this run** produced the target bytes |
| 3 | **`04-trigger.txt`** | single + `--repeat 50` + `--repeat 200`; **one** distinct observation; ASLR-on contrast | 251 runs, deterministic under `setarch -R` |
| 4 | **`01-window-and-isolation.txt`** | `snapshot.current "11"`; 0 `.lck`; boot time; `~/cwe416` absent; expected home contents | the window was **baseline-clean**, not resumed |
| 5 | **`07-rebuild.json`** | field-by-field vs `T30/build.json`; 12/13 equal; only `window.is_baseline` differs | the rebuild is conformant, and the difference is the intended one |

Failure of any item leaves the status at `REPORTED, NOT VERIFIED`. Items 2–4 are
the substantive ones; manifests without a build transcript prove integrity only.

**Current availability (2026-11-05 22:09): 0 of 5.** None of the rebuild
directory's files is present. The only `SHA256SUMS` in scope is
`_m4-verify/T30/SHA256SUMS`, the **first build's** manifest (uid 14); it is not
the rebuild manifest and cannot stand in for gate 1. A full-depth search of the
workspace (including `_m1-work` and the Desktop/Downloads areas) found no
`t30-rebuild-2026-11-05` directory and no `01-window-and-isolation.txt`.

---

## 7. Record 116 — diagnostic, not a T8.3 fixture

Reaffirmed. Record 116 carries the in-file banner (record 118 §7):

> "this record is a build/trigger diagnostic, and is NOT a T8.3 fixture"

M4 concurs. Consequences unchanged: `original.variant.elf` is never ingested;
the synthetic fixture's `output.sha256` stays `null`; nothing in 116 relieves
T8.3. No further edit to record 116 is required.

---

## 8. Decision separation — A/B is not the V0–V5 gate

Corrected per the Lead ruling. Two independent decisions:

| Decision | Question | Owner | What it unblocks |
|---|---|---|---|
| **116 Fix A/B** | how does the **synthetic** fixture link? | Lead | 116's build shape only |
| **T8.3 no-input contract** | can the acceptance model represent a case with **no input**? | contract owner | contract loadability → V0–V5 |

- Choosing **B** does not make the contract loadable.
- Choosing **A** does not make the synthetic sample public.
- Neither A nor B satisfies T8.3's second-public-sample requirement.
- A verified T30 rebuild changes neither.

**V0–V5 verification is deferred pending the no-input contract decision, not
pending A/B.** V0–V5 remain **NOT VERIFIED**.

Full note: `M4-decision-separation-116-t83-2026-11-05.md`.

---

## 9. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work**; no verdict here |
| Merge | **none** |
| Tag | **none** |
| Live success | **none** |
| Host execution | **none** |

---

## 10. Evidence

| File | Content |
|---|---|
| `M4-118-verification-evidence-2026-11-05.txt` | commands showing the absent files, the confirmed target hash, the 251/50 discrepancy, and the unresolvable commit |
| `M4-decision-separation-116-t83-2026-11-05.md` | the A/B vs no-input-contract separation |
| `118-m3-t30-baseline-rebuild-2026-11-05.md` | M3's report — cited, not attested |
| `README.md` | rebuild-directory description — cited, not attested |
| `M3-T30-CWE416-fixture.zip` | first-build package (uid 14), unchanged |

```text
Status: 118 remains REPORTED, NOT VERIFIED until the evidence directory is readable.
Gates available: 0 of 5. Gates 2-4 are substantive; manifests alone cannot close them.
Target hash confirmed; this run's output not verified.
Upgrade requires all five items: dual manifests, 02, 04, 01, 07.
A/B is a build-shape decision; the no-input contract is a separate model decision.
Record 91 unchanged; same operator; no merge, no tag, no live success.
```
