# 136 — M5 key installed, environment delivered, CWE122's recipe made reproducible

- Date: 2026-11-06 (16:51–17:15 local)
- Owner: Member 3 (guest execution / evidence)
- Number: 136, not 135 — M1's `135-correction-second-class-cwe416-2026-11-06.md`
  took that number while this record was being written. Same rule as 132/133:
  numbers are taken, not raced.
- Branches: `m3/cwe416-v3-noinput` (this record), `m3/cwe122-fixture-build`
  (the fixture change, `f25db07`)
- Gate status assigned here: **none**. No `verified_by`, V4 still `not_run`,
  T8.3 still blocked.

## 1. M5's key, and what it is not

Installed into `~m4verify/.ssh/authorized_keys` with `guest/add-m4-key.sh`:

```
ssh-ed25519 …KajmbR7C2qAdg5pqNehYRRtWBfFEmEDHaBeBhzs/bJI  m5-v4-access-2026-11-06
SHA256:JF1hZZdGsxmEUt0REdbg4X76LCbaA/1q+0IYObh3zgI
```

The private key never touched this host — `/tmp/m5-v4-access/id_ed25519` is on
M5's machine, and nothing in the repository, the packages or this record contains
it. The account still has no password and no sudo.

**What this key is for:** collaboration — reading the handoff, running the
checks, arguing about the evidence. **What it is not:** M4's replay identity.
`authorized_keys` now holds M5's key and only M5's key; when M4's public key
arrives it is added alongside, not replaced. A run by whoever holds the M5 key is
not an M4 replay, and no amount of "it's the same account" changes that.

I could not test M5's login from here — the private half is theirs — so what is
verified is the mechanism (a throwaway key installed by the same script logged in
as `m4verify` and was removed) and the line's fingerprint, which matches the one
M5 published.

## 2. The environment, delivered where M4 can read it

M4's key is still outstanding, so the fallback was taken: the recipe and its
evidence are now readable without logging in.

```
/opt/binrepair-handoff/                      root-owned, a+rX
  M4-v4-handoff-2026-11-06/                  run_selfcheck.sh, run_e2e.sh, verify_all.sh, scripts/
  T8.3-evidence-2026-11-06/                  the sample, candidate, V0–V5, V4 producer evidence
  T8.3-supplement-2026-11-06/                hooks audit, property mapping, check_mapping.py
  cwe416-v4-env-2026-11-06/                  provision_angr_venv.sh, selfcheck.py,
                                             run_selfcheck.sh, the 54 pins, 15 rows of evidence
```

Checked as `m4verify`: `sha256sum -c` 15/15 in the environment directory, and the
three entry points present. This is the "or" half of the request — M4 can rebuild
the interpreter from the recipe, or run the self-check on a machine that already
has `/opt/angr-venv`.

## 3. CWE122: the digest matched, so the pin did not move

The instruction was: add `-fno-pie -no-pie`, rebuild, and if the digest equals
`c9ddb9c2…` leave the pin alone; otherwise stop and report. It took two attempts,
and the first one is the interesting one.

**First rebuild differed.** `155f3bf6…` against the pinned `c9ddb9c2…`. Both were
EXEC (non-PIE) with the same entry point, so it was not the PIE question. Section
by section:

```
.text  .rodata  .data  .bss  .init  .fini  .plt  .eh_frame   all identical
.debug_line_str   0x13c (pinned)  vs  0x13b (rebuild)       one byte
372 bytes differ in total; two stripped copies also differ
```

Cause: `-g` records the build directory. `DW_AT_comp_dir` was `/var/tmp/cwe122`
in the pinned artefact and `/home/lab/c122` in the rebuild — one character
shorter, one byte of line-string, and then a different `.note.gnu.build-id`,
because the linker hashes the whole file.

**Second rebuild matched**, two ways:

| build | result |
|---|---|
| in `/var/tmp/cwe122` | `c9ddb9c2…` identical |
| anywhere, with `-ffile-prefix-map=$PWD=/var/tmp/cwe122` | `c9ddb9c2…` identical |

So the fix is `build.sh` gaining `-fno-pie -no-pie` **and** the prefix map, which
makes the digest independent of where the fixture is checked out. Verified from a
fresh copy at `~/c122c/CWE122_c_CWE129_fgets_01`: build → `c9ddb9c2…`, `EXEC`,
`tests/SHA256SUMS` 12/12 before and after, and the binary still runs
(`Calling bad()…`, ten lines, `Finished bad()`, exit 0).

