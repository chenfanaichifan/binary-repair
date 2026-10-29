# 32 — M5 formal v2 replay: cross-input authorization + canonical record sync

**Recipients:** Member 5, Member 4, Member 3/VMer, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** v2 remains the sole accepted evidence bundle. Support is historical (its manifest
format is non-standard, noted below). **v1 is not required.** The formal v2 replay is resolved
by a **cross-input, hash-bound authorization** (option B) unless M5 prefers a self-contained
re-issue. Canonical record is M4's `0b3b51e4…8f2da`; M5's `73b5e824…` record must not be
maintained as a competing version. Gate 3: items 1–6 PASS, M4 verifier signed, **M5 replay row
and Lead approval row still blank**.

> **Addendum (handoff 33):** this resolution was executed — the cross-input replay produced
> `c4a159…` from `aa428157…`, bound to v2; **Gate 3 is now APPROVED** with all three signature
> rows filled (record hash `0b3b51e4…8f2da`).

---

## 1. Support manifest — verified, historical, format limitation

| Item | Value |
|---|---|
| support zip | `3d49625c619c065e7942c8de7d433a58365f4ad616901f2de8b922cf962f72b0` (4,004 B) — verified |
| support `SHA256SUMS` file hash | `7cf4b4f61d815aee5bc1aeb1f1acdb90ba341d7375bbce5014c71ebcf2bba938` — verified, matches M4's value |
| two manifest hashes | `e53253cf…` / `3bdbc339…` — manually verified |
| format | lines are `filename UPPERCASE_HASH`, **not** `<sha256>  <path>`; `sha256sum -c` rejects the file, so a whole-package standard check is not possible. The two hashes are correct; record the format limitation, do not call the package "fully tool-verified". |

Support is **historical**: the accepted item-6 evidence is the v2 bundle, which contains the
same two manifests (standard layout) and its own `SHA256SUMS` 22/22. No support manifest needs
to be merged with anything.

## 2. v1 — not required

`gate3-bundle-2026-10-22.zip` (`0ef65546…`) is not delivered to M5 and **is not needed**: v2 is
the sole evidence bundle. Do not compute a v1 evidence-manifest hash and do not treat its
absence as an open gate-3 blocker.

## 3. Formal v2 replay — authorization (option B, cross-input hash-bound)

M5 correctly reports that v2 is raw evidence and does not contain `candidate.elf`,
`original.elf`, or `regen_c4a159.py`, so an in-bundle regen cannot run. Two permissible paths:

- **Option A (self-contained):** VMer re-issues `gate3-bundle-v2b` with the three inputs added;
  new zip hash; M5 replays inside the bundle.
- **Option B (authorized now):** M5 replays with the **hash-bound handoff inputs** and binds the
  result to the formal v2 evidence. This is not a hash mismatch and is not a weaker check,
  because every input and output is content-addressed:

  1. inputs from `m5-delivery-2026-10-22.zip`: original `aa428157…8393`, candidate
     `c4a159…aa82`, regen script `56331eedb4d72c55eec4e0f105fb20207576e6e6860b79ca4cedb175ed54e843`;
  2. run `python3 regen_c4a159.py original.elf replayed.elf`; require
     `sha256(replayed.elf) == c4a159…aa82` and `cmp` against the handoff candidate;
  3. bind to v2: v2 `candidate-before.txt` / `candidate-after.txt` / summary detail must all be
     `c4a159…aa82`; contract canonical `24bfe568…4e37` and contract file `15f6b492…` must match
     the v2 values; v2 zip `6151a806…0a65`; v2 evidence-manifest `4ba6ebad…6934`;
  4. record as **`REPLAYED (cross-input, hash-bound)`** with the exact inputs/outputs above.
     This fills the M5 row; it is not a formal in-bundle replay, but the gate decision may treat
     it as equivalent because the bytes are identical by hash.

If M5 prefers strict in-bundle replay, use option A; either way the record must say which was
done. No candidate edit, no fabricated hash, missing inputs never "pass".

## 4. Canonical record sync — required

M5's branch `origin/member-5/gate3-formal-v2` @ `3329ac7` carries a record with SHA-256
`73b5e824…` and stale item states (3/5 `NOT VERIFIED`, M4 row blank). That is **not** the
canonical record. Canonical is:

| Field | Value |
|---|---|
| path | `docs/route-a/gate3-record.md` on `origin/member-4-verification` @ `ad0128a` |
| SHA-256 | `62ed341b2b4416784f26ce342ffdf53689c37b5ce44a13730be1f256b2114d8b` |
| items | **1–6 PASS** (v2 content verified 21/21) |
| signatures | **M4 verifier signed**; M5 row blank; Lead row blank |

M5 must take this record as its base, fill only the M5 replay row (option A or B format), and
push. Do not re-open items 3/5 and do not blank the M4 row; item statuses are M4's verification,
not M5's replay scope.

**Confirmation log.** 2026-10-22 — support manifest hash verified but format-limited/historical;
v1 not required; formal v2 replay authorized as cross-input hash-bound (option A available);
canonical record `62ed341b…4d8b` on `member-4-verification`; M5 to add replay row only; Lead
approval last; Gate 3 not yet approved.
