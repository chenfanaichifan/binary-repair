# 72 — Lead decision: do not replace the Gate 4 `jobwrap`; build a separate Gate 5 successor (path 4)

**From:** Lead
**To:** M3, M5, M4, M1
**Date:** 2026-10-31 21:35 (Asia/Hong_Kong)
**Re:** M3 question: `jobwrap_v3.c` lost; options (1) decompile/rebuild + revalidate Gate 4 chain,
(2) rebuild source only, (3) review full disassembly.
**Status:** decision record. Gate 5 stays **BLOCKED**; no Gate 4/Gate 5/MVP pass, no fixture freeze.

## 1. Decision

**Do not rebuild/replace the deployed Gate 4 `jobwrap` binary (`b232d60b…`) and do not choose
option 1 as the first move. Option 2 alone does not unblock Gate 5. Option 3 is not a decision
path; use disassembly only as needed for source recovery.**

**Take path 4: keep the old `jobwrap` for Gate 4; build a separate Gate 5 successor binary with a
fixed-argv `gate5` mode, bind Gate 5 evidence to the new binary hash, and leave the Gate 4
evidence chain untouched.**

- Old `/usr/local/sbin/jobwrap` (`b232d60b20b13dc696402112dd1d970c35b41a3ee720af32cfb2df396c621fa8`)
  remains the Gate 4 wrapper. Do not overwrite it.
- Reconstruct `jobwrap_v3.c` for maintainability/audit (documented as a derived reconstruction,
  not hash-equivalent source). This satisfies option 2's documentation goal but is **not** a
  Gate 5 unblock by itself.
- Build a **new** `jobwrap-gate5`/`jobwrap_v4` binary in the guest with fixed-argv `gate5` mode:
  fixed script path, fixed argv, hash-checked script, same uid 1003 / netns / no_new_privs /
  cap-drop / rlimit controls as the existing wrapper.
- Gate 5 record binds the **new** binary hash and invocation; Gate 4 record keeps `b232d60b…`.
  The two evidence chains are separate. No P4 re-run/re-sign is caused by adding the new binary.
- If the Gate 5 criterion is later interpreted as requiring the **deployed `jobwrap` itself** to
  expose `gate5` (same path/version), that is option 1: rebuild, replace, and re-run the Gate 4
  evidence with the new hash. That is a separate Lead decision after M3 confirms the client
  requirement; it is not authorized by this record.

## 2. Why not the original options

- **Option 1 as proposed:** changing `jobwrap` hash would invalidate the P4/fingerprint/SHA256SUMS
  chain; re-running Gate 4 is costly and unnecessary if Gate 5 can use a separate successor.
- **Option 2 alone:** source reconstruction does not create a `gate5` entry; Gate 5 stays blocked.
- **Option 3 alone:** more disassembly is not a deliverable; M3 already has symbols/structure.
- Docs `52` §3 and `44` also allow a documented fixed-argv equivalent under existing isolation
  controls; a separate successor with the same controls is the cleanest equivalent, provided the
  exact invocation and hash are recorded. Prefer that over replacing the Gate 4 binary.

## 3. Required deliverables

1. **M3:** preserve the old `jobwrap` and its hash; produce a derived `jobwrap_v3.c` reconstruction
   (clearly marked derived, no hash-equivalence claim); build the separate `jobwrap-gate5`
   successor with fixed-argv gate5 mode; publish the new binary hash + invocation + isolation
   controls; verify `GATE5_SCRIPT_SHA256` fails closed.
2. **M5:** keep `routeb/jobwrap_gate5.sh`'s `GATE5_SCRIPT_SHA256` validation; confirm the wrapper
   invocation against the new binary; no final MVP tag.
3. **M3/VMer:** run the fixed-argv Gate 5 probe in the guest only after the new binary/wrapper
   hashes are fixed; return raw output + `SHA256SUMS`; no direct host run.
4. **M4:** verify new binary hash/wrapper hash/probe raw evidence independently; record Gate 5
   rows PASS/FAIL/NOT VERIFIED; do not reuse Gate 4 hash as if it were Gate 5.
5. **Lead:** no Gate 5 pass until the new chain is verified; Gate 4 status unchanged.

## 4. Status

| Item | Status |
|---|---|
| Gate 4 formal | `NOT RUN`; old `jobwrap b232d60b…` and P4 evidence unchanged |
| Gate 5 | **BLOCKED**; needs separate fixed-argv gate5 successor (or documented equivalent) + verified wrapper hash |
| Gate 6 | V4 model-level pass per `docs/handoffs/71`; Gate 6 status separate |
| Fixture | **NOT FROZEN** |
| Final MVP tag | none; `mvp-integration-2026-10-31` remains old `bcf2537` |

## 5. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (Gate 5 path) | Lead | 2026-10-31 | path 4 adopted: separate Gate 5 successor; do not replace Gate 4 jobwrap |
| M3 (build/probe) | M3 | — | pending |
| M5 (wrapper) | M5 | — | pending |
| M4 (verification) | M4 | — | pending |
