# Evidence for the M4 handoff

Two files, both produced on 2026-11-06 by running the delivered package:

| file | what it shows |
|---|---|
| `01-access.txt` | the `m4verify` account exists, is reachable over VMnet8 IPv4, has no privilege, is key-only, and can run the V4 interpreter |
| `02-clean-run.txt` | the package was extracted into an empty `/tmp/m4-clean-*` directory as `m4verify`, and `run_selfcheck.sh`, `run_e2e.sh` and `verify_all.sh` all exited 0 there |

The package itself is `M4-v4-handoff-2026-11-06/` at the repository root, with
`SHA256SUMS` covering its 12 files; the zip next to it in `dist/` is a convenience
copy and has its own `.sha256`.

These transcripts live outside the package on purpose. A transcript of checking
a tree cannot state the hash of the sums that cover it — the file would have to
contain its own digest. Keeping the evidence one level up means `SHA256SUMS`
inside the package stays a plain, verifiable list.

What these transcripts do **not** show: any gate verdict. V4 is still `not_run`
in the 124 bundle, no `verified_by` value exists anywhere, and CWE416 no-input
remains the only sample, so T8.3 stays blocked.
