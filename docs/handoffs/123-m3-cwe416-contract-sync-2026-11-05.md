# 123 — the tree owns the CWE416 contract: 8a2b408c file / c1684f15 canonical

- Date: 2026-11-05 (guest window 23:38–23:41 local)
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput`, on top of `5b186cb`; records 121 → 122 → this
- Evidence: `docs/handoffs/evidence/cwe416-contract-sync-2026-11-05/`
  (`SHA256SUMS` `725e1914…c757`, 10 rows / 12 files)
- `fixtures/` **unchanged** by this pass — `git diff 584b912 HEAD -- fixtures` is
  still empty
- Not claimed: any gate pass, Gate 4, T8.3 relief, binary-level V4, a second
  defect class

## 0. Status at a glance

| Item | State |
|---|---|
| Tree contract file hash | `8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b` |
| Tree contract canonical hash | `c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c` |
| Schema / mode | `schema_version: 3`, `input_mode: "none"`, 13 fields, no v2 field |
| 120 package's fixture copy | the same 14 filenames; `contract.json` byte-identical |
| `_m3-run`, `_m1-work/m3` | do not exist — nothing to delete or replace |
| `V3-no-input-2026-11-05/contract.json` | does not exist here; not touched |
| V3 on the candidate | `1/1`, `passed=1 total=1`, `invalid: not_applicable` |
| V3 on the unrepaired original | `0/1`, exit 1 |
| V4 | `not_run`, `claimed_scope: null` |
| V5 | `c9c2632e…` twice, `46d16e99…` twice |
| T8.3 | blocked |

## 1. The contract was already the tree's version

The request was to sync 120's fixture over the tree and replace an old v2
contract. Checked first, and the tree's `contract.json` is v3 no-input at
`8a2b408c…` — the same bytes as the copy inside the 120 package. So there was no
v2 file in `fixtures/public/CWE416_…_noinput/` to overwrite, and overwriting it
with the identical bytes would have been a no-op that looked like work.

Both hashes are reported because both get quoted, and they are different
questions:

```
file      sha256(1654 bytes of pretty-printed json)       = 8a2b408c…e3c3b
canonical sha256(compact, keys sorted, list fields sorted) = c1684f15…b4f7c
```

The canonical form is `SecurityContract.canonical_json()` — that is the value
`contract_sha256` and the reviewed-scope hash use, so reformatting the file moves
one and not the other. `01-contract-identity.txt` prints both from the tree path,
plus the field list and a check that none of the five v2-only fields is present.

## 2. A blanket overwrite would have undone 121

Twelve of the fourteen fixture files are byte-identical between the 120 package
and the tree. The two that are not:

```
defect.json        aff4afba4b69 (120)   1016ffd6c53f (tree)
tests/SHA256SUMS   1e574f9aab93 (120)   6df0a0635b14 (tree)
```

Those are exactly the files record 121 changed on purpose after 120 was packed:
`trigger_note` was rewritten to start with `not_applicable: input_mode is none …`
because the old wording read like a missing case and invited an invalid-first
reading. Copying 120's copies back would restore that wording.

So the contract was verified, not overwritten, and the two later files were left
alone. 120 is a snapshot; the tree is the later state. `02-fixture-vs-120.txt`
carries the full per-file table so the judgement can be re-checked instead of
trusted — and it says so in the file, not only here.

## 3. The cleanup targets do not exist

`_m3-run` and `_m1-work/m3` were searched four ways and are absent on all four:
`ls` in the repo root, `find /d -maxdepth 6`, `find / -maxdepth 6` in the guest
over ssh, and `git ls-files`. There was nothing inside them.

The inventory in `04-contract-inventory.txt` does find one v2 CWE416 contract:
`.tmp/cwe416-build/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/contract.json`
(`7b61bdd1…`). It is scratch, it belongs to the retired synthetic fixture (no
`_noinput`), and no package carries it — the 120 and 121 zips each hold only the
v3 contract. It was left in place: it is the last surviving contract of a
retired fixture, and deleting it removes history for a path nothing reads. If
the aim is that no v2 file can be globbed anywhere, renaming it to
`contract.v2-retired.json` is the smaller move — one line, and the request did
not ask for it by name, so it is offered rather than done.

The `V3-no-input-2026-11-05` demo does not exist on this host either, so nothing
was written near it. It is a demo, not a CWE416 fixture; it stays untouched
whichever machine it lives on.

## 4. V3 re-run from the tree, in a new guest directory

The kit was packed from the tree and unpacked into `~/cwe416-sync`, a directory
that did not exist before this window, so nothing from the 122 run could leak in.
Same candidate (`46d16e99…`), same `valid.json`, same runner:

```
input_mode: none   invalid: not_applicable   valid: 1/1
passed: 1   total: 1   repaired_pass: true   (exit 0)
```

Control on the unrepaired original, same runner and manifest:

```
valid: 0/1   passed: 0   total: 1   repaired_pass: false   (exit 1)
stdout_hex: 6937030a
```

One detail worth keeping: the 122 control printed `4ba2020a`, this one
`6937030a`. Both are tcache residue and neither is the 100-byte block, which is
why the fixture freezes its observation under `setarch -R`. It also means the
control's failure must not be described as "it printed the wrong constant" — it
printed different residue, twice, and failed both times for the same reason.

## 5. V4 stays not_run, and the reason is not "no engine"

angr 10.0.4.post1 and z3 5.1.0 are installed in `/opt/angr-venv` on the guest
(z3 is simply not on PATH). So a symbolic run was possible and was not
performed. `05-v4-not-run.json` records the engine, the absence of a run, and
why: a real V4 needs per-run solver accounting (sat/unsat/unknown/eval) and a
bound that cannot hide a timeout behind "proven"; the earlier V4 submissions
were rejected for concrete `'A'`-byte inputs and silent `max_steps`
(`docs/handoffs/63`, `64`, `66`, `67`). An ad-hoc query would be a claim with
nothing behind it, which is worse than `not_run`. `claimed_scope` is `null`.

V5 measured again in this window, from the tree fixture:

```
SUPPORT=<fixture>/support sh build.sh   ->  c9c2632e…23c9  (twice)
patch_candidate.py --original <that>    ->  46d16e99…fcd0  (twice)
```

## 6. What still does not move

`required_obligations` still lists `symbolic`. An attempt assembled from the 122
bundle therefore remains `REQUIRED_CHECK_NOT_RUN` → `inconclusive`; running the
V3 runner a second time does not change that, and this record does not either.
It is a contract-owner decision: either the obligation is satisfied by a real
model with accounting, or it is removed from the contract on purpose.

T8.3 stays blocked. One sample, one repair, one observation. No second defect
class is described here and none is implied by `1/1`.

## 7. Checking it without trusting this record

```sh
cd docs/handoffs/evidence/cwe416-contract-sync-2026-11-05
sha256sum -c SHA256SUMS                 # 10 rows, all OK
sha256sum SHA256SUMS                    # 725e1914…c757
cat bundle-sha256.txt                   # same value, kept outside the listing
sha256sum run_sync.sh                   # the script that produced 03-*
```

`SHA256SUMS` covers every file except itself and `bundle-sha256.txt`;
`bundle-sha256.txt` is `sha256(SHA256SUMS)`, so the package can be checked from
outside without the listing hashing itself.
