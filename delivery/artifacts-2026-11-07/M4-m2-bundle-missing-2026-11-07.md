# M4 — M2 bundle not received; V4 key still mismatched (2026-11-07)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** M2 bundle intake and V4 replay status. No merge, no marker, no gate
promotion, no tag.

---

## 0. Status

| Item | Result |
|---|---|
| `outputs/m2-06eb7ee.bundle` | **NOT RECEIVED** — absent from every accessible path |
| `06eb7ee` / `2963163` / `d3993555c303` | **not local, not on any fetched remote ref** |
| fetch bundle / merge 2963163 → d3993555c303 | **NOT RUN** |
| full suite | **NOT RUN** |
| final SHA | **N/A** |
| `delivery/m4/acceptance-<sha>/` | **N/A** |
| V4 `verified_by="m4"` | **NOT WRITTEN** — guest key mismatch |
| T8.3 | **BLOCKED** — wording not unified, V4 not replayed |
| 124 | **`inconclusive` / `required_check_not_run` / `symbolic`** |
| 118 | **VERIFIED** — independent of T8.3 |

---

## 1. Bundle search

```text
$ find /Users/huageorge/Desktop -name 'm2-06eb7ee.bundle'
(no output)

$ find /Users/huageorge/Desktop -name '*.bundle'
upload/route-b.bundle          # old M5 bundle, not M2

$ mdfind -name 'm2-06eb7ee.bundle'
(no output)

$ git cat-file -t 06eb7ee / 2963163 / d3993555c303
fatal: Not a valid object name   (all three)

$ git ls-remote origin | grep -E '06eb7ee|2963163|d3993555'
(no remote ref)
```

Record 96 says the bundle was created but not pushed:

> `06eb7ee` 已打包为 `outputs/m2-06eb7ee.bundle`（SHA256 `6AEF3C73…6CC6`）；
> `git push` 被远端拒绝，需人工转交或提供凭据。

So the file is the missing handoff, not something M4 can reconstruct.

---

## 2. What is needed to do the M2 merge

Deliver one of:

1. `outputs/m2-06eb7ee.bundle` (record 96: SHA-256 prefix `6AEF3C73…6CC6`), or
2. a reachable branch/commit containing `06eb7ee`, `2963163`, and
   `d3993555c303`.

Then the sequence is fixed:

```sh
git bundle verify outputs/m2-06eb7ee.bundle
git bundle list-heads outputs/m2-06eb7ee.bundle        # must include 06eb7ee
git fetch outputs/m2-06eb7ee.bundle <branch>:m4/m2
git switch -c m4/accept-m2 d3993555c303
git merge --no-ff 2963163
git rev-parse HEAD                                     # final SHA
python -m pytest -q -o addopts=""                      # full suite
mkdir -p delivery/m4/acceptance-<sha>/
```

`delivery/m4/acceptance-<sha>/` will contain the bundle digest, merge parents,
full-suite count, final SHA, and the V4 status. Nothing is written before the
merge and suite actually run.

---

## 3. V4 key mismatch remains

Guest route is up at `10.11.0.132:2222`, but this session's key is not installed:

```text
this session  SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q
installed     SHA256:JF1hZZdG… (M5), SHA256:FZfxZXkW… (claimed M4)
```

`FZfxZXkW`'s private half is not on this host and not in the agent; the M5 key
is excluded by the work order. So `verify_all.sh` / the harness / the five
criteria / `verified_by="m4"` remain pending until M3 installs this session's
public key:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBFmDHmwn/0KeulZ32w97zmV2jP+p7kGMdWew2rZnbdq m4-guest-replay-2026-11-06
```

---

## 4. T8.3 and 124

`dd2d926`'s T8.3 `gate-index.json` still lists `"a second sample"` under
`not_done_by_M3` while its README calls the CWE416 sample the second sample —
wording not unified; T8.3 stays **BLOCKED**.

```text
124: V0 passed, V1 passed, V2 not_run, V3 passed, V4 not_run, V5 passed
     outcome = inconclusive
     reason  = required_check_not_run
     failing = symbolic
```

`118 = VERIFIED (rebuild evidence package)` remains independent.

---

## 5. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 6. Evidence

| File | Content |
|---|---|
| `M4-m2-bundle-missing-evidence-2026-11-07.txt` | bundle search, missing commits, remote grep, record 96 quote, 124 gates |
| `96-m2-tool-contract-review-2026-11-07.md` | the bundle's origin and SHA prefix |
