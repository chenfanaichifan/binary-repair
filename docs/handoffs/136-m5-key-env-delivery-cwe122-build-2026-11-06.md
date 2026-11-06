# 136 — M5 key installed, environment delivered, CWE122's recipe made reproducible

- Date: 2026-11-06 (16:51–17:15 local)
- Owner: Member 3 (guest execution / evidence)
- Number: 136, not 135 — M1's `135-correction-second-class-cwe416-2026-11-06.md`
  took that number while this record was being written. Same rule as 132/133:
  numbers are taken, not raced.
- Branches: `m3/cwe416-v3-noinput` (this record), `m3/cwe122-fixture-build`
  (the fixture change, `f25db07` → rebased to `79cd4f9`; see §9)
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

## 6. Guest state, and the two keys on the account

M4's key arrived as text in this window and is now installed beside M5's:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBFmDHmwn/0KeulZ32w97zmV2jP+p7kGMdWew2rZnbdq  m4-guest-replay-2026-11-06
file sha256  ab8fbd7dc23bf900dc1597da8025a689feed55f77275c87869e55fa4dca5a703
fingerprint  SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q
```

| | |
|---|---|
| `authorized_keys` | mode **600**, owner **m4verify:m4verify**, `.ssh` at **700** |
| keys present | **2** — M5 `JF1hZZdG…` first, M4 `bRq28b6J…` second |
| M5's line | unchanged: same fingerprint, same position. Nothing was replaced |
| idempotent | a second run prints `already present` and the count stays 2 |
| sshd | `0.0.0.0:22` and `[::]:22`; `pubkeyauthentication yes`, `passwordauthentication no`, `strictmodes yes` |
| account | uid 1004, own group, no sudo, password locked (`L`) |

Evidence, with both sides' digests and the full acceptance run:
`docs/handoffs/evidence/m4-key-install-2026-11-06/`.

### The correction this window owes

Records 135 and 136 both said M4's key "was not on this host". That conclusion came
from searching the working tree, `D://` to depth three, `/tmp`, the home directory,
Desktop and Downloads, and from fingerprinting every `*.pub` on disk. The request
then named the missing step: the key is on a separate branch,
`delivery/t83-2026-11-06` (root `f46c626c`, key commit `df99853b`), which no
checkout here contains. `git fetch origin delivery/t83-2026-11-06` was the command
those two windows did not run.

**This window did not verify that either**, and says so rather than inheriting the
claim. The fetch was attempted five more times and failed every time with the same
transport fault as the rest of the afternoon; `git cat-file -t` on both commit ids
still returns `could not get object info`, because without the branch there is
nothing to read. So the installed key is byte-identical to the **text and the two
digests supplied with the request**, which is a weaker statement than "identical to
what the branch holds" — and it is the one the evidence directory makes. When the
transport recovers, `git show origin/delivery/t83-2026-11-06:m4_guest_key.pub`
should produce the same 108 bytes; if it does not, the evidence directory is wrong
and the key has to be replaced.

What this unlocks and what it does not: M4 can now authenticate, which was the only
client-side blocker. It does not make M4's replay happen, and it is not a replay.
`V4` stays `not_run` until M4 runs the harness and writes its own `verified_by`.

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

## 9. The 502 was hiding a non-fast-forward

`m3/cwe122-fixture-build` refused to push four times with
`CONNECT tunnel failed, response 502`, and that was read as "the network is
down, try later". When the tunnel came back the same push failed in a different
way:

```
! [rejected]  m3/cwe122-fixture-build -> m3/cwe122-fixture-build (non-fast-forward)
```

So there were two separate facts stacked on top of each other, and the transport
error was masking the second one:

```
local  f25db07   (1 commit: the CWE122 build fix)
remote 52ffecd   (10 commits ahead of the common base, incl. M1's
                  "record 1b08ae5 as the M3 intake base")
base   6ce16ac6
```

The branch had been cut before those 10 commits landed, so this was a rebase,
not a retry. Only `tools/fixture_intake.py` changed on the remote side and only
the three CWE122 files changed on this side — no overlap, so the rebase applied
cleanly and dropped nothing:

```
f25db07  ->  79cd4f9   build.json  +6/-1, build.sh +15/-1, tests/SHA256SUMS +2/-2
              (rebased onto 52ffecd; the three changed files are byte-identical)
```

The lesson is the one worth keeping: **"502" describes the transport, not the
state of the branch.** A retry loop that only counts HTTP failures would have
reported "network flaky" forever; the push had to reach the server to learn it
was being rejected for a reason that had nothing to do with the network.

Nothing about the fixture's content changed in the rebase — the digest is still
`c9ddb9c2…`, `output.sha256` and `tests/*.json#original_sha256` still hold it,
and the pin did not move for a second time.

## 10. Push state, corrected

The status block this window was given says `3e2c108: 未推送，远端仍 2533780`. That
is no longer true: `3e2c108` was pushed at 17:47 during a brief window, and the
push printed

```
To https://github.com/chenfanaichifan/binary-repair.git
   2533780..3e2c108  m3/cwe416-v3-noinput -> m3/cwe416-v3-noinput
```

A caveat that belongs next to it: `git ls-remote` fails again as of 18:05, so the
remote cannot be read right now to re-confirm. The claim rests on that push's own
output, not on a fresh read.

`m3/cwe122-fixture-build` is the branch that is still outstanding, at `79cd4f9`
after the rebase in §9. A background loop is retrying it every ten seconds and will
stop as soon as `ls-remote` agrees with local. Two branches, two different reasons:
one is behind the network, the other was behind the network *and* behind a rebase
that the network error was hiding.
