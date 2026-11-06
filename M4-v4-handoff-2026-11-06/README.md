# M4 — V4 verification handoff

Everything needed to check the V4 evidence on the machine that produced it, plus
the expected outputs to check it against.

**What this is not.** It carries no `verified_by` value, no gate result, and no
claim that V4 passes. The 124 bundle still records V4 as `not_run`. Deciding
whether the evidence is acceptable is M4's job; this package only makes the
decision executable and falsifiable.

## Access

| | |
|---|---|
| address | `m4verify@192.168.30.128` port 22 — routable IPv4 on VMnet8, no link-local, no `%5` |
| user | `m4verify` (uid 1004), own group, `/bin/bash`, password locked |
| key | `dist/m4verify_id_ed25519`, fingerprint `SHA256:5JOwkAS+6WI6rTdI88Ho6J4Lly/A+lozxUhEPN21zBc` |
| privilege | none. `sudo` answers "a password is required"; the account is in no sudo group |
| interpreter | `/opt/angr-venv/bin/python` — CPython 3.12.3, angr 10.0.4.post1, z3 5.1.0, readable by this user |

```sh
ssh -i m4verify_id_ed25519 m4verify@192.168.30.128
```

or, if you prefer a name, put this in `~/.ssh/config`:

```
Host binrepair-m4
    HostName 192.168.30.128
    User m4verify
    IdentityFile ~/keys/m4verify_id_ed25519
    IdentitiesOnly yes
```

The address is the guest's VMnet8 lease, bound to the VM MAC, and has been
`192.168.30.128` in every window recorded since 2026-10-22. If a reboot ever
moves it, ask the hypervisor rather than guessing:

```sh
"D:/VMware/vmrun.exe" -T ws getGuestIPAddress "D:/VMs/binrepair-u2404-x64-01/BinRepair-Lab.vmx"
```

The private key ships outside this directory on purpose: it is not in
`SHA256SUMS`, not in the zip, and not in git. Only the public half is installed,
at `/home/m4verify/.ssh/authorized_keys` (mode 600, owner `m4verify`).

## Run it

Copy this directory anywhere, then:

```sh
sh verify_all.sh        # 3 steps, exits 0 when all pass
```

or the steps separately:

```sh
sh run_selfcheck.sh     # is this the recorded environment?   exit 0/1/2
sh run_e2e.sh           # does the producer reproduce the output? exit 0/1/2
```

All three resolve their paths from their own location, so the working directory
does not matter and nothing has to be exported first.

This exact tree was extracted into a fresh empty directory as `m4verify` and run
there; `sh run_selfcheck.sh` exited 0. The transcripts are kept with the record
that delivered this package,
`docs/handoffs/evidence/m4-handoff-2026-11-06/`, rather than inside the package —
a transcript of checking a tree cannot contain the hash of the sums that cover
it, so the evidence sits one level up and is hashed separately.

## Layout

```
M4-v4-handoff-2026-11-06/
  README.md
  run_selfcheck.sh                    environment check + comparison, exit 0/1/2
  run_e2e.sh                          harness rerun + byte comparison, exit 0/1/2
  verify_all.sh                       integrity, self-check, rerun; exit = failures
  scripts/selfcheck.py                the 18 checks, --json writes the normalised result
  scripts/summarize_output.py         one-screen summary of a harness output file
  inputs/v4_harness.py                the producer, unchanged from record 128
  inputs/candidate.elf                repaired binary
  inputs/original.elf                 unrepaired control
  inputs/contract.json                v3 no-input contract, unchanged since record 121
  expected/selfcheck.expected.json    normalised result of the 18 checks
  expected/harness-output.expected.json  the producer's recorded output
  SHA256SUMS                          every file above
```

## Inputs, and where they come from

| file | sha256 | origin |
|---|---|---|
| `inputs/v4_harness.py` | `986688bc…b863e` | `docs/handoffs/evidence/cwe416-v4-2026-11-06/v4_harness.py` (record 128) |
| `inputs/candidate.elf` | `46d16e99…1fcd0` | `docs/handoffs/evidence/cwe416-candidate-2026-11-05/candidate.elf` (record 122) |
| `inputs/original.elf` | `c9c2632e…123c9` | `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/original.elf` (record 121) |
| `inputs/contract.json` | `8a2b408c…e3c3b` | same fixture directory, `schema_version 3`, `input_mode none` |
| `expected/harness-output.expected.json` | `9c6eeda7…8ca8c` | `docs/handoffs/evidence/cwe416-v4-2026-11-06/harness-output.json` |

The contract is included so the target entry is read from it rather than
hardcoded: `target_entry` resolves to `0x4012aa` in both binaries.

## What the expected outputs mean

`expected/selfcheck.expected.json` is the normalised result of the 18 checks —
per-check `ok` flags, the engine block, and the pass count. `run_selfcheck.sh`
compares the measured result against it structure by structure and prints the
first difference if they disagree. Machine-specific text (hostname, platform,
interpreter path) is printed for the reader but kept out of the comparison, so
the file is portable while the checks stay strict.

`expected/harness-output.expected.json` is the producer's output. `run_e2e.sh`
compares the whole file with `cmp`, not field by field: if any number, ordering
or string moves, the digest moves, and that is the point. The recorded
measurement is

```
known_good  candidate  holds      eval=1 sat=0 unsat=1  steps 11/64
known_bad   original   violated   eval=1 sat=1 unsat=0  steps 14/64
complete=True unexplored=[] unknown=0 timeouts=0 claimed_scope=model replay 2 identical
```

The negative control matters as much as the positive one: a harness that reports
"no violation" on both binaries has proven nothing, and `known_bad` is there to
fail that case.

## Known defect in the producer's docstring

`inputs/v4_harness.py` still says its output "is written only through
`write_v4_evidence`, which re-checks the checklist". That was true in record 127
and stopped being true in 128, when the second writer was deleted and M1's
adapter took over. The code writes the measurement file directly
(`args.out.write_text(...)`, around line 473); the adapter still produces the
product `v4-symbolic.json` from it.

The sentence is left alone rather than fixed here, because the file's sha256
(`986688bc…`) is what records 128 and 129 cite; correcting a docstring would
change the bytes that two delivered records vouch for. Treat the code as
authoritative and the sentence as stale.

## What is still not claimed

- **No `verified_by`.** Nothing in this package sets it. Writing it is the
  verifier's act, after its own replay — doing it here would make the producer
  its own judge.
- **V4 remains `not_run`** in `gate-index.json` of the 124 bundle. Running these
  scripts says the environment and the producer are reproducible; it does not say
  the evidence is sufficient.
- **One sample.** CWE416 no-input only. T8.3 stays blocked: no second defect
  class exists here, and none is implied by this package.
- **The scope is a model.** `claimed_scope: model` — a property over the target
  function with a symbolic `malloc` result, not a statement about machine code.
  `not_claimed` inside the expected output lists the exclusions, including that
  the candidate's unsat comes from an empty disjunction (no `free()` on that
  path) rather than from a solved constraint.
