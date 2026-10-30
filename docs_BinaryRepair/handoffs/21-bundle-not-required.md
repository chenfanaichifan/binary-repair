# 21 — Bundle not required: Gate 3 item-6 evidence definition and replay hash

**Recipients:** Member 3 / VMer, Member 4, Member 5, Lead
**From:** Lead
**Date:** 2026-10-22
**Status:** clarification of how Gate 3 item 6 is satisfied after VMer declined the packaged
bundle. **No gate status changes:** Gate 3 `CONDITIONALLY FEASIBLE`, gate 4 `NOT RUN`, fixture
`NOT FROZEN`; items 3–6 remain `NOT VERIFIED` until the guest run exists; the record stays
DRAFT/unsigned.

---

## 1. Decision

VMer will **not** produce a packaged evidence bundle (no `routea.gate3 bundle` archive).
That is accepted. The requirement in handoff 11 §3 item 6 is **raw outputs plus hashes for
every item** — not a particular packaging. The gate is unchanged:

- **Item 6 is satisfied by:** the raw outputs VMer/M3 delivers (per-case stdout/stderr/rc,
  wrapper `summary.json`, runtime-probe log, chain manifest/revert log, isolation attestation,
  test-count output) **plus** a sorted `SHA256SUMS` over exactly those files, and the SHA-256 of
  that manifest.
- **Who builds the manifest:** VMer/M3 may generate it with plain `sha256sum`; if they deliver
  only raw files, **M4** generates the manifest from its own copies and records both the file
  hashes and the manifest hash. M4 does not edit the raw files.
- **What is waived:** only the *packaging tooling* (`routea.gate3 bundle`, zip/archive layout).
  No raw output, no hash, and no isolation precondition is waived.
- A missing manifest/hash is `NOT VERIFIED`; a manifest over partial files is `NOT VERIFIED`.

## 2. Minimal evidence set (no bundle)

| # | File(s) | Required content |
|---|---|---|
| E1 | `original.elf`, `tests/valid.json`, `tests/invalid.json`, candidate | identity hashes |
| E2 | edit manifest / build recipe output | schema-2 manifest + rebuild result |
| E3 | `readelf`/`objdump`/LIEF outputs + runtime-probe log | static structure + R-X mapping/bytes/execution |
| E4 | per-case `*.stdout`, `*.stderr`, `*.rc` + wrapper `summary.json` | six frozen cases, original V0 |
| E5 | chain manifest + guest fingerprint + revert log | isolation evidence, snapshot `gate3-harness-v2` |
| E6 | wrapper attestation (uid/caps/NoNewPrivs/egress/sudo/evaluator/Seccomp) | isolation controls |
| E7 | `SHA256SUMS` (sorted, relative paths) + manifest hash | item-6 hash list |

`SHA256SUMS` format: one line per file, `<sha256>  <relative path>`, sorted by path; hash of the
file itself recorded as `evidence-manifest-sha256`. M4 verifies every line before signing;
M5 replays the candidate/contract and the manifest hash.

**Manifest rules (no weakening):**

1. `LC_ALL=C` sort, paths relative to the evidence root, no `./` prefix, `SHA256SUMS` itself
   excluded (so the manifest can be regenerated without self-reference); the exact generation
   command is quoted in the record, e.g.
   `find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum`.
2. `evidence-manifest-sha256` = SHA-256 of the `SHA256SUMS` file bytes.
3. **Two manifests, never merged:** the VMer/M3 session set (items 3–5) and M4's independent
   copy set. M4 may build a manifest from its own copies but must not rewrite VMer's bytes; a
   manifest over partial files is `NOT VERIFIED`.
4. Item 6 binds to the **same session** as items 3–5; cross-session hashes void item 6.
5. The `SHA256SUMS` file is small and must be transferred through the same human copy channel
   as the archive; otherwise M5 cannot replay the manifest hash. No zip/package is needed.

## 3. Effect on the replay ruling (handoff 19)

Handoff 19 said "recompute the evidence bundle's `SHA256SUMS` and bundle hash". Read it as:

> M5 must recompute the **evidence-manifest `SHA256SUMS` hash** over the delivered evidence set
> (the same relative paths M4 recorded) and report both the candidate/contract hashes and the
> manifest hash. There is no bundle hash to reproduce; the manifest hash replaces it.

Candidate `c4a159…aa82` and contract `24bfe568…4e37` requirements are unchanged.

## 4. Effect on the Gate 3 record

`docs/route-a/gate3-record.md` item 6 and §7 are updated to this definition (raw outputs +
hash manifest; bundle tooling not required). Because that changes the file, the canonical hash
changes: see §5. Six-item statuses and signature order are unchanged.

## 5. Single canonical draft after this change

| Item | Value |
|---|---|
| path | `docs/route-a/gate3-record.md` on `origin/member-4-verification` |
| state | DRAFT, unsigned; items 1–2 PASS, 3–6 NOT VERIFIED |
| SHA-256 | `0b3b51e49f24c5759ff5d37a0569d44149af989dd4e72af6e51b279f0901f2da` (computed after the edit; old `bddccbfe…` and `3dcdc862…` are void and must not be cited) |

Everyone who adopted `bddccbfe…` must replace it with the new hash version (or send a diff
against the new hash). No two records. The next hash change should be the one that fills
items 3–6 from real evidence.

**Confirmation log.** 2026-10-22 — VMer declines the packaged bundle; Lead accepts and defines
item 6 as raw outputs + sorted `SHA256SUMS`/manifest hash; replay hash redefined accordingly; no
gate status or item status changed.
