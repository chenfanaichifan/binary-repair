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

Post-freeze changes are recorded in
[`state-change-2026-10-22.md`](state-change-2026-10-22.md); the frozen
`provenance.md` is left unedited and its hash is unchanged.

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

### O1 — V4 is unrun (the toolchain is no longer the blocker)

The tools that were missing on 2026-10-20 (angr/Claripy/Z3, LIEF, clang,
Ghidra/JDK) are now installed and smoke-tested — see
[`state-change-2026-10-22.md`](state-change-2026-10-22.md) §1. Installation was
assigned to another team member on 2026-10-20; the Lead does not modify the VM.

**V4 itself has not been run.** A toolchain is not a V4 result: the verdict is
Member 4's, and until it runs this item stays open as "V4 unrun", not "V4
blocked for lack of tools".

### O2 — Candidate execution is not yet isolated

1. the reset point is now `clean-baseline` (uid 6, 2026-10-22 16:54, shut down),
   but its **revert has not been tested**;
2. `lab` still has passwordless sudo — a binary invoked directly as `lab` can
   become root;
3. the isolated wrapper exists (`/opt/binrepair/run-isolated.sh`: `runner`
   uid 1003, empty network namespace) but **the broker does not invoke it**, and
   there is no hypervisor-level egress block;
4. tools are not read-only to the execution user.

At minimum the wrapper must be wired into the broker, tools mounted read-only,
and the egress gap either closed or accepted in writing **before a candidate
binary runs through the product**. Owner: not yet assigned (the Lead does not
modify the VM). Blocks "run candidates", not the input freeze.

### O3 — Guest image hash is not frozen

The disk is a **chain** (2026-10-22); there is no single-file identity.
Hashes were taken with the VM powered off (no `vmware-vmx` process):

```text
7dec112509c833a66b44c2e1aebdc607d33b323ca61351d7cfe0c83886101468  disk.vmdk           (6,792,544,256 B)
28451ed9fcf8f54f6fbe0c337c9fe8f6e4823dba08e242daae52855b4647bd92  disk-000001.vmdk    (33,882,112 B)
b501715b37e954e1ea509ab138d03bb34e45d5672a5b5192dc28dc72bd37100c  disk-000002.vmdk    (12,320,768 B)
b94aa009ea4de3d2087ef1df95ee0f4a45de50fe4966a61f9668c415918b7323  disk-000003.vmdk    (3,997,696 B, active layer, not part of clean-baseline)
```

These are **provisional**: no clean-shutdown cycle has been recorded for the
current chain, and the lead requires one before the guest image hash is frozen.
Record the whole set or consolidate the chain; a single-file hash identifies no
baseline. They are not signed and must not be presented as the V5 image identity.

### O4 — Backend commit

Local commits exist on `member-3-route-a`: `d1e0741` (fixture + gate 6
evidence), `baefea2` (byte-exact checkout attributes), `627d9eb` (manifest-set
hash confirmed) and `5b60915` (2026-10-22 state change), all on top of
`e030cc2`. They are **not pushed**: remote operations still fail with
`SEC_E_NO_CREDENTIALS` (re-probed 2026-10-22). No remote commit hash can be
recorded yet, so another member cannot fetch the state this record describes —
and a local hash is not a stable identity, since every later commit moves HEAD.

## 5. Not frozen, not signed

- **Gates 3–5** — no sign-off. Route A feasibility, Route B unchanged round
  trip and safe placement are still pending.
- **V4 symbolic detection** — not run. The toolchain is now present (see
  `state-change-2026-10-22.md` §1), so "tools absent" is no longer the reason;
  the item stays pending until Member 4 runs it and reports a verdict.
- **Guest image hash** — not frozen; requires a clean shutdown (O3).
- **Sign-off** — none. No role has signed this record. It freezes inputs, not
  gate conclusions.

## 6. Invalidation

Any change to a row in §1 creates a new freeze record and invalidates prior
approvals. If gates 3–5 later fail, the sample is replaced and a new record is
created; the existing freeze does not become a pass. Gate 6 remains `partial`
until symbolic detection is either performed or explicitly recorded
`unsupported`.
