# Candidate handoff — Member 3 → Member 5 (gates 3–5)

**Status: NOT FROZEN — feasibility candidate.**
Built 2026-10-20 02:27 UTC. "Freeze" is a hash lock + sign-off that happens
*after* gates 3–5 pass; it is **not** a prerequisite for running them. This
candidate exists so the gate work can start now.

## 1. What is being handed over

Canonical directory:
`fixtures/public/CWE121_src_char_declare_cpy_51b/`

| Artifact | SHA-256 | Notes |
|---|---|---|
| `original.elf` (26,792 B) | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` | the binary to patch |
| `tests/valid.json` | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` | 4 valid cases |
| `tests/invalid.json` | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` | 2 invalid cases |
| `provenance.md` | see `SHA256SUMS` | build/provenance record |
| `evidence/03-run-boundary.txt`, `04-gdb-crash-100.txt`, `06-manifest-vs-original.txt` | see `SHA256SUMS` | V0 evidence |

`SHA256SUMS` in the fixture root is the integrity list; verify with
`sha256sum -c SHA256SUMS` before starting.

Do **not** edit `original.elf`, the manifests, or the provenance. Work on
copies for gate experiments and record every copy's hash.

## 2. Contract the gates are testing against

- `DEST_CAPACITY = 50` (`char dest[50]`, case line 28); max valid **49**.
- Function under test: `..._51b_badSink` @ **0x4012b0** (104 B).
- Harness `main` @ **0x401256–0x4012af** is fixture infrastructure and is
  **outside the repair scope**. A candidate patch must not touch it.
- valid (`len <= 49`): reproduce the original's measured stdout / exit 0.
- invalid (`len >= 50`): exit **1**, stdout empty, stderr exactly
  `ERROR: input exceeds destination capacity\n`.
- Both routes must emit byte-identical stderr. Do not relax this locally; a
  contract change is a team decision with a new manifest.

Original runs 4/6 on the manifest (valid pass, invalid fail). That is V0
evidence, **not** gate 6 and not a gate 3–5 result.

## 3. What gates 3–5 need from you

### Gate 3 — Route A patch feasibility

- Can a machine-instruction patch enforce the length check and return 1?
- Can it produce the exact stderr bytes? Be explicit: if this requires adding
  a data string and a call through the PLT at a site with unknown live
  registers, say whether that is still within Route A's permitted scope
  (F2 says machine-instruction changes only). This is a **scope ruling** for
  Member 4 + team lead, not something to decide silently.
- If not feasible: report `unsupported` with the reason and the evidence.
  Do not change the oracle.

### Gate 4 — Route B unchanged round trip

- Recover the local region, compile it, and pass the **unchanged round trip**
  before any security edit.
- Report the recovered region, compile command, behavioral comparison on the
  valid tests, and any manual corrections.

### Gate 5 — safe placement, both routes

- Together with Member 3: patch site(s), exact bytes, instruction boundaries,
  affected transfers, and confirmation that the edit does not overlap
  `0x401256–0x4012af`.
- "It fits by luck" is not placement evidence; show the boundary check.

## 4. Environment and isolation

Your stated environment (Ubuntu + JDK 21 + Ghidra + Patcherex2) is fine for
**feasibility** work. Two conditions:

1. use a disposable Ubuntu x86-64 guest, not the Windows host, for any
   assemble/patch/execute step;
2. our guest is **not** ready for candidate execution (a snapshot exists but
   post-dates the fixture build, passwordless sudo, NAT reachable, no read-only
   tool mount). If you use our guest, stop and tell us first; otherwise keep
   the gate work in your own disposable VM and record its profile.

## 5. Failure path

If the candidate fails any gate:

- record the exact reason and evidence, do not "work around" it by changing
  the oracle or the harness;
- tell Member 3 and Member 4 **before** the 2026-10-21 freeze;
- the team decides whether to replace the sample. Do not substitute a second
  sample for the same input without agreement.

## 6. Return format

```text
Gate 3: PASS / FAIL / PARTIAL / NEEDS SCOPE RULING
  patch site: ...
  changed bytes: ...
  stderr byte-exact: yes / no
  evidence: path + sha256
Gate 4: PASS / FAIL
  recovered region: ...
  round-trip result: ...
  evidence: ...
Gate 5: PASS / FAIL
  placement (both routes): ...
  boundary check vs 0x401256-0x4012af: ...
Recommendation: freeze / replace sample / need ruling
```

Deadline: **2026-10-21**. Passing gates 3–5 plus Member 4's gate 6 `partial`
acceptance is what turns this candidate into the frozen fixture; the hashes do
not change at freeze, only their status does.
