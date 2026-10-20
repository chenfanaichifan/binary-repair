# fixtures/public — public sample directory

Allowed:

- Test samples compiled or built by the team.
- Public CTF / teaching / previously disclosed CVE historical binaries.
- Provenance for each sample: source, build method, SHA-256.

Forbidden:

- Client-provided binaries or any confidential derived content.
- Unauthorized third-party binaries.

Convention: real sample files may be large; confirm with the team whether to use Git LFS before committing.
Record source and hashes in `PROVENANCE.md` in this directory (template to be provided by Member 3).
