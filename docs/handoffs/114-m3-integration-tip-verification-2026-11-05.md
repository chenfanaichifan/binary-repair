# 114 — Integration tip verified from the M3 side; one contract defect found

**Owner:** M3 · **Date:** 2026-11-05 · **Status:** the integration report is
confirmed on every point I can measure, **except** that the CWE416 and CWE122
`contract.json` files both fail the domain model the pipeline approves them
with. T8.3 stays **blocked**. No RTL, no merge, no tag, no live success.

Follows `112` (support files) and `113` (CWE416 contract gap). Everything below
was measured against `origin/integration/live-bridge-2026-11-03`, not against a
working tree of mine.

## 1. Confirmed

| Claim | How checked | Result |
|---|---|---|
| `ddd3869` was the pre-push base | `git merge-base --is-ancestor ddd3869 965b868` | **ancestor: yes** |
| `4292da0` and `de4c63d` are ancestors, docs not lost | `--is-ancestor 4292da0 965b868` | **ancestor: yes** |
| `fba137e` reverted | `9d59e72` reverts it; `src.c`/`harness.c` absent at tip | **confirmed** |
| CWE121 intake returns 4 findings, exit 1 | `fixture_intake.py --check` | `src.c`, `build.sh`, `build.json`, `defect.json` → **4, exit 1** |
| CWE416 intake returns exactly 1 finding | same | `original.elf` only → **1, exit 1** |
| CWE416 ships 10 files, `tests/SHA256SUMS` covers all | re-hashed each entry | **9/9 entries, 0 mismatch, no uncovered file** |
| CWE122 `src.c` is verbatim SARD, not reconstructed | compared to the 152,957,342 B archive | **`082045a2…46a0`, byte-identical, 5,206 B** |
| CWE416 declares itself synthetic | `PROVENANCE.md` | **declared, with the 422 reason stated** |
| CWE122 intake returns 2 findings | `fixture_intake.py --check` | `original.elf`, `tests/SHA256SUMS` → **2, exit 1** |

The CWE122 byte check is the strongest of these: I hashed the file out of the
archive, out of the commit and against `defect.json#source.sha256`, and all
three agree. That is a real upstream sample, unlike the CWE416 fixture.

## 2. Where the tip actually is

The report says the tip is `965b868`. The branch is five commits past it:

```text
2a424be  docs(canonical): fix one head and record the remote SHA
165891d  feat(ai-usage): pass partial through instead of dropping it
147721d  docs(integration): pin the reproducible anchor and close the 8c77fcd probe
4997443  fix(fixtures): store the SARD case as bytes, not as text
03e3b11  feat(fixtures): scaffold the CWE-122 second class from SARD 112
965b868  feat(intake): land the bug-site check and complete the task-30 fixture
```

This is not a discrepancy about what was said, only about what is now on the
branch: `03e3b11` and `4997443` land a **second** fixture after the message was
written, and `108-m3-cwe122-build-request.md` is addressed to me. I read it as
the current work item rather than `965b868`.

## 3. The defect: neither new contract can be loaded

`contract.json` for CWE416 and CWE122 is shaped like a description of the
sample. `SecurityContract` is shaped like a description of an *input-boundary
rejection*. They are not the same shape, and the gap is not caught by intake.

Measured with the exact entry point `scripts/demo_e2e.py:229` uses to compute
the approved scope hash:

```text
CWE121_src_char_declare_cpy_51b          scope sha256 24bfe568e162be57   OK
CWE416_Use_After_Free__malloc_free_char_01
    ValueError: unknown contract fields: ['invalid_behavior', 'max_input_bytes']
CWE122_c_CWE129_fgets_01
    ValueError: missing contract fields: ['allowed_calls']
```

CWE416 is missing all four of `invalid_input_response`, `invalid_stdout`,
`invalid_stderr`, `max_valid_input_bytes`, and adds two keys that are not model
fields. CWE122 has 16 of 17 required keys and omits `allowed_calls`.

`SecurityContract.from_dict` (`app/domain/contracts.py:240`) rejects unknown
keys before it rejects missing ones, which is why CWE416 reports the two extras
and hides the four gaps in one message.

### Why intake does not catch it

