# 20 — Confirmation: gate-3 draft adopted by M4, verification scope, snapshot v2

**Recipients:** Member 4 (draft owner), Member 3 (VMer-side evidence), Member 5 (build/hash
replay), Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** record-keeping confirmation only. **No gate status changes:** Gate 3
`CONDITIONALLY FEASIBLE`, Gate 4 `NOT RUN`, fixture `NOT FROZEN`; six items remain
`1 PASS / 2 PASS / 3–6 NOT VERIFIED`; the record stays **DRAFT, unsigned**.

> **Addendum 2026-10-22 (superseded hash):** after VMer declined the packaged bundle,
> `docs/route-a/gate3-record.md` was updated to the bundle-free item-6 definition (handoff 21).
> The new canonical hash is `b6fedd2b0e82e8d553fd1e9321393c848438f54ce0abea058afa2fa90d66bf0b`;
> both `bddccbfe…e081` (adopted below) and `3dcdc862…` are **void** and must not be cited.
> The adoption/verification-scope statements below remain historically true; only the file
> hash is superseded.

---

## 1. Draft adoption (M4 confirmed)

M4 confirmed that the local copy was replaced with the canonical draft and that only one version
is kept:

| Item | Value |
|---|---|
| canonical draft | `docs/route-a/gate3-record.md` on `origin/member-4-verification` @ `2ecab3d` |
| SHA-256 | `bddccbfee70733223a43bed0d0420c1ec130cb6fa07338c402a8355cc6a9e081` |
| old draft hash | `3dcdc862e292d67ad6d645294dfac2c4a311854ebd43caef9a5d70ad93fdd3ee` — **VOID, do not cite** |
| copies | one canonical copy; `delivery/gate3-record-draft.md` is the same bytes/hash (transfer copy only) |

Anyone holding the old hash must replace the file with the `bddccbfe…e081` version or send a
diff against that hash; do not maintain two drafts. Editing the draft again requires a new
hash and a new notification to everyone listed here.

## 2. Verification scope (do not overstate)

- **M3-side:** verified only the SHA-256 of the downloaded file,
  `bddccbfe…a9e081`. That is a file-integrity check, **not** gate-3 evidence.
- **Lead-side:** `HEAD = 2ecab3d`, `delivery/gate3-record-draft.md` equals the canonical hash,
  and the `docs/route-a/SHA256SUMS` entry matches. These are the Lead's checks, not M3's.
- Neither check upgrades any gate-3 item. Items 3–6 stay `NOT VERIFIED` until VMer/M3 produce
  the runtime evidence and M5 records the build/hash replay.

## 3. Snapshot naming: `gate3-harness-v2`

VMer plans to use **`gate3-harness-v2`** as the harness snapshot name, superseding the working
name `gate3-harness`. Naming only; the requirements are unchanged (handoff 11 §1, handoff 16
§5/§7):

- new snapshot = **new image record**: recompute the chain manifest **powered off**, record its
  SHA-256, the guest fingerprint, and the raw revert command/output/timestamp;
- record the actual snapshot name/id and the VMer operator in the run evidence;
- record wrapper hash/owner/mode and the isolation attestation (`uid 1003`, `CapEff=0`,
  `NoNewPrivs=1`, no egress, `sudo -n true` fails, evaluator unreadable, `Seccomp: 0`);
- candidate SHA-256 before/after, per-case rc/stdout/stderr, original V0 (documented 4/6).

The draft record's procedure is unchanged; the actual snapshot name is filled from the run
evidence when items 3–6 are updated (a later record revision; the current hash stays valid until
then).

## 4. Signing order (unchanged: handoff 19 §5, record §9)

1. M4 fills the verifier row only after items 3–6 are `PASS` with raw evidence (verifier
   signature only — not approval, not a gate pass).
2. M5 records the build/hash replay: `c4a159…aa82`, contract `24bfe568…4e37`, recomputed bundle
   `SHA256SUMS`/bundle hash; mismatch returns the record to `NOT VERIFIED`.
3. Lead fills the approval row last. Until then the record stays DRAFT with blank signature
   rows.

**Confirmation log.** 2026-10-22 — M4 adopts `bddccbfe…e081` as the single draft; old
`3dcdc862…` is void; M3-side file-hash check is explicitly separated from Lead-side checks and
from gate evidence; `gate3-harness-v2` recorded as the VMer snapshot name with the same evidence
requirements. No gate status changed.
