# 132 — Lead: no marker without a replay; CWE122 stays non-PIE and its recipe must say so

- **Owner:** Lead (decision only; no product code in this record)
- **Date:** 2026-11-06
- **Status:** binding for 124, V4, CWE122 and T8.3; changes no gate, no verdict, no merge, no tag
- **Basis:** M4's self-check stop, record 117's open variant question, and measurements in
  `132-lead-environment-and-pie-evidence-2026-11-06.txt`
- **Numbering:** 125–131 and 134–135 are taken; this record takes 132

---

## 0. Decision

| Item | Decision |
|---|---|
| M4's stop | **Correct.** No environment, no replay, no marker. |
| `replay.verified_by="m4"` | **Not written.** Writing it without a replay would be a false verifier statement. |
| V4 | **`not_run`**, unchanged |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED**, independent |
| CWE122 provenance | **Contract's non-PIE requirement stands.** The recipe is the thing that is wrong. |
| PIE as a future direction | Only by a **formal contract + task amendment and re-review**; never by default, never silently |
| T8.3 | **BLOCKED** on both blockers below |
| Merge / tag / live success | none |

Two independent blockers now hold T8.3:

1. **V4 evidence** — M4 has no environment to replay, so the marker cannot be
   written and V4 stays `not_run`.
2. **CWE122 build provenance** — the committed artefact is non-PIE, but its
   `build.sh` as written produces PIE, so the recipe and the artefact do not
   describe the same build.

## 1. The stop, verified

M4 measured its own host; I re-measured from this host, so the record does not
rest on a single machine's claim. The two agree on what matters:

| Check | Result |
|---|---|
| `/opt/angr-venv/bin/python` | **absent** (exit 127) |
| `python3.12` | **absent** (this host has 3.11.8) |
| `import angr` | **ModuleNotFoundError** |
| guest `192.168.30.128` | **100% packet loss** from this host (subject to this host's routing) |
| `selfcheck.py` / `run_selfcheck.sh` in the workspace | **not shipped** — nothing to run |

Because the path is a Linux path, its absence on a macOS host proves nothing
about M3's guest; the load-bearing measurement is M4's own `exit 127`, and M4's
record states it. What is now established beyond doubt is that **no runnable
environment was delivered to M4**, and no self-check script was handed over.

Consequence: self-check 18/18 NOT RUN; V4 harness ×2 NOT RUN; five criteria NOT
CHECKED; marker NOT WRITTEN.

## 2. Why the marker must not be written anyway

`verified_by="m4"` is a statement that M4 ran the analysis and the result held.
It is not a status flag to unblock ingestion. Record 131 §2 measured that the gate
is an operator marker, not a signature: a hand-edited marker is accepted by
`validate_v4_evidence(..., require_independent=True)`. So once written without a
run, **nothing in the product would catch it** — the attempt would read as if an
independent replay had happened.

That is exactly the failure mode the whole gate exists to prevent, and it would be
undetectable afterwards. M4's stop is therefore the correct behaviour, not a
schedule problem.

## 3. CWE122: the mismatch, measured

| Fact | Evidence |
|---|---|
| Contract requires non-PIE | `contract.json:12` — "Linux x86-64 non-PIE guest" |
| Declared recipe is non-PIE | `build.json` argv contains `-fno-pie -no-pie`; `output.sha256 = c9ddb9c2…c4915` |
| Committed artefact is non-PIE | `original.elf` 26,344 B, `e_type = 2` (EXEC), sha256 `c9ddb9c2…c4915` |
| Test manifests bind that artefact | `tests/valid.json` and `tests/invalid.json` `original_sha256 = c9ddb9c2…c4915` |
| **`build.sh` as written is PIE** | line 7: `gcc -O0 -g -DINCLUDEMAIN -DOMITGOOD -I support src.c support/io.c -o original.elf` — no `-fno-pie -no-pie` |
| The sibling recipe does carry the flags | CWE416 `build.sh:43` has `-fno-pie -no-pie`; its artefact is EXEC |
| Record 117 measured the PIE alternative | `d50641cb…bb8a`, 26,304 B — and flagged the variant as the Lead's decision |
| Nothing would catch a PIE artefact today | `tools/fixture_intake.py:151-154` checks the ELF magic only; no `e_type` check |

The artefact hashes because M3 built it with the flags from `build.json` argv,
not from `build.sh`. That is a reproducibility hole: a reader who runs the
committed script gets a different binary (PIE, `d50641cb…`), and every pin in the
fixture then disagrees with the build.

Note also: `CWE121_src_char_declare_cpy_51b/` ships `contract.json`, `original.elf`
and `tests/` but **no `build.sh`/`build.json`**, so that fixture's build is not
reproducible from the tree at all. Its artefact is EXEC, so this is a provenance
gap, not a PIE conflict.

### 3.1 Exact work for CWE122 (owner M3)

1. Add `-fno-pie -no-pie` to `build.sh` so it matches `build.json#argv` and the
   contract.
2. Rebuild in the guest and compare: if the digest is `c9ddb9c2…c4915`, the
   recipe and the artefact now agree and no pin changes. If the digest differs,
   **stop and report** — do not silently re-pin; a different digest from an
   identical recipe means the toolchain differs from the one that produced the
   pin.
3. If (and only if) step 2 yields a new digest that must be adopted: update
   `build.json#output.sha256`, `tests/valid.json`, `tests/invalid.json`,
   regenerate `tests/SHA256SUMS`, and re-run intake. Record the old and new
   digests in one place.
4. Never rename a PIE artefact into a non-PIE fixture slot, and never keep the
   old `c9ddb9c2…` pin while shipping a different binary.

### 3.2 Tooling gap (owner M5, with M1 review)

Add an ELF-type check to `tools/fixture_intake.py`: read `e_type` and compare it
with the contract's stated environment (`non-PIE` ⇒ `ET_EXEC`); a `DYN` artefact
must fail with a finding, not pass silently. Until that lands, the check is
manual and this record is the reason it exists.

## 4. If the Lead later chooses PIE

Not today, and not by default. Doing it properly means one change, reviewed as a
whole:

1. Amend `contract.json#environment_assumptions` and the task text together.
2. Change the recipe and rebuild; accept that fixed-address edit authorisations
   ("verified-unused region of an R-X PT_LOAD, RIP-relative references only") no
   longer hold as written and must be restated.
3. Re-pin `output.sha256`, both manifests, `SHA256SUMS`; re-run intake.
4. Re-review by M4 and M5, because the repair contract changed, not just a hash.
5. Any existing candidate bound to the non-PIE original becomes inapplicable —
   including 124's `46d16e99…fcd0`, which is an edit to the non-PIE CWE416
   artefact and is unrelated to CWE122, but the same rule applies to any future
   CWE122 candidate.

A PIE change that updates a hash but not the contract is not a decision; it is a
silent contract change.

## 5. Assignment

**M1 — host backend.**
Keep 124 at `inconclusive` / `required_check_not_run` / `symbolic`. Keep the
`verified_by="m4"` gate; do not ingest a V4 claim without the marker. Help deliver
a guest or a same-version venv for M4. Keep CWE121 v2 `24bfe568…4e37` and the 120
gate. T8.3 blocked; no merge to `main`, no tag, no live-success text.

**M3 — producer and guest.**
Deliver something M4 can actually run: guest access, or `run_selfcheck.sh` /
`selfcheck.py` / `cwe416-v4-env-2026-11-06/` with the exact pins (Python 3.12.3,
angr 10.0.4.post1, z3 5.1.0). Do §3.1 for CWE122. Never write
`verified_by="m4"`. T8.3 stays blocked; no invented second defect class.

**M4 — verifier.**
When the environment exists: self-check 18/18, then two independent harness runs,
then the five criteria; only then the marker. Wait for the PIE/non-PIE decision
before verifying a CWE122 second-class sample. Keep 124 and 118 exactly as they
are; record 91 unchanged; same operator; reviews 9–12 separate; no merge, no tag,
no live-success text.

**M2 — console.**
Continue T8.2 (`assistant_llm.py`, `test_assistant_llm.py`) with the approved
`gates/v3` shape: `partial=true` renders "部分真实用量", `None` renders "未提供".
Not part of the T8.3 producer or guest work.

**M5 — data contracts.**
Add the ELF-type check (§3.2) and keep the contract's non-PIE requirement
enforced rather than assumed.

## 6. State carried forward

| Item | Value |
|---|---|
| V4 | `not_run`; marker not written; self-check not run |
| 124 | `inconclusive` / `required_check_not_run` / `symbolic`; candidate `46d16e99…fcd0` |
| 118 | VERIFIED (rebuild evidence package), independent |
| CWE122 | non-PIE `c9ddb9c2…c4915` (26,344 B, EXEC) pinned; `build.sh` must gain the flags |
| CWE122 PIE alternative (not adopted) | `d50641cb…bb8a`, 26,304 B |
| T8.3 | BLOCKED (environment + CWE122 provenance) |

## 7. Not claimed

- No claim that M3's guest lacks the venv; only that M4 was not given a runnable
  one, and no self-check script was shipped.
- No claim that the CWE122 artefact is wrong — it is the recipe that disagrees.
- No claim that a PIE fixture is unacceptable in principle; only that it needs a
  formal amendment, not a hash swap.
- No gate, verdict, merge or tag was changed to publish this record.

## 8. Signature

| Role | Name | Date | State |
|---|---|---|---|
| Lead | Lead | 2026-11-06 | published |
| M1 | — | — | pending acknowledgement |
| M3 | — | — | pending acknowledgement |
| M4 | — | — | pending acknowledgement |
| M2 | — | — | pending acknowledgement |
| M5 | — | — | pending acknowledgement |