Because the bytes did not change:

- `build.json#output.sha256` and `tests/{valid,invalid}.json#original_sha256` keep
  `c9ddb9c2…` — the pin is untouched, as instructed;
- what did change is the recipe and the two manifests that describe it:
  `build.sh` (flags plus prefix map), `build.json` (the map, the build directory,
  a note about why), `tests/SHA256SUMS` (those two rows).

**Intake:** `tools/fixture_intake.py --check … --baseline-cwe CWE-121` → `OK`, so
the sample is a distinct class from the first one.

**Not done, deliberately:** no PIE artefact was renamed into place, and the
fixture was not rebuilt to a new digest and re-pinned. The committed
`original.elf` is the same file it was; only the recipe that produces it now
agrees with the contract.

## 4. Branch state, recorded not acted on

`m3/cwe416-v3-noinput` is **97 commits ahead of `origin/main`**. Everything M4 and
M5 are being handed — fixtures, contract, candidate, packages — is invisible to
anyone reading `main`. That is the standing reason this keeps looking incomplete
from the outside.

Per instruction, **no merge before T8.3 closes**. Merging a 97-commit branch while
the sample's verdict is still open would put unreviewed evidence on `main` and
make the merge itself the story. The item is recorded here so it does not become
folklore.

## 5. One wording for "the second class"

The Lead fixed the vocabulary in `docs/fixtures.md` (section "Decided
2026-11-06"): **the second class is CWE-416**, the no-input sample frozen in
record 133, with the terms carried from record 103 (CWE-121 first class, CWE-416
second class). **CWE-122 is out** — no third class — and the
`fixtures/public/CWE122_*` `-text` rule must not reach the final line.

Three sentences M3 will use from now on, and nowhere else:

1. **The second class is CWE-416 no-input**: `mechanism: lifetime`, heap,
   `input_mode: none`, frozen in record 133 with the hashes in its gate-index.
2. **T8.3 is blocked on acceptance, not on selection.** The sample is chosen and
   evidenced; what is missing is M4's replay of V4 and the Lead's acceptance of
   the evidence.
3. **CWE-122 is not part of T8.3.** Its build recipe was fixed on
   `m3/cwe122-fixture-build` so a rebuild is not PIE-instead-of-non-PIE, and that
   branch is not proposed for the final line.

Where earlier M3 documents said "second sample" without saying which class, they
meant this one. The sealed packages (133 and the T8.3 bundle) keep their bytes and
their phrasing; this record is the interpretation they are read against, and it
supersedes nothing about their content.

## 6. Guest state, and the key that is still missing

`192.168.30.128:22` is up and listening on both stacks; `lab` reaches it, and
`~m4verify/.ssh/authorized_keys` holds exactly one line — M5's
`m5-v4-access-2026-11-06`, fingerprint `SHA256:JF1hZZdGsxmEUt0REdbg4X76LCbaA/1q+0IYObh3zgI`.

**No M4 public key has been provided yet**, so nothing was installed for M4. When
it arrives, one command adds it beside M5's line:

```sh
sudo sh /opt/binrepair-handoff/T8.3-evidence-2026-11-06/guest/add-m4-key.sh m4_id_ed25519.pub
```

Until then M4's replay cannot happen, which is the same thing as saying T8.3 stays
blocked — the two are not separate blockers.

## 7. Boundaries

- **No `verified_by`** anywhere: not in the JSON, not in the READMEs, not in the
  packages, not in this record.
- **V4 is still `not_run`.** M5's access is collaboration; the replay that moves
  V4 is M4's, with M4's own key.
- **T8.3 stays blocked.** One CWE416 sample and one CWE122 fixture in progress is
  not a family, and nothing here proposes a second class.

## 8. Open items

1. M4's public key → add it next to M5's line, never replacing it.
2. M4's replay of `v4/harness-output.json`, then its own `verified_by`.
3. CWE122 still needs the rest of its T8.3 path (contract review, candidate,
   gates) — the build recipe is now reproducible, which is only step one.
4. Branch merge, after T8.3 closes, decided by the Lead.
