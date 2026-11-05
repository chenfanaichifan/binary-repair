# CWE416 no-input — the tree fixture is the contract the runner reads

- Date: 2026-11-05 (guest window 23:38–23:41 local)
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput`, on top of `5b186cb`; records 121 → 122 → this
- Question this pass answers: does the contract in the **formal tree** drive V3,
  or is a staging copy still doing it?

## 0. What was found, in one table

| Check | Result |
|---|---|
| Tree contract file hash | `8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b` |
| Tree contract canonical hash (through `SecurityContract.sha256()`) | `c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c` |
| Schema / mode | `schema_version: 3`, `input_mode: "none"`, 13 fields |
| Any v2 field left in it | none of the five |
| Same bytes as the 120 package's fixture copy | yes, byte-identical |
| `_m3-run`, `_m1-work/m3` | do not exist on this host, on the guest, or as a tracked path |
| `V3-no-input-2026-11-05/contract.json` | does not exist on this host; not touched |
| V3 on the candidate | `1/1`, `passed=1 total=1`, `invalid: not_applicable` |
| V3 on the unrepaired original | `0/1`, `repaired_pass: false`, runner exit 1 |
| V4 | `not_run`, `claimed_scope: null` |
| V5 | rebuild `c9c2632e…` twice; patch `46d16e99…` twice |
| T8.3 | blocked |

Nothing in `fixtures/` changed in this pass. The tree already carried the v3
contract; the work was to prove that, not to write it again.

## 1. The two hashes, and why there are two

`contract.json` is 1,654 bytes of pretty-printed JSON. `SecurityContract`
serialises a canonical form instead — sorted keys, sorted list fields, no
whitespace — so the reviewed-scope hash does not move when someone reformats
the file. Both are reported because both get quoted, and they must not be
confused:

```
file      sha256(b"<the 1654 bytes>")                    = 8a2b408c…e3c3b
canonical sha256(compact sorted json, list fields sorted) = c1684f15…b4f7c
```

`01-contract-identity.txt` is the run that produced both, including the field
list and a check that none of `invalid_input_response`, `invalid_exit_code`,
`invalid_stdout`, `invalid_stderr`, `max_valid_input_bytes` is present.

## 2. Syncing 120's fixture would have undone 121

The 120 package's fixture and the tree fixture have the same 14 filenames, and
12 of them are byte-identical — **including `contract.json`**, which is why the
sync this pass was asked for is already true. The two that differ are
`defect.json` and `tests/SHA256SUMS`:

```
defect.json        aff4afba4b69 (120)   1016ffd6c53f (tree)
tests/SHA256SUMS   1e574f9aab93 (120)   6df0a0635b14 (tree)
```

Those are the files record 121 changed on purpose after 120 was built: the
`trigger_note` now starts with `not_applicable: input_mode is none …`, because
the old wording read like a missing case and invited an invalid-first reading.
Copying 120's copies over the tree would put that wording back.

So the contract was checked and left as it is, and the two later files were left
as they are. 120 is a snapshot; the tree is the later state. `02-fixture-vs-120.txt`
has the full per-file table so the choice can be re-checked rather than trusted.

## 3. The directories named for cleanup do not exist

`_m3-run` and `_m1-work/m3` are not on this host (`ls`, `find /d -maxdepth 6`),
not in the guest (`find / -maxdepth 6` over ssh), and not tracked (`git ls-files`).
There was nothing inside them to delete or replace. `04-contract-inventory.txt`
records the searches verbatim rather than asserting the outcome.

What the inventory does find:

- the **only** v2 CWE416 contract on this host is
  `.tmp/cwe416-build/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/contract.json`
  — scratch, and it belongs to the retired synthetic fixture (no `_noinput`);
- no package contains it: the 120 and 121 zips each carry only the v3 no-input
  contract, at `8a2b408c…`;
- the guest's only copy, in `~/cwe416-cand/kit`, is v3 at `8a2b408c…`.

That scratch copy was left in place. It is the last surviving contract of a
retired fixture — removing it deletes history for a path nothing reads, and if
the aim is broader (no v2 file can be picked up by a glob anywhere), renaming it
to `contract.v2-retired.json` is the smaller move. Either is a one-line change
and neither is silently done here.

## 4. V3, from the tree tarball, not from the staging copy

The kit for this window was packed from the tree (`tar` of `fixtures/…/_noinput`
plus `routeb/run_manifest_repaired.py`, `routeb/contract_mode.py`,
`app/domain/contracts.py`) and unpacked in a **new** guest directory,
`~/cwe416-sync`, so the run cannot inherit anything from the 122 window.

```
input_mode: none   invalid: not_applicable   valid: 1/1
passed: 1   total: 1   repaired_pass: true   (runner exit 0)
```

Control, same runner and same `valid.json`, on the unrepaired original:

```
valid: 0/1   passed: 0   total: 1   repaired_pass: false   (runner exit 1)
stdout_hex: 6937030a
```

Note the residue: the 122 control printed `4ba2020a`, this one `6937030a`. Both
are tcache residue and neither is the 100-byte block — which is exactly why the
fixture freezes its observation under `setarch -R` and why the control's failure
must not be read as "it printed the wrong constant". The candidate, by contrast,
prints the same 100 bytes every run.

## 5. V4 and V5

V4 stays `not_run`, and the honest reason is in `05-v4-not-run.json`: angr
10.0.4 + z3 5.1.0 **are** installed (`/opt/angr-venv`). So this is not "no engine
available" — no symbolic run was performed, because a real V4 needs a harness
with per-run solver accounting and a bound that cannot hide a timeout behind
"proven", and the earlier V4 submissions were rejected for exactly that
(`docs/handoffs/63`, `64`, `66`, `67`). An ad-hoc query would be a claim with
nothing behind it. `claimed_scope` is `null`.

V5, measured again in this window from the tree fixture:

```
SUPPORT=<fixture>/support sh build.sh  ->  c9c2632e…23c9   (twice, identical)
patch_candidate.py --original …        ->  46d16e99…fcd0   (twice, identical)
```

## 6. Files

| File | What it is |
|---|---|
| `00-window-host.txt` | host side: branch, commit, contract hashes, absent directories |
| `01-contract-identity.txt` | file hash, canonical hash, field list, fixture self-check 13/13 |
| `02-fixture-vs-120.txt` | per-file comparison of the 120 fixture against the tree |
| `03-guest-run.txt` | the whole guest run: hashes, V3, control, V5, V4 note |
| `03a-v3-candidate.json` | the V3 manifest the runner wrote for the candidate |
| `03b-v3-original.json` | the same for the unrepaired original |
| `04-contract-inventory.txt` | every reachable CWE416 contract, plus the searches |
| `05-v4-not-run.json` | V4 `not_run`, with the engine that exists and was not used |
| `run_sync.sh` | the script that produced `03-*`; no hidden steps |

## 7. Checking it without trusting this record

```sh
cd docs/handoffs/evidence/cwe416-contract-sync-2026-11-05
sha256sum -c SHA256SUMS          # every file except SHA256SUMS itself
sha256sum SHA256SUMS             # compare with bundle-sha256.txt
cd -
sha256sum fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/contract.json
python3 -c "import json,sys; sys.path.insert(0,'.'); \
from app.domain.contracts import SecurityContract as S; \
print(S.from_dict(json.load(open('fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/contract.json'))).sha256())"
```

## 8. Not claimed

No gate verdict, no Gate 4, no T8.3 relief, no binary-level V4, no second defect
class and no second sample. `required_obligations` still lists `symbolic`, so an
attempt assembled from the 122 bundle remains `REQUIRED_CHECK_NOT_RUN` →
inconclusive — which is a contract-owner decision, not something this pass can
close by running the runner again.
