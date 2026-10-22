# 19 — Ruling: Gate 3 replay waiver (build/hash replay still required)

**Recipients:** Member 5 (replay owner), Member 4 (gate-3 record), Member 3 (guest/evidence),
Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** binding ruling for the Gate 3 record. No gate status changes: Gate 3
`CONDITIONALLY FEASIBLE`, Gate 4 `NOT RUN`, fixture `NOT FROZEN`. Items 3–6 remain
`NOT VERIFIED`; the record stays **DRAFT / unsigned**.

---

## 1. Ruling (exact wording, to be quoted in the record)

> **The Lead waives only the full independent rerun of the six frozen cases by Member 5.
> Member 5's build/hash replay is not waived: M5 must reproduce `c4a159…aa82` from the recorded
> recipe on `original.elf` (`aa428157…`), verify the canonical contract `24bfe568…4e37`,
> recompute the evidence bundle's `SHA256SUMS` and bundle hash, and report the observed values.
> If that replay is missing or does not match, the gate-3 record is `NOT VERIFIED` and the
> signature line stays blank.**

Rationale: the waiver removes duplicate *runtime* execution (already covered by VMer/M3 under
isolation and by M4's independent checks), not the identity proof. Candidate bytes and the
evidence bundle hash must be independently reproducible by the second owner before approval.

## 2. Effect on the documents

- `docs/route-a/gate3-record.md` is updated to **DRAFT — NOT SIGNED**; six items are
  `1 PASS / 2 PASS / 3–6 NOT VERIFIED`; a signature table with blank fields is added; §7.5 cites
  this ruling.
- Earlier wording in the record ("M5 replay waived by Lead") and the general "M5 replays" in
  handoff 13 §7 / handoff 16 §6 are read through this ruling: **full rerun waived, build/hash
  replay required**. No other replay step is waived.
- Nothing here re-opens the oracle, manifests, contract constants, or frozen hashes.

## 3. What M5's replay must record

| Item | Required observation |
|---|---|
| candidate | reproduce `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` from `original.elf` + the recorded recipe (`regen_c4a159.py` / `routea.cave`) |
| contract | `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` recomputed with `contract_sha256` |
| evidence manifest | recompute the sorted `SHA256SUMS` hash over the delivered raw evidence set (no bundle package — handoff 21); report candidate, contract and manifest hashes |
| mismatch | stop and report the concrete difference; no signature, no "close enough" |

M5's replay does not replace M4's independent verification and does not create a second
candidate or contract.

## 4. Canonical gate-3 record (single version)

`docs/route-a/gate3-record.md` is **not** in the `1826505` archive (that archive predates the M4
evidence record). The single canonical draft lives on `origin/member-4-verification`:

| Item | Value |
|---|---|
| path | `docs/route-a/gate3-record.md` (repo root on `member-4-verification`) |
| state | DRAFT, unsigned; items 1–2 PASS, 3–6 NOT VERIFIED |
| SHA-256 of the draft | `62ed341b2b4416784f26ce342ffdf53689c37b5ce44a13730be1f256b2114d8b` |

Anyone holding another draft of the same file must replace it with this version (or send a diff
against this SHA-256) rather than keeping two records. After a signed version exists it is the
record that gets merged to `main`; the draft is not gate evidence.

## 5. Signature rule

- M4 signs only after items 3–6 are `PASS` with raw evidence.
- M5's build/hash replay is recorded before the Lead approval line is filled.
- Missing replay or missing runtime evidence = `NOT VERIFIED`; never a pass.
- The signature table in the record stays blank until then.

**Confirmation log.** 2026-10-22 — Lead rules: full independent rerun waived; build/hash replay
required (`c4a159…`, `24bfe568…`, bundle `SHA256SUMS`/bundle hash); gate-3 record stays DRAFT,
unsigned, items 3–6 `NOT VERIFIED`; canonical draft path/hash pinned to
`docs/route-a/gate3-record.md` on `member-4-verification`. No gate status changed.

---

## 6. Addendum (2026-10-22): bundle declined — manifest hash replaces bundle hash

VMer will not produce a packaged evidence bundle (handoff 21). The replay ruling above is
unchanged except for the hash object:

- candidate `c4a159…aa82` and contract `24bfe568…4e37` requirements are unchanged;
- the "bundle `SHA256SUMS`/bundle hash" is replaced by the **SHA-256 of the sorted
  `SHA256SUMS` manifest over the delivered raw evidence set** (`evidence-manifest-sha256`);
- the gate-3 record was updated to the bundle-free item-6 definition; its canonical hash is now
  `62ed341b2b4416784f26ce342ffdf53689c37b5ce44a13730be1f256b2114d8b`;
  `bddccbfe…e081` and `3dcdc862…` are **void** and must not be cited.
