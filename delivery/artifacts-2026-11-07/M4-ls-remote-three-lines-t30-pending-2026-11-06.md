# M4 — ls-remote three lines; T30 build artifacts still pending (2026-11-06)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** actual remote ref check and T30 artifact gate. No gate promotion, no
merge, no tag.

---

## 0. Verdict

| Item | Result |
|---|---|
| `canonical/m1-m5-integration` | **`1938c31`** — remote head, SSH and HTTPS agree |
| `m1/t30-acceptance-ab-2026-11-05` | **`fdc083d`** — remote |
| `m3/cwe416-v3-noinput` | **`42d0018`** — remote |
| `8735f75` as a remote ref | **REJECTED** — no remote ref contains it |
| `8735f75` locally | **not even an object** in this clone |
| T30 build artifacts | **NOT DELIVERED** — no `original.elf` / `output.sha256` / tests / SUMS build package |
| CWE-121 | **NOT VERIFIED** — `verified_by: null` |
| 118 | **VERIFIED** — independent of T8.3 |
| T8.3 | **BLOCKED** |

---

## 1. Actual `ls-remote`

Remote: `git@github.com:chenfanaichifan/binary-repair.git`.

```text
1938c311672282ebd1fee3634fec9aad57760769  refs/heads/canonical/m1-m5-integration
e2317772d638dbedbc64e6f049d1dcf4f1bc7699  refs/heads/integration/live-bridge-2026-11-03
fdc083da747ff305457bb7f8096ad35431ba4e08  refs/heads/m1/t30-acceptance-ab-2026-11-05
42d00181e03c17eaf54d18924b4ea8d2de499406  refs/heads/m3/cwe416-v3-noinput
472aa94b8d931e03a2b20a8e4f671ba64f832230  refs/heads/main
```

HTTPS cross-check returns the same three SHAs:

```text
1938c311672282ebd1fee3634fec9aad57760769  refs/heads/canonical/m1-m5-integration
fdc083da747ff305457bb7f8096ad35431ba4e08  refs/heads/m1/t30-acceptance-ab-2026-11-05
42d00181e03c17eaf54d18924b4ea8d2de499406  refs/heads/m3/cwe416-v3-noinput
```

### The three lines

| Line | Ref | SHA |
|---|---|---|
| canonical (M1+M5) | `canonical/m1-m5-integration` | `1938c31` |
| M1 T30 | `m1/t30-acceptance-ab-2026-11-05` | `fdc083d` |
| M3 CWE416 | `m3/cwe416-v3-noinput` | `42d0018` |

---

## 2. `8735f75` is not remote

```text
$ git ls-remote origin | grep -i 8735f75
(no remote ref contains 8735f75)

$ git cat-file -t 8735f75
fatal: Not a valid object name 8735f75
```

Record 111 says the canonical branch was force-updated `8735f75 -> 1938c31`
(`force-with-lease`), with the SHA read back from `git ls-remote` after the push.
The actual remote confirms it: **the canonical head is `1938c31`; `8735f75` is
not a remote ref, and in this clone it is not even present as an object.**

So `8735f75` must not be cited as a remote existence or as the canonical head.

---

## 3. T30 build artifacts — pending

What exists is documentation/acceptance, not the build:

```text
M1-T30-acceptance-and-AB-2026-11-05.zip (11 files):
  106-…decision.md, 118-evidence-absence.txt, SHA256SUMS, constraints.txt,
  contract-probe.txt, cwe416-corpus.txt, cwe416-fixture.txt, fork.txt,
  status.json, suite.txt, t30-package.txt

delivery/t30-rebuild-2026-11-05/:
  M3-t30-rebuild-evidence-2026-11-05.zip, PROVENANCE.md, README.md
```

There is **no `output.sha256` anywhere** in the workspace, and no
`original.elf`/tests/SUMS build package for T30. Verification is therefore
**pending**, not passed.

When the build package arrives, the four checks are:

| # | Artifact | Check |
|---|---|---|
| 1 | `original.elf` | SHA-256, size, ELF identity, contract/entry binding |
| 2 | `output.sha256` | format, content, and the hash it claims matches the built bytes |
| 3 | tests | valid/invalid cases, counts, and the no-input `1/1` shape where applicable |
| 4 | `SHA256SUMS` | coverage of every shipped artifact, no omissions, `shasum -c` clean |

---

## 4. CWE-121 and 118

- **CWE-121: NOT VERIFIED.** `fixtures/public/CWE121_…/build.json` still has
  `verified_by: null`; no independent replay/acceptance has been recorded.
- **118: VERIFIED** (rebuild evidence package), independent of T8.3.

T8.3 remains **BLOCKED**: one sample, one defect class, no second public sample.

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
| `M4-ls-remote-t30-evidence-2026-11-06.txt` | SSH/HTTPS `ls-remote`, 8735f75 absence, T30 zip/delivery listing, no `output.sha256`, CWE121/124 state |
| `_m1-work/canonical` | the clone used for `ls-remote` |
| `M1-T30-acceptance-and-AB-2026-11-05.zip` | acceptance docs, not the build |
