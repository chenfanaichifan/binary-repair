# 09 — Ruling: Route A may add code and data (strategy C)

**Recipient:** Member 3 (Route A), Member 5 (gate 3), team
**From:** Lead, with Member 4 (verification slice) review
**Date:** 2026-10-22
**Ruling:** **Option A. Strategy C is inside Route A's allowed range.** Gate 3 is unblocked.
**Basis:** PRD F2 (lines 67-81); Tech Design §5 line 100 ("No new external library dependency
in replacement code; allow only explicitly resolved existing calls") and §8 "Added-code
policy" (lines 205-209); `verification-design.md` §4.4 (frozen oracle) and §2.1 (outcomes);
`route-a/docs/06-instruction-repair.md` strategy C.
**Deadline met:** recorded before the 2026-10-22 18:00 deadline; no `NEEDS SCOPE RULING`
suspension is needed.

---

## 1. Question being ruled on

Member 3 measured the vulnerable site in the public fixture ELF
(`CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b`, original SHA-256
`aa428157...`):

| Fact | Measured value |
|---|---|
| target sink | `..._51b_badSink` @ `0x4012b0`, signature `void badSink(char *data)` |
| vulnerable copy | `call strcpy@plt` @ `0x401304`-`0x401308`, no length check before it |
| live state at the call | `rdi = &dest`, `rsi = data`, `rdx = data`, `rax = &dest` |
| available scratch registers | `rcx`, `r8`-`r11` — all caller-saved |

The frozen invalid-input contract requires `return_code = 1`, `stdout = ""`, and
byte-exact `stderr = "ERROR: input exceeds destination capacity\n"` (42 bytes), with no
crash (`verification-design.md` §4.4). To produce that from an instruction-level patch you
need added string bytes, a write to fd 2, a length test, and process termination; a few
substituted bytes cannot do it.

**The question:** does Route A's allowed range include adding data, calling a writer, and
placing added code (a cave or a new mapped region)?

Two corrections to the original framing, both material:

- **The invalid path must terminate the process, not "set a return code".** `badSink`
  returns `void`; if it returned normally, `main` would return 0. The added code must call
  `exit`/`exit_group` (or `exit@plt` if imported) with status 1.
- **A PLT/writer call is an option, not a requirement.** Tech Design §5 forbids a new
  external library dependency, and §8 rejects unresolved relocations. A raw `write` (fd 2,
  the string, 42) followed by `exit_group(1)` needs no import and no relocation change, so
  it is the lower-risk mechanism. A libc writer is acceptable only if the ELF already
  imports it (gate 3 must measure this; no ELF/dynsym/PLT evidence is committed today).

---

## 2. Ruling

**Yes — Option A.** Strategy C is not a scope violation. It is exactly the fallback the
project design provides for Route A:

1. **PRD F2** (Route A acceptance criteria): *"It may use another suitable location when
   the original location is too small. It records edited regions, added code, necessary
   redirection, and structural changes."*
2. **Tech Design §8, "Added-code policy":** *"Both routes may add code elsewhere. Prefer
   reviewed existing space; zero bytes alone do not establish unused executable storage.
   Otherwise allow a new mapped RX region and necessary metadata changes through a tested
   backend. Record every changed file interval, virtual mapping, header, relocation, and
   detour."*
3. **Member 3's own work item** (`route-a/docs/06-instruction-repair.md`) lists strategy C
   ("redirect to added code") as a Route A strategy to investigate.
4. **Tech Design §5 line 100** permits replacement code with "only explicitly resolved
   existing calls" — a raw syscall resolves nothing new; an existing PLT import is an
   explicitly resolved existing call.

Route A stays distinct from Route B on provenance, not placement: Route A's added
instructions are reviewed/deterministic template output; Route B's are compiler output from
recovered C. Both routes may place code elsewhere, so F5 still compares two different
repair methods.

**Still may end `unsupported`.** The ruling removes the scope objection only. If gate 3
finds no safe encoding, no verified-unused space, an unmappable segment, broken
relocations, or an unprovable register/flag state, the honest route outcome is `unsupported`
with the concrete limiting fact (`verification-design.md` §2.1). That is not a reason to
change the oracle.

---

## 3. Why Option B is rejected

Changing the invalid-path contract to "stderr empty" or "non-empty but not byte-asserted"
would:

- **weaken a frozen oracle to fit one route's implementation difficulty**, which
  `AGENTS.md` forbids ("Never weaken a test, oracle, or verification gate to get a green
  result");
- **break the F5 cross-route comparison** that §4.4 exists to protect: Route A and Route B
  must produce the same observable behaviour or one V3 assertion set cannot cover both;
- **change product behaviour for route convenience**, when the contract's invalid path is a
  reviewed product requirement, not a Route A detail.

Option C in the query ("keep exact stderr, accept Route A may be unsupported") is **not an
alternative to A** — it is A's contingency outcome if implementation fails. We do not
pre-empt it by editing the contract now.

---

## 4. Three layers, and what actually changes

| Layer | Status | Consequence |
|---|---|---|
| Route category (design) | **Allowed** — see §2 | Gate 3 may investigate strategy C now |
| Reviewed contract | **No fixture contract is persisted yet.** The only committed contract value is the test-side oracle mirror in `tests/test_fixture_v3_manifest.py` on `origin/main` (`authorized_edits = ()`, `allowed_calls = ("strcpy", "printLine")`); that mirror is not the approved contract | The **first persisted contract revision** must carry the authorizations in §4.1 before a strategy-C candidate is frozen/approved. There is no existing freeze record to re-open and no manifest change |
| Product pipeline | **Gap** — candidate validation only accepts reviewed templates (`bounded-copy-guard`, `guard_capacity`) and `DEFAULT_ALLOWED_CALLS = ()` | A reviewed Route A template is needed to *express* the candidate; implementation work, not a scope issue |

### 4.1 Contract revision (M5 owns; M4 confirms; Lead approves)

The oracle constants are **unchanged**:

| Constant | Frozen value |
|---|---|
| `dest_capacity_bytes` | 50 |
| `max_valid_input_bytes` | 49 (capacity includes terminator) |
| `invalid_exit_code` | 1 |
| `invalid_stdout` | `""` |
| `invalid_stderr` | `"ERROR: input exceeds destination capacity\n"` |

Only `authorized_edits` and `allowed_calls` are extended. Proposed `authorized_edits`
entries (each <=300 printable ASCII characters, per `SecurityContract` validation; the
byte bounds below are review bounds, and gate 3 may report that a larger bound is needed):

1. `Allow a 5-byte relative redirect of call strcpy@plt at 0x401304 to reviewed added code and a branch back to 0x401308 on the valid path.`
2. `Allow up to 256 bytes of added x86-64 code in a gate-3-verified unused region of a loadable R-X segment reachable from 0x401304; zero bytes alone are not evidence.`
3. `Allow up to 64 bytes of added read-only data holding exactly ERROR: input exceeds destination capacity plus LF, RIP-relative references only.`
4. `Allow the invalid path to write that data to fd 2 and exit 1 without returning to main or writing stdout.`
5. `Allow no new PT_LOAD, dynamic import, GOT/PLT/relocation/header edit or permission change without a later reviewed revision.`
6. `Only if gate 3 rejects the cave: allow one new R-X PT_LOAD, page-congruent offset/vaddr, fixed non-PIE address, no overlap, recorded headers.`

`allowed_calls` stays `("strcpy", "printLine")` for a syscall-based repair (syscalls are not
"calls" and are covered by entry 4). Add a writer — exactly `write`, `fputs`, or `fwrite`,
plus `exit` if used — **only if gate 3 confirms that import already exists**; never list a
function the ELF cannot reach. Note that `allowed_calls` is consumed only by Route B
validation; for Route A it is reviewed scope plus V1 evidence, not validator enforcement.

Effects of the revision: it changes the canonical contract payload and therefore
`reviewed_scope_sha256` — a new contract revision and a new approval are required, which is
the normal approval flow, not a re-freeze of the test manifest. `valid.json` / `invalid.json`
and the manifest set hash are **not** changed.

### 4.2 Implementation gap

The Route A candidate payload stays schema-compliant: a new reviewed template (for example
`guard-and-reject-stderr` with a capacity parameter and a fixed error line) is a
`template_id` + `parameters` entry in `DEFAULT_TEMPLATES`; no candidate-schema change and no
`allowed-mappings` field is needed. Placement is server-reviewed and hash-bound; V1 enforces
it. The model still proposes only a reviewed template; the added code/data is produced
deterministically by the template, which keeps Tech Design §8's "the first implementation
does not accept arbitrary machine-code plans" rule intact.

---

## 5. What gate 3 must test and record (Member 5)

Gate 3 answers feasibility, not acceptance. Record each item with a command and an
evidence file:

1. **Site and redirect** — 5-byte `call` at `0x401304`, rel32 reach to the added code, no
   other incoming edges to the displaced interval, `rdi`/`rsi`/`rdx`/`rax` live,
   `rsp` alignment at entry; length obtained by an inline compare loop (no new import) or a
   confirmed existing `strlen`.
2. **Cave proof** (preferred placement) — verified unused: no incoming edges, no
   relocations or symbols pointing at it, not covered by unwind info, inside a loadable
   R-X segment, bytes unchanged from the original; zero bytes alone are not evidence.
3. **New RX mapping** (only if the cave is rejected) — headers, flags, offset, vaddr,
   filesz, memsz, align; page-congruent; fixed non-PIE address; no overlap; W^X preserved;
   LIEF load map plus independent `readelf`; section-only changes rejected.
4. **Added data** — offset, vaddr, length, exact bytes, read-only access, RIP-relative
   references only.
5. **Detour** — source/target, instruction boundary, displacement, displaced instruction
   (if any) and restoration; changed bytes reported separately from added bytes.
6. **Termination** — invalid path writes the exact 42 bytes to fd 2, exits 1 via
   `exit_group` (or `exit` import), never returns to `main`; stdout empty; no crash. A
   direct syscall may be blocked by guest seccomp — record the guest policy.
7. **Writer/import evidence** — inspect `dynsym`/PLT for `write`/`fputs`/`fwrite`; no ELF,
   dynsym, or PLT evidence is committed on any ref today, so this must be measured. Adding
   a new import means editing `.dynsym`/`.dynstr`/`.rela.plt`/`.got.plt`/`.dynamic` plus
   versioning/RELRO: treat as out of this profile.
8. **CET** — "CET enabled" is an unverified assumption; record compile-time `ENDBR64`
   separately from runtime IBT and shadow-stack enforcement. A direct rel32 branch needs no
   landing pad; an indirect entry does; a mismatched `ret` breaks under shadow stack.
9. **Protections** — NX, RELRO, canary preserved; no writable-executable page; no
   permission broadening.
10. **Edit manifest** — complete changed/added intervals, mappings, headers, relocations,
    detours, template id, imports vs the original PLT, guest/kernel/CET facts.

Outcome recording:

- **Feasible** → advance to the reviewed template + contract revision, then a candidate.
- **Unsupported** → only when a required placement/encoding/interface capability is outside
  the supported profile; record the concrete limiting fact. That label is decided by the
  acceptance engine from the route's evidence, not by the reporter.
- **Missing backend/tooling** → an implementation gap, not `unsupported`: the obligation is
  `not_run`, which yields `inconclusive`. It is never counted as a pass and never as proof
  of infeasibility.

---

## 6. If gate 3 ends unsupported

The MVP requires both routes to succeed (PRD line 206; Tech Design §9 acceptance rules).
An `unsupported` Route A therefore means the MVP is not met for this fixture. The team then
decides **once, explicitly**, among: an alternate placement inside the same authorization,
or a different public fixture whose original already has a stderr write path (preferred
over weakening the oracle). Any contract change is a full-team re-freeze. A member must not
re-freeze unilaterally, and V3 keeps asserting the exact bytes until such a decision is
recorded.

---

## 7. What this ruling does not change

- V3 still asserts exit 1, empty stdout, and byte-exact stderr on both routes.
- The V0 expectation for the original stays 4/6 (it SIGSEGVs on invalid input).
- No manifest file, manifest hash, or manifest set hash changes.
- No change to the six outcome labels or to V0-V5 kinds.

---

## 8. Reply requested

- **Member 5:** gate 3 result as `FEASIBLE` (with placement and writer recorded) or
  `UNSUPPORTED` (with the concrete fact) — no `NEEDS SCOPE RULING` for scope, since this
  ruling settles it.
- **Member 3:** append the measured constraints and the chosen strategy to
  `route-a/docs/06-instruction-repair.md` §Investigation log, and confirm the instruction
  interval and added-byte plan to Member 5.

---

## 9. Sign-off

- Lead: 2026-10-22, Option A.
- Member 4 (verification): reviewed 2026-10-22 — **agrees with Option A, rejects Option B**;
  amendments incorporated here: the oracle mirror is not an approved contract, the invalid
  path must terminate the process, syscall writes avoid a new dependency, `allowed_calls` is
  Route B enforcement, and a missing backend is an implementation gap (`inconclusive`), not
  `unsupported`.

**Confirmation log.** 2026-10-22 — ruling issued; strategy C is in Route A's range; oracle
unchanged; the first persisted contract revision must authorize the additions; gate 3
unblocked.
