# 132 — the M4 handoff, packed the way the earlier packages were

- Date: 2026-11-06 (15:20–15:33 local)
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput` at `86b6e36`
- Package: `dist/M3-132-m4-handoff-package-2026-11-06.zip`
  — 50,091 B, 21 entries, top-level sha256
  `bd938c672c0f6ee563c17ffb9ead35f794ab751eaa15502a2baac17cb3b7c268`
- Gate status assigned here: **none**. No `verified_by` anywhere.
- Number: 132, not 131 — M1's `131-v3-count-source-2026-11-06.md` was written first
  (15:21 against this file's 15:23). Record numbers are taken, not raced.

## 1. What "packed" means here

Same shape as 120, 121 and 124, because a consumer should not have to learn a new
layout per delivery:

```
M3-132-m4-handoff-package-2026-11-06/
  INDEX.md                                  what it is, how to verify, what it does not claim
  130-m4-v4-handoff-2026-11-06.md           the record that built the payload
  handoff/M4-v4-handoff-2026-11-06/         13 files — the runnable package
  evidence/m4-handoff-2026-11-06/           5 files — the transcripts
  SHA256SUMS                                20 rows
```

`INDEX.md` carries the content table, the three verification commands, the access
facts and the exclusions, so the archive explains itself without the reader
needing this record.

## 2. The rules that were applied, and why each one

**The archive hash lives outside the archive.** `dist/M3-132-….zip.sha256` holds
`<hash>  <filename>`, verified with `sha256sum -c`. A manifest inside the zip
cannot contain the zip's digest, so the top-level hash is delivered beside it —
the same reason the transcripts are not inside the payload.

**Three hash layers, each checkable on its own.** Outer `SHA256SUMS` (20 rows)
over everything; the handoff's own `SHA256SUMS` (12 rows); the evidence's own
`SHA256SUMS` (3 rows). A verifier who only wants the payload never has to trust
the outer list, and vice versa.

**The private key is not in the package.** `dist/m4verify_id_ed25519` sits beside
the archive, is excluded by `.gitignore`, and appears in no manifest here.
Shipping a secret inside a hash-manifested archive breaks the manifest's purpose
(every copy is now a copy of the key) as well as the key's.

**The contract and the fixture were not touched.** This delivery adds files; it
does not edit `fixtures/public/CWE416_…_noinput/`, whose `contract.json` is still
`8a2b408c…e3c3b` with `schema_version: 3`, `input_mode: none`.

**No gate, no `verified_by`, one sample.** Recorded in the record, the INDEX and
the handoff README, because a package that is quiet about its boundaries invites
someone to read more into it than it contains.

## 3. Verification, in the order a consumer would do it

Host side, from the archive itself:

```
$ cd dist && sha256sum -c M3-132-m4-handoff-package-2026-11-06.zip.sha256
  M3-132-m4-handoff-package-2026-11-06.zip: OK

$ extract, then
  outer:    20/20
  handoff:  12/12
  evidence: 3/3
  handoff/ identical to M4-v4-handoff-2026-11-06/ in the repository
  evidence/ identical to docs/handoffs/evidence/m4-handoff-2026-11-06/
```

Guest side, as `m4verify`, from the archive as it shipped — this is the part that
proves the packaged bytes execute rather than merely hash-match:

```
$ python3 -c 'zipfile.ZipFile("/tmp/arc132/pkg.zip").extractall("/tmp/arc132")'
extracted
outer: 20/20
handoff: 12/12
== sh verify_all.sh ==
=== 1/3  file integrity ===   PASS: 12 files match SHA256SUMS
=== 2/3  environment self-check ===   identical: 18/18 checks, same engine block
                                      PASS: this machine matches the recorded environment
=== 3/3  end-to-end rerun ===         byte-identical
                                      PASS: the harness reproduces the recorded output
ALL PASS: 3/3 steps
EXIT=0
```

The transcript above is quoted here rather than shipped inside the archive: it
describes the archive, so putting it in would change the bytes it describes.
`evidence/…/02-clean-run.txt` inside the package is the equivalent run of the
payload from the repository copy, and it is hashed there.

## 4. What is inside, by count

| part | files | rows in its `SHA256SUMS` |
|---|---|---|
| `INDEX.md` | 1 | — |
| record 130 | 1 | — |
| `handoff/M4-v4-handoff-2026-11-06/` | 13 | 12 (excludes `SHA256SUMS` itself) |
| `evidence/m4-handoff-2026-11-06/` | 5 | 3 (excludes `SHA256SUMS` and `bundle-sha256.txt`) |
| `SHA256SUMS` | 1 | 20 rows total |
| **zip entries** | **21** | |

## 5. What the payload can and cannot tell you

It answers two questions: *is this the recorded environment* (`run_selfcheck.sh`,
18 checks, exits 0/1/2) and *does the producer reproduce the recorded output*
(`run_e2e.sh`, `cmp`, byte-identical). What it does not answer is whether the
evidence is worth a pass — that is M4's replay, and the field it would fill in is
absent here on purpose.

Standing boundaries, unchanged: V4 `not_run` in the 124 bundle; no second defect
class, so T8.3 remains blocked; `claimed_scope: model`, with the candidate's
`unsat` disclosed as an empty disjunction in `not_claimed`.

One carried defect: `handoff/…/inputs/v4_harness.py` still claims it writes only
through `write_v4_evidence`, which stopped being true in 128. The docstring is
left as is because its sha256 is what records 128 and 129 vouch for; the INDEX
says which part to trust.

## 6. Reproduce the package

```sh
mkdir -p pkg/M3-132-m4-handoff-package-2026-11-06/{handoff,evidence}
cp docs/handoffs/130-m4-v4-handoff-2026-11-06.md pkg/M3-132-…/
cp -r M4-v4-handoff-2026-11-06 pkg/M3-132-…/handoff/
cp -r docs/handoffs/evidence/m4-handoff-2026-11-06 pkg/M3-132-…/evidence/
# write INDEX.md, then take the sums in sorted order and zip from the parent
find . -type f | sort | xargs sha256sum > SHA256SUMS
```

The one thing that must not be skipped: `find | sort` before hashing. An
unordered `xargs` produces a manifest that fails on a machine with a different
directory order, and it will look like a corrupted archive.
