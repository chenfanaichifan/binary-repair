# 67 — Gate 5 Route A successor execution witness (M3+M5 run, 2026-10-31)

**From:** M3+M5 (merged agent, executor — NOT the M4 verifier)
**To:** M4 (independent verifier), Lead
**Date:** 2026-10-31 21:53 (Asia/Hong_Kong)
**Status:** **Execution witness only.** This is NOT the Gate 5 verdict and NOT an M4 signature.
Record `51` remains UNSIGNED / NOT VERIFIED until M4 independently re-hashes every file and
signs its own verifier row. This document records what actually ran, for M4 to verify against.

---

## 0. What this is and is not

- **Is:** the raw result of building the `jobwrap-gate5` successor (approved by Lead in handoff
  66) inside the guest and running M4's fixed probe under it.
- **Is NOT:** a PASS/FAIL claim. The probe's own CHECK lines are *inputs for M4*, not a gate
  result (the probe script itself says so). M4 classifies; M4 signs record `51`.

---

## 1. Successor binary

| Field | Value |
|---|---|
| Source | `route-a/jobwrap-gate5/jobwrap_gate5.c` (committed, git `80c90e7`) |
| Build | `gcc -O2 -Wall -Wextra -Werror -static` inside guest (`lab@192.168.30.128`), GCC 13.3.0 |
| Install path | `/usr/local/sbin/jobwrap-gate5` (does NOT overwrite `/usr/local/sbin/jobwrap` = `b232d60b`) |
| **SHA-256** | **`90af91ef6b238428d202f891e5829ed81733b76dd9e7f184acd91f4cd769ff20`** |
| Size | 799,2xx bytes (static) |

Note: three earlier builds were iterated during bring-up (`24d981be…`, `2629129a…`,
`f17acec3…`, `4c98eeee…`) to fix header includes, seccomp install ordering, and the seccomp
allow-list. **The binding hash is the final one above** (`90af91ef…`). None of the intermediate
builds were used for the run recorded here.

## 2. Invocation (fixed argv, exactly as approved)

```
sudo /usr/local/sbin/jobwrap-gate5 probe m4-gate5 -- /srv/gate5-build /var/tmp/gate5-work
```

- `repo-root` = `/srv/gate5-build` (a guest checkout staged for the probe: `routea/out/cave-probe.elf`,
  `fixtures/public/CWE121_src_char_declare_cpy_51b/{original.elf,tests/{valid,invalid}.json}`,
  `scripts/m4_gate5_probe.py`).
- `work-dir` = `/var/tmp/gate5-work`.

## 3. Fail-closed (negative) check — passed

Before the real run, the probe blob was tampered (`echo '# tampered' >>` the probe), and the
successor refused to execute:

```
jobwrap-gate5: probe blob mismatch: got 9c827d2e…e7, expected f39a0302…cb
```

The pinned blob check is fail-closed and does not read the environment.

## 4. Probe result (raw, unclassified by us)

`scripts/m4_gate5_probe.py` output — **19 PASS, 0 FAIL, 0 NOT VERIFIED**:

| ID | Result |
|---|---|
| R1-candidate-identity | PASS `c4a159…aa82` |
| R1-original-identity | PASS `aa428157…8393` |
| R6-isolation-uid | PASS `uid=1003` |
| R6-isolation-caps | PASS `CapEff=0000000000000000` |
| R6-isolation-nnp | PASS `NoNewPrivs=1` |
| R2-runtime-mapping | PASS `0x401000–0x402000 r-xp /var/tmp/gate5-work/candidate.elf` |
| R4-site / R4-cave / R4-after / R4-ret | PASS (all four gdb markers) |
| R3-memory-equals-file | PASS `file=… memory=… bytes=1815/1815` |
| R5-case-valid-empty/smallest/typical/maximum | PASS (rc=0) |
| R5-case-invalid-first/longer | PASS (rc=1) |
| R5-six-cases | PASS `6/6` |
| R7-candidate-stable | PASS `c4a159…aa82` |
| R8-evidence-manifest | PASS `rows=29 sha256sums_sha256=05438764…3ec8` |

## 5. Isolation attestation (from `environment.txt`, raw)

```
Uid:      1003 1003 1003 1003
Gid:      1003 1003 1003 1003
CapEff:   0000000000000000
CapBnd:   000001ffffffffff
NoNewPrivs: 1
Seccomp:  2
default_route_rc=1 default_route=''
netns=net:[4026532222]
script_sha256=f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb
```

Interpretation (for M4): uid/gid 1003, effective capabilities fully cleared (`CapEff=0`),
NoNewPrivs on, seccomp filter active (mode 2), **no default route in an isolated netns**
(`net:[4026532222]`, `default_route=''`) → no egress. Probe blob hash matches the pinned
`f39a0302…d146cb`.

## 6. Evidence custody

- Raw evidence captured to host at `.tmp/gate5-evidence/` (29 files incl. `probe-summary.json`,
  `environment.txt`, `six-cases.json`, `cave-{file,memory}.bin`, per-case rc/stdout/stderr,
  `SHA256SUMS`).
- `SHA256SUMS` sha256 = `05438764a119ee979fa3ab175b8ec08250e392e112cd5203fbd52cdf77873ec8`.
- Raw evidence is NOT committed to the repo (matches record `51` custody rule).

## 7. What remains (M4-owned)

- M4 re-hashes every returned file and does NOT use this summary as the result.
- M4 fills record `51` rows R1–R8 with PASS/FAIL/NOT VERIFIED and signs its own verifier row.
- Gate 5 may be called PASS only when `51` has all rows PASS, M4 signs, and the Lead approves.
- Record `51` stays UNSIGNED until then; fixture remains NOT FROZEN.

## 8. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| M3+M5 (executor) | M3+M5 | 2026-10-31 | executed; no verdict claimed |
| M4 (verifier) | M4 | — | — (blank; verifies independently) |
| Lead (Gate 5 approval) | Lead | — | — (blank) |
