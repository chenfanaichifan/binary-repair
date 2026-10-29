# 29 — M5 replay is PARTIAL/BLOCKED: evidence-manifest files delivery

**Recipients:** Member 4, Member 3/VMer, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** M5's partial replay is accepted and recorded. **No replay PASS, no verifier signature,
no approval.** Gate 3 remains `CONDITIONALLY FEASIBLE`; record items stay **1/2/4/6 PASS,
3/5 `NOT VERIFIED`**, DRAFT.

---

## 1. What M5 confirmed (accepted)

| Item | Value |
|---|---|
| candidate | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` — verified |
| contract canonical | `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` — verified |
| v1 bundle zip SHA-256 | `0ef655464459dd0597f8259b3784ee15389884c9a75b26afa1299af7f54bf8d5` (13,530 B / 21 files; M4 verified inner sums 20/20) — known value, not recomputable by M5 yet |
| item-6 support zip SHA-256 | `3d49625c619c065e7942c8de7d433a58365f4ad616901f2de8b922cf962f72b0` (4,004 B) — known value |
| chain manifest | `e53253cf1c3408d832dd4c30b6e75afc4e8c2d621a2c0a3c0959131255878e7c` |
| harness manifest | `3bdbc3396fd183ed8563e2d7b0648d02be3a3c55c1a52ccc08890614a97ed678` |

## 2. Delivered by M4 to the shared workspace

| File | SHA-256 |
|---|---|
| `delivery/gate3-item6-support-2026-10-22.zip` | `3d49625c619c065e7942c8de7d433a58365f4ad616901f2de8b922cf962f72b0` (verified after copy) |
| `delivery/evidence-manifests/gate3-item6-support-SHA256SUMS.txt` | file hash `7cf4b4f61d815aee5bc1aeb1f1acdb90ba341d7375bbce5014c71ebcf2bba938` |

The support manifest lists the two files (uppercase hex, exactly as produced):
`harness-v2-manifest.txt E53253CF…8E7C`, `harness-manifest.json 3BDBC339…D678`.
`evidence-manifest-sha256` for the support package = SHA-256 of that `SHA256SUMS` file =
`7cf4b4f6…a938`.

## 3. Still missing for M5

M5 cannot compute the **v1 bundle** evidence-manifest hash because the v1 zip and its inner
`SHA256SUMS` have not been delivered to an M5-readable location. Required:

- `gate3-bundle-2026-10-22.zip` (13,530 B, zip SHA `0ef65546…f54bf8d5`) copied to
  `D:\BinaryRepair_Project\delivery\` **or** its inner `SHA256SUMS` file delivered;
- for the final replay: the formal **v2 bundle** `gate3-bundle-v2-2026-10-22.zip`
  (18,285 B, 23 files, reported `8256c850…be64f`) similarly copied.

Do not substitute the zip hash for `evidence-manifest-sha256`: handoff 21 §2 defines it as the
SHA-256 **of the `SHA256SUMS` file bytes**, not of the package.

## 4. M5 replay state (recorded as-is)

```text
M5 build/hash replay: PARTIAL / BLOCKED
  candidate c4a159…aa82: verified
  contract 24bfe568…4e37: verified
  v1 bundle evidence-manifest: NOT VERIFIED — file not delivered
  item-6 support evidence-manifest: 7cf4b4f6…a938 (delivered; M5 may recompute)
  formal v2 bundle: NOT VERIFIED — file not delivered
```

M4 verifier row and Lead approval row stay blank. Once the v1 zip/SHA256SUMS and the formal v2
bundle are delivered, M5 computes the manifest hash(es), records the replay line, then M4 fills
the verifier row and the Lead approves.

**Confirmation log.** 2026-10-22 — M5 partial replay accepted; support package + its
`SHA256SUMS` (hash `7cf4b4f6…a938`) delivered to the shared workspace; v1 bundle and formal v2
bundle still required before a replay PASS; no signature, no gate change.
