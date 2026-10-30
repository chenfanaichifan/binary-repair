# 33 — Gate 3 approved: v2 evidence, M4 verifier, cross-input M5 replay, Lead approval

**Recipients:** Member 4, Member 3/VMer, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** **Gate 3 is APPROVED and closed.** v2 is the sole evidence bundle; v1 and the support
package are historical. Gate 4 remains **NOT RUN**, Gate 5 Route A runtime remains guest-scoped,
Gate 6 remains partial, fixture `NOT FROZEN`.

---

## 1. Decision

The formal-v2 replay blocked only because the v2 raw-evidence bundle does not carry the build
inputs (`candidate.elf`, `original.elf`, `regen_c4a159.py`). The Lead authorizes the
**cross-input, hash-bound** replay (handoff 32, option B) and closes Gate 3 because every input
and output is content-addressed and was independently re-run:

| Step | Observed |
|---|---|
| original (handoff delivery) | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`, 26,792 B |
| regen script | `56331eedb4d72c55eec4e0f105fb20207576e6e6860b79ca4cedb175ed54e843` |
| `python regen_c4a159.py original.elf replayed.elf` | rc 0, wrote `replayed.elf` |
| replayed | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`, 26,792 B |
| handoff candidate | `c4a159…aa82` — **cmp MATCH** |
| v2 candidate-before/after | `c4a159…aa82` (both files, summary detail) |
| contract | canonical `24bfe568…4e37`; file `15f6b492…` |
| v2 bundle | `6151a80633fdde0d9b1ce87c126b01994a730625557d17297828468799710a65`, 18,318 B, inner sums 22/22 |
| v2 evidence-manifest | `4ba6ebad30a4035c6a16c62c1fbab53dda67bce60db2b87510b83aa97f876934` |

No hash was fabricated and no candidate bytes were changed. M5's own handoff replay (§8.1) and
this binding check agree.

## 2. Signatures (canonical record)

`docs/route-a/gate3-record.md` on `origin/member-4-verification`:

| Role | State |
|---|---|
| M4 verifier | signed 2026-10-22 — items 1–6 PASS against v2 bundle `6151a806…` |
| M5 build/hash replay | recorded 2026-10-22 — `REPLAYED (cross-input, hash-bound)` |
| Lead approval | signed 2026-10-22 — **Gate 3 APPROVED**, scoped to Gate 3 only |

Canonical record hash after approval:
`0b3b51e49f24c5759ff5d37a0569d44149af989dd4e72af6e51b279f0901f2da`.

## 3. Cleanup decisions

- **v1 bundle** (`0ef65546…`): historical; not required, not replayed.
- **support package** (`3d49625c…`): historical; its manifest hash `7cf4b4f6…` is valid as a
  file hash but the manifest format is non-standard (`filename UPPERCASE_HASH`), so it was never
  claimed as tool-verified; v2's standard 22/22 supersedes it.
- **M5's branch record** `73b5e824…` @ `3329ac7`: stale; canonical is the record above. Do not
  maintain two records.
- **M5 patch re-review** (`2ac0f66` / `b68aabcd…cab8`) remains a separate review item; base
  `ad1a1f8` is behind `main` — rebase only if M5 asks.

## 4. Scope statement (important)

Gate 3 PASS covers **only** the six Gate 3 items on the v2 evidence. It does **not** imply:

- Gate 4 PASS — formal status is **NOT RUN** (CI `6/6` is supplementary);
- Gate 5 runtime PASS — Route A static placement proof only, guest runtime remains scoped work;
- Gate 6 PASS — V4 symbolic still pending;
- fixture frozen — it is not.

**Confirmation log.** 2026-10-22 — Gate 3 approved: v2 accepted, M4 verifier signed, M5
cross-input hash-bound replay executed and matched (`aa428157…` → `c4a159…`; v2 `6151a806…`,
manifest `4ba6ebad…`), Lead approval signed. Scope limited to Gate 3; Gate 4 NOT RUN.
