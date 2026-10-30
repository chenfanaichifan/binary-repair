# P4 v3 remaining gaps (guest boot 2026-10-30)

Closed on 2026-10-30 (byte-exact, all hashed in SHA256SUMS):
- isolation.json: gate4-harness uid 11 snapshot name/created_at + chain manifest hash;
- chain-manifest.json: .vmsd + uid 4..11 layer hashes, computed powered off;
- revert-raw.log: unedited vmrun stop/revertToSnapshot stdout/stderr + exit codes (2026-10-30T19:33 +08);
- post-revert-fingerprint.txt: live in-guest fingerprint after the scripted revert (19:38);
- harness-manifest.json regenerated for uid 11: wrapper b232d60b, gate4.conf a912e6b0, runner 515c4d60, kit v6 499f510c;
- jobwrap and gate4.conf: real exported bytes (hash-bound transfer).

Still open (acceptance, not guest evidence):
- M5 adapter/replay and real p2_acceptance run; Gate 4 acceptance is NOT RUN.
- revert.log remains the 2026-10-29 manual-restore summary; revert-raw.log records the
  2026-10-30 scripted re-revert that reproduced the uid 11 environment, not the original run's restore.

No gate4_pass claim. The 2026-10-29 Gate 4 execution result (pass, 6/6 behaviour-identical)
is separate from Gate 4 acceptance.

Supersedes P4 v2 (dist/P4-package-v2-2026-10-29.zip, sha256 0e31e24544f7a78b144f5fcab46de0aaaca47ab571c69041eade7cb6e5d7c7de).
