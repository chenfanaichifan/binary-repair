# Phase-8C final release evidence (2026-11-16)

This addendum is stored on the evidence branch and is the final-SHA CI/gate
record for the Phase-8C release. It does not change the gated tree.

- gated/release SHA: `4a7b2355ffc5225d013a777bc7d588abac58f944`
- gated tree SHA: `4bf501314b6469328d0256031990bfc402ce6677`
- frozen-tree nightly gate: **13/13 required checks passed**, 0 failed,
  0 skipped, 0 unavailable; `mainline_unchanged=true`
- final hosted CI: run `43748886046` (CI) and run `43748886289` (Ubuntu verification),
  both success on `4a7b2355ffc5225d013a777bc7d588abac58f944`
- previous gated-code CI recorded in claims: run `43744573286` / Ubuntu
  `43744573230` on `f1ba37eee5146b5bb5de97046a0f8b4b653538ff`; the final run above
  covers the final release SHA. Both are real runs; no CI claim is transferred
  between SHAs.
- self-hosted Lima nightly: `not_run` (no self-hosted runner); the local
  frozen-tree nightly gate is separate evidence. Signoff:
  `docs/operations/phase8c-ci-signoff.md`

## Final public benchmark

- manifest `d46f06bf...`: 32 samples, 24 runtime-oracle, 8 analysis-only,
  dev 18 / validation 14; 30 executed, 2 unsupported.
- 3 verification attempts: 2 independently verified, 1 rejected; published
  `false_verified=0`; 1 deterministic claim (`heap-malloc`) withdrawn after
  independent ABI rejection. Two serialized public repeats were identical
  (`a477ea3c...`), but unconditional stability is not claimed.
- eligible repair cases 24; verified-repair rate 2/24 = 0.0833;
  detection/root-cause/localization 3/24; analysis-only detection 6/8.

## Final hidden benchmark

- commitment `eaec60aadd42388efb725a668b887465268c78fd257ec4622ac56eac571bae12`
  (file `3ebf2901...`); 8 samples = 6 runtime + 2 analysis-only.
- all 8 executed; 0 candidates, 0 independently verified, 0 rejected,
  0 `false_verified`. Hidden material, PoCs, reference fixes, paths and
  per-sample ids are not published; only opaque commitment and aggregate counts.
- hidden/public contamination: clean; the initial public-identical hidden
  variant was regenerated before the final campaign.
- no hidden generalisation or hidden availability claim.

## Evidence and limitations

- Public/hidden contamination clean; full quality audit `ok` with one warning
  that the public manifest does not advertise the separate hidden commitment
  (intentional, avoiding a circular manifest/commitment digest).
- The two public verified repairs remain deterministic fixture repairs under
  declared target scope; no arbitrary-binary/whole-program capability.
- External ingestion `not_run` (no local external corpus); compiler variants
  use one Zig 0.17.1 toolchain; cross-compiler verification not claimed.
  Phase-8D and Phase-9-16 are not implemented.
- The earlier one-off C1 reproduction flake remains a documented warning; it
  was not reproduced across two serialized repeats under the C11 lock.
- No new vulnerability-repair capability, automatic upgrade, hidden
  availability, or capability promotion is claimed.
