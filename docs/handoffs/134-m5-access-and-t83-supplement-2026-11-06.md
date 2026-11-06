# 134 — M5 access, the shared handoff, and the two questions a verifier asks first

- Date: 2026-11-06 (16:39–17:05 local)
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput` at `ea5cc9e`
- For: M5 (asked for guest access plus the V4 handoff)
- Gate status assigned here: **none**. V4 stays `not_run`, no `verified_by` is
  written, T8.3 stays blocked.

## 1. What M5 gets

**Account** — `m5verify` on the guest, built the same way as `m4verify`:

| | |
|---|---|
| uid | 1005, own group, `/bin/bash` |
| privilege | none. `sudo -n true` exits 1; the sudo group is still `lab,ubuntu` |
| password | locked (`passwd -S` → `L`); a key is the only way in |
| keys at delivery | **none**. The account exists with an empty `authorized_keys` |
| reachable at | `192.168.30.128:22`, VMnet8 IPv4 |

The keypair belongs to M5, not to me:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/m5_id_ed25519 -C "m5@verifier"      # M5
sudo USER_NAME=m5verify sh guest/add-m4-key.sh m5_id_ed25519.pub    # M3, on the VM host
```

The same script that installs M4's key, with `USER_NAME` set — it refuses a
private key, appends idempotently, and leaves the file at 600. No private key for
any account exists in the repository or in a package.

**Files** — a root-owned, read-only install that any account can read and run:

```
/opt/binrepair-handoff/
  M4-v4-handoff-2026-11-06/       12 checks + 13 files, the runnable package
  T8.3-evidence-2026-11-06/       29 rows, the sample, candidate, V0–V5, V4 producer evidence
  T8.3-supplement-2026-11-06/     4 files, the audit and the mapping (§3)
```

`chmod a+rX` on directories and files, `+x` on the three scripts. M5 cannot write
into it; `sha256sum -c` in each directory is the way to confirm nothing changed.

## 2. Rehearsal, run as m5verify

A throwaway key was installed with the procedure above, the checks were run, and
the key was removed. What came out (`logs` kept beside this record):

```
$ id
uid=1005(m5verify) gid=1005(m5verify) groups=1005(m5verify)
$ sudo -n true
sudo: a password is required          exit=1

$ sha256sum -c SHA256SUMS             (in each directory)
  all 12 rows OK (payload)
  all 29 rows OK (T8.3 bundle)

$ sh /opt/binrepair-handoff/M4-v4-handoff-2026-11-06/verify_all.sh
  EXIT=0    ALL PASS: 3/3 steps
$ /opt/angr-venv/bin/python -c 'import angr, z3; print(angr.__version__, z3.get_version_string())'
  10.0.4.post1 5.1.0
$ test -w .../README.md
  not writable (expected)
```

This is a rehearsal by M3, not an M5 run. It proves the account, the path and the
permissions work; it says nothing about what M5 will conclude, and it is not
evidence of independence.

## 3. The supplement, because two questions come before any verdict

`T8.3-supplement-2026-11-06/` — reading, not new measurement. It does not touch
the candidate, the fixture, the contract or any gate file.

**`hooks-audit.md`** — the five hooks (`malloc`, `memset`, `free`, `printLine`,
`exit`, which are exactly the contract's `allowed_calls`), each with what it
replaces, which direction it approximates, what it could hide, and why it cannot
hide this defect. It says plainly that the model cannot see a data-value defect,
because `memset` is a no-op and the question is pointer identity.

It also lists two places where the harness's own documentation is wrong, and
leaves both alone: the module docstring still mentions `write_v4_evidence` (stale
since record 128), and `HOOKS[3].why` claims the state is terminated after
observing `printLine`, which the code does not do — it returns and continues,
which is *more* coverage, not less. Patching a comment would change bytes that
records 128, 129 and 133 vouch for.

**`property-mapping.md`** — the contract forbids a *symptom* ("stdout carries
allocator residue"), the harness asks a *cause* ("a freed pointer reached the
printer"). The file argues both directions: cause ⇒ symptom through tcache
behaviour; symptom ⇒ cause only under three named conditions (one writer, no
reallocation in between, no post-free write). It also explains why the split is
not a gap — V3 measures the symptom on the real binary, V4 proves the cause over
every address `malloc()` can return.

**`check_mapping.py`** — the mechanical half, nine assertions, `9/9` and exit 0
when run against the delivered bundle as `m5verify`:

```
target_entry matches · input_mode none on both sides · property is pointer-flow
hooks == allowed_calls · known_good holds with unsat · known_bad violated with sat
scope model and empty disjunction disclosed · forbidden_behavior names free() and stdout
required_obligations are the six gates
```

It fails if the harness starts asking about a different function, if a hook
appears that the contract does not allow, or if the model-scope disclosure
disappears.

## 4. Nothing frozen was touched

| | |
|---|---|
| candidate | `46d16e99…1fcd0` — unchanged since record 124 |
| fixture | `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/` — no edits |
| contract | `8a2b408c…e3c3b` file, `c1684f15…b4f7c` canonical — unchanged |
| `M3-133` archive | still valid; no file in it changed, so it was not rebuilt |

## 5. Boundaries

- **No `verified_by`.** Neither account, neither directory, neither record.
- **V4 is `not_run`** in `gate-index.json`, and the producer evidence next to it
  is not promoted by anything written here.
- **T8.3 stays blocked.** One sample, one mechanism. M5 running these checks is
  a reader exercising the package, not the "second class" decision — that is M4's
  replay plus the Lead.

## 6. What M5 still needs from us

1. Send the public half of a keypair; M3 installs it (one command above).
2. Nothing else — the paths, sums and scripts are already in place, and the
   rehearsal shows they work for this account.