`tools/fixture_intake.py:317` `_check_contract` asserts that `schema_version`,
`required_obligations`, `forbidden_behavior` and `valid_domain` exist, that the
obligation set is complete, and that two strings are non-empty. It never builds
a `SecurityContract`. So:

```text
FAILED (1 finding(s))
missing_file  original.elf  required for intake
```

is an accurate statement about **files** and says nothing about whether the
contract can be approved. An unbuilt fixture and an unapprovable fixture print
the same line.

That is the honest version of "content-complete but unbuilt": it is true of the
directory listing, not of the contract.

### What I did not do

I did not edit either `contract.json`. `108` says "Do not edit … contract.json
… If something there is wrong, report it; do not patch it here", and the same
holds for CWE416, which M1 wrote. Patching the body here would also change the
bytes that `tests/SHA256SUMS` binds, turning a report into an unaudited edit.

## 4. Two notes on the CWE-122 build, before anyone burns a guest window

Both are things I can see in the recipe and cannot settle without a compiler.
Per `108` these are exactly the "stop and report" conditions.

1. **`build.sh` does not pin `-no-pie`, but `108` expects `EXEC (non-PIE)`.**
   `gcc -O0 -g -DINCLUDEMAIN -DOMITGOOD` on Ubuntu 24.04 (gcc 13.3, the version
   `build.json` claims) defaults to PIE, so `readelf -h` is likely to report
   `Type: DYN`, not `EXEC`. Either the recipe or the expectation has to move;
   which one is a fixture decision, not mine.
2. **`build.sh` does not pin `-fno-stack-protector`,** while `108` forbids
   adding `-fstack-protector`. On the same toolchain the default is
   `-fstack-protector-strong`, so "the plain build" is not what the two
   directives together produce.

I will measure both on the guest and report what `readelf` actually prints
rather than picking the answer that matches the brief.

## 5. T8.3: the carrier changed, the block did not

`113` argued the second class should be an input-boundary defect, and listed
CWE122 as the cheapest option. That is now the committed direction, and it is
better provenance than CWE416: CWE122 is byte-identical SARD, CWE416 is
self-declared synthetic.

So the two fixtures are not equivalent:

| | CWE416 `malloc_free_char_01` | CWE122 `c_CWE129_fgets_01` |
|---|---|---|
| origin | synthetic, written here | verbatim SARD 112 |
| can carry a *public sample* obligation | **no** | **yes** |
| useful for | trigger stability, `--uaf` observation technique | the T8.3 second class |
| `bug_site` | heap | heap, `cwe_parent: CWE-787` |

One line in CWE416's `PROVENANCE.md` says "T8.3 needs a second class and this
fixture is it". Everything else in that file is careful, and that sentence
undercuts it: a self-declared synthetic sample cannot carry the public-sample
obligation, which is the whole reason T8.3 is blocked. I would strike the
sentence, not the fixture — the fixture is a good trigger-stability probe.

T8.3 therefore stays blocked, now for one reason instead of four: CWE122 has no
`original.elf`, so nothing has been measured, so there is nothing to verify.

## 6. Not verified

- **`412 passed / 3 skipped`.** This environment has no pytest (`pytest` is not
  installed for the interpreter on PATH, and there is no venv in the tree), so I
  neither confirm nor dispute the number. It is your measurement, not mine.
- **The CWE416 `--uaf` sentinel behaviour.** `PROVENANCE.md` is explicit that
  the `'X'` bytes depend on glibc tcache reuse and are not a language
  guarantee. Until `original.elf` exists, the six `expected` blocks are stated
  intentions, not observations.
- **Anything requiring the guest.** No `gcc` on this host, `AGENTS.md` forbids
  compiling here, and the guest window is not open.

## 7. One correction to my own earlier reading

While checking byte stability I first concluded CWE416 was exposed to the
CRLF-normalisation defect that `4997443` fixed for CWE122: a checkout without
`.gitattributes` in the worktree produced `src.c` at `bc241470…` instead of the
recorded `9a909296…`. Re-running with the tree fully checked out — so the
committed `.gitattributes` actually applies — gives `eol=lf` for CWE416 and
`text: unset` for CWE122, and **9/9 sums match for CWE416, `082045a2…` for
CWE122**. The first result was an artefact of my test, not a defect in the
branch. Recorded because a withdrawn finding is worth as much as a kept one,
and this one is easy to reproduce the wrong way.
