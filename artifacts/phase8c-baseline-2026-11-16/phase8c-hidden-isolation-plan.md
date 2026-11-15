# Phase-8C hidden corpus isolation plan

Status: design only. C1 does not create or read a hidden corpus; the private root is Lead-owned and its current observed state is recorded below (C1 stats it only, never lists or reads contents).

## Private root

- default: `/Users/huageorge/.binaryrepair/phase8c-hidden`
- override: `PHASE8C_HIDDEN_ROOT`
- create with mode `0700`; parent `$HOME/.binaryrepair` may exist but the hidden root itself must be owner-only
- observed: exists=True, permissions=0o700, env_set=False, hidden_corpus_read=False
- no hidden bytes are committed to the public repository or copied into public artifacts

## Threat model (operational isolation, not cryptography)

1. Same-UID and root processes can read the private root. The design does not claim cryptographic secrecy; it prevents accidental public leakage and untrusted CI/fork access.
2. Leak surfaces to control: logs, exception messages, temp files, runner artifacts, CI artifact uploads, environment dumps, public manifest/evidence refs, shell history and crash reports.
3. Public outputs must be aggregate-only: aggregate counts/rates and confidence intervals; never hidden sample ids, bytes, per-sample hashes or per-sample failure text.
4. CI isolation: hidden jobs run only on a trusted/self-hosted or protected runner with the root mounted read-only; fork PRs and untrusted workflows never receive secrets or the root; artifacts are sanitized by an allowlist of aggregate fields.
5. Temp/host isolation: hidden work uses an owner-only temp root, sanitizes environment variables and removes temp files; errors are generic and contain no hidden identifiers.

## Commitment format (proposal)

- canonical hidden manifest: sample_id_hmac, binary_sha256, split, vulnerability class, oracle evidence refs, expected outcome kind
- `hidden_commitment_sha256 = SHA-256(domain || canonical_manifest || campaign_salt)`; salt is not published before the campaign
- public pre-commitment: commitment hash + campaign id + aggregate policy only
- after the campaign: reveal aggregate metrics and (only if the Lead approves) the salt; hidden bytes/sample ids stay private
- v1 hidden fields remain `hidden_available=false`, `hidden_commitment_sha256=null` until C5/C6 produce real evidence

## Boundaries and acceptance (C11)

- permission test (0700), env-override test, absence => not_run
- leak tests for logs/errors/temp/report/CI artifacts
- aggregate-only publication test (no hidden ids/bytes)
- commitment tamper/verify test
- C1 records no hidden run and no hidden capability claim
