# T30 provenance: one canonical artifact path, and the git binding for c274893

This file binds the T30 CWE-416 artifact to a repository, a branch, a commit,
and exactly one path. It travels with the record 118 evidence delivery.

## 1. Upstream case source

| Field | Value |
|---|---|
| repository | `https://github.com/dsp-testing/samate-c-cpp` |
| commit | `01e353daa3d28a4ce2ae68904cbcde5e03e3519d` |
| path | `C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c` |
| SHA-256 (as served, CRLF) | `fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e` |
| size | 3,198 bytes |

The fixture's `src.c` is the same content with LF line endings:
`262dee1d39243c944a55b4b967ab6a56524977dc88a684ff0b7150cacf0b5a61`.

## 2. The built artifact and its one canonical path

**Canonical path:**

```
docs/handoffs/evidence/T30/build/original.elf
```

| Field | Value |
|---|---|
| git remote | `git@github.com:chenfanaichifan/binary-repair.git` |
| branch | `member-3/t62-host-safe` |
| branch head at this record | `472b26ea95f8bfbc63ccaba4ef4b4233e3816d75` |
| commit holding T30 | `c274893d3cc495fd8c1cbc9e28847b565b341f7e` |
| commit subject | `feat(t30): CWE416 fixture built in the guest, with a deterministic trigger` |
| artifact SHA-256 | `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9` |
| artifact size | 25,344 bytes |

`c274893` is an **ancestor** of `origin/member-3/t62-host-safe` (head
`472b26e`), not of `integration/live-bridge-2026-11-03`. Resolve it with:

```sh
git fetch origin member-3/t62-host-safe
git cat-file -p c274893:docs/handoffs/evidence/T30/build/original.elf | sha256sum
# c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
git cat-file -s c274893:docs/handoffs/evidence/T30/build/original.elf
# 25344
```

## 3. The three non-canonical spellings, declared aliases

These appear in the historical 118 evidence and in T30's own files. None of them
is an identity path; they resolve only relative to a package root or a guest
working directory.

| Alias | Where it appears | What it really is |
|---|---|---|
| `build/original.elf` | `T30/build.json#output.file`, `T30/SHA256SUMS` | package-relative path inside the T30 directory; valid only after checkout/extraction of `docs/handoffs/evidence/T30/` |
| `T30/build/original.elf` | record 118 shorthand | shorthand for the same package-relative file; not a repository path |
| `/var/tmp/cwe416/original.elf` | `02-build.txt` guest output | ephemeral guest build output; not a repository path and not stable across runs |

A fourth string, `original.elf` (and `./original.elf` in `trigger.sh`), is the
flat ZIP member / process invocation basename, not an artifact identity. It is
not counted as a path spelling.

**Rule for new records and verifiers:** use
`docs/handoffs/evidence/T30/build/original.elf` at `c274893`. Do not use the
three aliases as identity, and do not resolve `T30/...` from a branch where
`docs/handoffs/evidence/T30/` does not exist.

The historical evidence is not rewritten to remove the aliases: `T30/SHA256SUMS`
and the 118 evidence `SHA256SUMS` hash those bytes. This file is the mapping;
the canonical path above is the identity.

## 4. Record 118 evidence package

| Field | Value |
|---|---|
| source branch | `origin/m3/cwe122-fixture-build` |
| source commit | `87f63502d0fc5679f9dd797b7adc20c2069a5d39` |
| source directory | `docs/handoffs/evidence/t30-rebuild-2026-11-05/` |
| transport zip | `dist/M3-t30-rebuild-evidence-2026-11-05.zip` on that branch |
| zip SHA-256 | `968fb8d9a80f991567c0cdd1e082a844556ef6405ee366786e2b3b7a010fcbd5` |
| zip members | 11: `00-window-host.txt`, `01`–`07`, `collect.sh`, `README.md`, `SHA256SUMS` |
| directory `SHA256SUMS` | 10/10 verified (covers 00–07, README.md, collect.sh) |
| guest `06-SHA256SUMS` | 5/5 verified (covers 01–05) |

The zip extracts to `t30-rebuild-2026-11-05/`. The 11 files in this delivery
folder are byte-identical to the source branch; they were not edited.

## 5. What changed in this delivery

- The evidence was previously absent from the M1 workspace and the repo. It is
  now delivered as a directory and as the original transport zip with its
  top-level `.sha256`.
- The canonical path is fixed to the repository path above; the three aliases
  are declared aliases, not alternate identities.
- The `c274893` git binding is written here, because record 118's `git cat-file`
  command is unusable without the branch that contains the object.

M4 has moved record 118 to **VERIFIED (rebuild evidence package)** on this
delivered evidence; the verification is scope-limited and does not re-execute
the rebuild. This file supplies the bytes and coordinates behind that record.
