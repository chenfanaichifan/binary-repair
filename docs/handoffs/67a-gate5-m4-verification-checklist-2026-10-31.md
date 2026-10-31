# 67a — Gate 5 Route A: M4 verification checklist (hash manifest + run details)

**Purpose:** standalone re-hash checklist so M4 can independently verify the Gate 5 Route A
probe run recorded in `67` without trusting the executor's summary.

**Rule (from record `51`):** M4 re-hashes every returned file; the executor's summary is NOT the
result. Each file below is hashed with `sha256sum`; a mismatch → the row is FAIL.

**Evidence location:** `.tmp/gate5-evidence/` (29 files). Not committed to the repo.

---

## 1. Successor binary (bind Gate 5 only)

| Field | Value |
|---|---|
| Source | `route-a/jobwrap-gate5/jobwrap_gate5.c` (git `ac96e74`) |
| Build | guest `gcc -O2 -Wall -Wextra -Werror -static`, GCC 13.3.0 |
| **Binary SHA-256** | `90af91ef6b238428d202f891e5829ed81733b76dd9e7f184acd91f4cd769ff20` |

M4 re-hash: `sha256sum /usr/local/sbin/jobwrap-gate5` (inside guest).

## 2. Pinned identities (compile-time, fail-closed)

| Item | SHA-256 |
|---|---|
| probe `scripts/m4_gate5_probe.py` | `f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb` |
| candidate `routea/out/cave-probe.elf` | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` |
| original `fixtures/.../original.elf` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |

## 3. Six frozen cases (from `six-cases.json`)

| case | input_len | expected rc | observed rc | ok |
|---|---|---|---|---|
| valid-empty | 0 | 0 | 0 | true |
| valid-smallest | 1 | 0 | 0 | true |
| valid-typical | 10 | 0 | 0 | true |
| valid-maximum | 49 | 0 | 0 | true |
| invalid-first | 50 | 1 | 1 | true |
| invalid-longer | 100 | 1 | 1 | true |

## 4. Isolation attestation (from `environment.txt`)

| Field | Observed | Expected |
|---|---|---|
| Uid | `1003 1003 1003 1003` | 1003 |
| Gid | `1003 1003 1003 1003` | 1003 |
| CapEff | `0000000000000000` | 0 |
| NoNewPrivs | `1` | 1 |
| Seccomp | `2` | filter active |
| default_route | `''` (rc=1) | no egress |
| netns | `net:[4026532222]` | isolated |
| script_sha256 | `f39a0302…d146cb` | matches pin |

## 5. Full file hash manifest (re-hash each; 29 files)

```
c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82  candidate.elf
4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865  case-invalid-first.rc
083d3bfb2d9e1fa4978aabdd2318d60c67bd54f2a34d0086b0a9d11f6f84f69b  case-invalid-first.stderr.bin
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  case-invalid-first.stdout.bin
4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865  case-invalid-longer.rc
083d3bfb2d9e1fa4978aabdd2318d60c67bd54f2a34d0086b0a9d11f6f84f69b  case-invalid-longer.stderr.bin
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  case-invalid-longer.stdout.bin
9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa  case-valid-empty.rc
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  case-valid-empty.stderr.bin
01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b  case-valid-empty.stdout.bin
9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa  case-valid-maximum.rc
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  case-valid-maximum.stderr.bin
4a2cc35d0c0a06ee211d0d8bc49a1208caf43d3de57e13867c9333610e544199  case-valid-maximum.stdout.bin
9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa  case-valid-smallest.rc
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  case-valid-smallest.stderr.bin
06f961b802bc46ee168555f066d28f4f0e9afdf3f88174c1ee6f9de004fc30a0  case-valid-smallest.stdout.bin
9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa  case-valid-typical.rc
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  case-valid-typical.stderr.bin
705d290c12895901f809f6c2fe772a94db5181d726464d840682106f4a934b87  case-valid-typical.stdout.bin
1926ce1f526820ef0376c212a76f9e7b4ee96ea8ba797b135669498e58ea6b1d  cave-file.bin
417fb23720e4ae7605d6ac3154b8980b8c3c13d12782a632ffc5dc04a4585d36  cave-file.sha256
1926ce1f526820ef0376c212a76f9e7b4ee96ea8ba797b135669498e58ea6b1d  cave-memory.bin
417fb23720e4ae7605d6ac3154b8980b8c3c13d12782a632ffc5dc04a4585d36  cave-memory.sha256
d9a21ea53e443dbca43e430c48cd9c4c33bf0e99bfb601272ff5208387583df4  environment.txt
261f4cce1a7ea213eaccbfe8ac13b1255b3da5025f94f33c2fb1eb733aa26b8e  gdb-probe.log
93ff7811a209e2a8479230bbb9b6bc19f7f311d3af383ec350c1db2a7e7d5494  gdb-probe.rc
8eb3093eba42ebdf5d55021644254ba178c5051e53896970819bf9876df452c5  probe-summary.json
b5f037743f9d5f76b8cfa291e839c420a6bcc508b9dedcdb5f547ab521cf0f55  probe.gdb
b4213dfe9502c1e456bc3314c0e8e9791bb821ea52c8e4108ba7852ad61bcba6  six-cases.json
```

`SHA256SUMS` (the evidence manifest itself) sha256 =
`05438764a119ee979fa3ab175b8ec08250e392e112cd5203fbd52cdf77873ec8`.

## 6. M4 signature

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | M4 | — | — (blank; fills record `51` after independent re-hash) |
| Lead (Gate 5 approval) | Lead | — | — (blank) |
