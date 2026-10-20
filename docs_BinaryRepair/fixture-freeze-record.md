# Fixture freeze record — CWE121_src_char_declare_cpy_51b

**Status: input freeze, 2026-10-20.** Only the artifacts in §1 are frozen.
Gates 3–5, V4 symbolic detection and the guest image hash are **not frozen and
not signed** (§5). "Frozen" here means the input bytes and the reviewed
contract cannot change without a new record; it does **not** mean the fixture
passed the route gates or that V4 is ready.

## 1. Frozen inputs

| Artifact | Identity |
|---|---|
| Case | `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b` (Juliet C/C++ 1.3, s09) |
| Case source SHA-256 | `8387d64613192b47c30658153548d111366f232a0bf03714e26643dd16ad343b` |
| `original.elf` | 26,792 bytes, SHA-256 `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| `tests/valid.json` | 1,951 bytes, SHA-256 `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| `tests/invalid.json` | 1,460 bytes, SHA-256 `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |
| Manifest-set SHA-256 | `a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78` (rule below) |
| Reviewed contract | `DEST_CAPACITY = 50`; `MAX_VALID_LEN = 49`; `ERROR_STDERR` = exactly `ERROR: input exceeds destination capacity\n` |
| Oracle | valid (`len <= 49`): reproduce the original's measured stdout and exit 0; invalid (`len >= 50`): exit 1, stdout empty, the exact `ERROR_STDERR` bytes |

`build/`, `evidence/` and `tests/v3_oracle.py` are **supporting material**, not
part of the freeze key. They can be regenerated or corrected without
re-freezing the inputs; changing the rows above cannot.

### Manifest-set hash — confirmed

Rule: SHA-256 (UTF-8) of the canonical JSON below, with `sort_keys=True`,
`separators=(",", ":")`, `ensure_ascii=False`, and `manifests` sorted by
`name`. This is the `manifest_set_json` / `manifest_set_sha256` rule from
`app/domain/manifests.py`; it is **not** byte concatenation and **not** a
concatenation of file hashes.

```json
{"case_id":"CWE121_src_char_declare_cpy_51b","manifests":[{"name":"invalid.json","sha256":"d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d"},{"name":"valid.json","sha256":"17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76"}],"original_sha256":"aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393","schema_version":1}
```

Reproduced independently on 2026-10-20 and matches Member 4's value
`a564f039…33a78`. `case_id`, `original_sha256` and `schema_version` are fixed
inputs.

Covered files (root `tests/`): `invalid.json` (1,460 B,
`d493f370…f8190d`) and `valid.json` (1,951 B, `17b2ee39…1e76`).

**LF caveat.** The hashes are over LF bytes. A CRLF-converted copy hashes
differently (`valid.json` → `7f984a97…`, `invalid.json` → `c5e8dc0a…`), and the
set hash will not match. The fixture directory pins `* -text`; the repository
root now pins `* text=auto eol=lf` so JSON stays LF on Windows checkouts.

## 2. Contract and oracle

- `DEST_CAPACITY = 50` (`char dest[50]`, case line 28); maximum valid length
  **49**, first invalid **50**.
- valid: reproduce the original's measured stdout and exit 0.
- invalid: exit **1**, stdout empty, stderr exactly
  `ERROR: input exceeds destination capacity\n`.
- V0: the original scores **4/6** on the manifest (valid pass, invalid fail);
  this is behaviour evidence, not gate 6.
- V3: a repaired candidate must score **6/6**, with byte-identical stderr on
  both routes.

## 3. Gate status (recorded, not signed)

| Gate | Owner | Status | Evidence |
|---|---|---|---|
| 1. valid-input domain | Member 3 | **done** | 0–49 measured, `evidence/03-run-boundary.txt` |
| 2. binary-level violation | Member 3 | **done** | 100 × `A` SIGSEGV, `evidence/07-gate6-crash-evidence.txt` |
| 3. Route A patch feasibility | Member 5 | **pending** | — |
| 4. Route B unchanged round trip | Member 5 | **pending** | — |
| 5. safe placement, both routes | Member 5 + Member 3 | **pending** | — |
| 6. verifier detects original violation | Member 4 | **partial** | concrete counterexample accepted (`docs_BinaryRepair/gate6-crash-summary.md`); symbolic pending V4 |

Gates 3–5 run on the **candidate** ELF, not on a frozen artifact. Passing them
is recorded in a separate gate record; it does not retroactively sign this
freeze. Handoff note for Member 5:
`docs_BinaryRepair/candidate-handoff-to-member-5.md`.

## 4. Open items (explicit, not implied)

### O1 — V4 is blocked

Missing in the guest: angr/Claripy/Z3, LIEF, clang, Ghidra/JDK. V4 cannot run;
it must be reported `unsupported`/deferred with this reason. Installation was
assigned to another team member on 2026-10-20; the Lead does not modify the VM.
Member 4 owns the V4 verdict. Exit condition: all five installed and
smoke-tested on a **new** clean snapshot.

### O2 — Candidate execution is not yet isolated

1. `clean-toolchain` (uid 3) exists as a powered-off reset point, but it was
   taken **after** the 10:27 fixture build and its **revert has not been
   tested**;
2. `lab` has passwordless sudo;
3. NAT is reachable, no per-job egress block;
4. tools are not read-only to the execution user.

At minimum network cut + unprivileged user + read-only tools must be fixed
**before any candidate binary runs**. Owner: not yet assigned (the Lead does
not modify the VM). Blocks "run candidates", not the input freeze.

### O3 — Guest image hash is not frozen

Hashes captured on 2026-10-20 while the VM was powered off:

```text
30068de303b2a9a9c187a3c2980f1b988b8d6b433c32402fe911eadc1899b0d2  disk.vmdk
8521f4e854d7cac4f607d0208ccd08b9d8121fe68015c7392badb3474d38ce89  disk-000001.vmdk
9a1e3959c9f4ad9d4752101fd4ff9a43191fb7d72e61fa20e033f9fd235ce794  noble-cloudimg.vmdk
```

These are **provisional**: `cleanShutdown` was `FALSE` and no clean-shutdown
cycle has been recorded. The lead requires a clean shutdown before the guest
image hash is frozen. They are not signed and must not be presented as the V5
image identity.

### O4 — Backend commit

Local commits exist on `member-3-route-a`: `d1e0741` (fixture + gate 6
evidence) and `baefea2` (byte-exact checkout attributes). They are **not
pushed**: remote operations fail with `SEC_E_NO_CREDENTIALS`. No remote commit
hash can be recorded yet.

## 5. Not frozen, not signed

- **Gates 3–5** — no sign-off. Route A feasibility, Route B unchanged round
  trip and safe placement are still pending.
- **V4 symbolic detection** — not run; angr/Claripy/Z3/LIEF/clang/Ghidra absent;
  recorded as pending/`unsupported`.
- **Guest image hash** — not frozen; requires a clean shutdown (O3).
- **Sign-off** — none. No role has signed this record. It freezes inputs, not
  gate conclusions.

## 6. Invalidation

Any change to a row in §1 creates a new freeze record and invalidates prior
approvals. If gates 3–5 later fail, the sample is replaced and a new record is
created; the existing freeze does not become a pass. Gate 6 remains `partial`
until symbolic detection is either performed or explicitly recorded
`unsupported`.
