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

1. `Allow a 5-byte relative redirect of call strcpy@plt at 0x401304 to reviewed added code and a branch back to 0x401309 (the instruction after the 5-byte call) on the valid path.`
2. `Allow up to 256 bytes of added x86-64 code in a gate-3-verified unused region of a loadable R-X segment reachable from 0x401304; zero bytes alone are not evidence.`
3. `Allow up to 64 bytes of added constant data holding exactly ERROR: input exceeds destination capacity plus LF inside the added-code region; RIP-relative references only.`
4. `Allow the invalid path to emit that data on fd 2 through the existing fprintf@plt and the existing stderr object, then exit 1 via exit_group without returning to main or writing stdout.`
5. `Allow extending the existing R-X PT_LOAD's p_filesz/p_memsz from 0x8e9 to 0x1000 (mapped end 0x402000) to cover the verified-unused tail ending at 0x401fff; record offset, vaddr, filesz, memsz, align; keep page congruence and no segment overlap.`
6. `Allow no new segment, dynamic import, GOT/PLT/relocation edit or permission broadening; only if the tail extension is rejected, allow one new R-X PT_LOAD with recorded headers.`

**Writer amendment (2026-10-22, after M5's measured CI probe).** The ELF already imports
`fprintf` and has the `stderr` COPY relocation; it imports **no** `write`, `fputs`, `fwrite`,
`exit`, `strlen`, or `strncpy`. The first persisted contract revision therefore sets
`allowed_calls = ("strcpy", "printLine", "fprintf")` for the measured mechanism. The raw
`write(2)` + `exit_group` pair remains an acceptable alternative only if the candidate
switches to it and the guest seccomp result is recorded. Never list a function the ELF
cannot reach; adding a new import is out of this profile. Note that `allowed_calls` is
consumed only by Route B validation; for Route A it is reviewed scope plus V1 evidence, not
validator enforcement.

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

## 5. What gate 3 must test and record (Member 4 since handoff 13; M3 supplies the guest)

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
7. **Writer/import evidence** — the committed ELF imports `fprintf` and has the `stderr`
   COPY relocation; it imports no `write`/`fputs`/`fwrite`/`exit`/`strlen`/`strncpy`
   (measured from `readelf --dyn-syms`/PLT, handoff 13 §3). Re-measure in the guest before
   relying on it. Adding a new import means editing
   `.dynsym`/`.dynstr`/`.rela.plt`/`.got.plt`/`.dynamic` plus versioning/RELRO: treat as out
   of this profile.
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

- **Member 4 (gate 3 evidence owner since handoff 13):** the evidence package result per
  handoff 11 §3 — `GATE 3 PASS` (all six items), `FAIL` (concrete failing fact), or
  `NOT VERIFIED` (missing evidence / missing isolation precondition). No `NEEDS SCOPE
  RULING` for scope, since this ruling settles it.
- **Member 5:** the contract revision with the six `authorized_edits` above (including the
  `fprintf` writer amendment) and a complete edit manifest, or approval of M4's
  supplementary manifest from the recorded recipe; keep gate 4 moving.
- **Member 3:** the guest and isolation evidence, guest access for M4, the canonical
  `original.elf` source confirmation, and the measured constraints appended to
  `route-a/docs/06-instruction-repair.md` §Investigation log.

---

## 9. Sign-off

- Lead: 2026-10-22, Option A.
- Corrections 2026-10-22 (after M5's measured CI probe): the valid-path return is
  **`0x401309`** (the 5-byte call occupies `0x401304`-`0x401308` inclusive); the measured
  writer is `fprintf@plt` + the existing `stderr` COPY relocation, so the contract revision
  authorizes `fprintf` in `allowed_calls`; gate 3 evidence ownership moved to M4
  (`handoffs/13-route-a-ownership-handoff.md`, ratified by the Lead).
- Member 4 (verification): reviewed 2026-10-22 — **agrees with Option A, rejects Option B**;
  amendments incorporated here: the oracle mirror is not an approved contract, the invalid
  path must terminate the process, syscall writes avoid a new dependency, `allowed_calls` is
  Route B enforcement, and a missing backend is an implementation gap (`inconclusive`), not
  `unsupported`.

**Confirmation log.** 2026-10-22 — ruling issued; strategy C is in Route A's range; oracle
unchanged; the first persisted contract revision must authorize the additions; gate 3
unblocked.

---

## 10. Gate-board status after this ruling (for M1's `main` README / any status page)

`origin/main` at `d493f74` (2026-10-22 16:48, written before this ruling) reports:

- Gate 3 (Route A) **NEEDS SCOPE RULING**;
- Gate 4 (Route B round trip) **NOT RUN**;
- "Gate 3 stays **UNSUPPORTED** until the LIEF/Patcherex2 layout audit exists; after that
  it is **CONDITIONALLY FEASIBLE**".

Correct labels from now on:

| Gate | Owner | Status after this ruling | Why |
|---|---|---|---|
| 3 — Route A patch feasibility | M5 → **M4** (2026-10-22, handoff 13) | **IN PROGRESS — CONDITIONALLY FEASIBLE** (work status; independent cave probe + formal six-case run pending; see §11; M5's CI probe 6/6 is supplementary only, handoff 13 §5.6) | The scope question is settled and the strategy-C measurement is done; `passed` / `failed` / `unsupported` remain invalid until the cave probe and six-case run produce evidence. `unsupported` needs the concrete placement/encoding fact, not an expectation |
| 4 — Route B unchanged round trip | M5 | **NOT RUN** (environment blocker) | Needs a disposable Ubuntu guest with JDK21 + Ghidra + Patcherex2 + clang and the isolation preconditions. It does **not** depend on gate 3 and can run in parallel once the environment exists. The environment work is approved in `10-v4-isolation-decision-record.md` (owner M3, 2026-10-23 18:00) |
| 5 — safe placement for both routes | M4 (Route A) + M5 (Route B) + M3 (guest) | pending | Needs gate-3 and gate-4 artifacts |
| 6 — verifier detects the original violation | M4 | partial | Concrete crash evidence accepted; symbolic half pending V4 |

Status-page rules: a gate is `passed` / `failed` / `not_run` / `unsupported` — never "not
pass"; a missing backend or audit is `not_run` (an implementation gap, not `unsupported`
and not a pass); and no gate may be pre-labelled `passed` or `unsupported` before its
evidence exists. The M1 README lines above should be rewritten to that effect.

---

## 11. Follow-up: gate 3 interim result and tail-cave mapping (2026-10-22)

Member 3's measurement (condensed): the 19-byte interval between the redirected
`call strcpy@plt` at `0x401304` and `ret` at `0x401317` has **zero spare bytes**; the PLT
exposes **no `strlen`/`strncpy`**; an **1815-byte tail cave** exists at `0x4018e9`-`0x401fff`;
strategy C is structurally feasible. However, the segment's file-backed end currently stops
at `0x4018e9` (`p_filesz`), so those bytes are not loaded from the file today; a runtime
probe must show whether the range is mapped and executable. If it is not, the fix is
extending `p_filesz`/`p_memsz` to `0x401fff` — a header change, **not** a new segment.
Until the cave check and the six-case run, gate 3 is `CONDITIONALLY FEASIBLE` only.

### 11.1 Status ruling

`CONDITIONALLY FEASIBLE` is accepted as a **work status, not a gate pass**. Gate 3 stays
open until all three exist:

1. the runtime cave probe (range mapped, R-X, file bytes present, an instruction there
   executes);
2. the six manifest cases actually run on the patched candidate and match the frozen oracle;
3. the added/edited bytes, the header change, and the detour are recorded in the edit manifest.

The fixture remains **NOT FROZEN**. "Conditionally feasible" must never be rendered as pass.
The full pass criteria are in `11-environment-evidence-confirmations.md` §3 (six required
items); this section only sets the interim status.

### 11.2 Tail-cave mapping is in scope

Extending the existing R-X `PT_LOAD`'s `p_filesz`/`p_memsz` so the verified-unused tail is
file-backed is a "necessary metadata change through a tested backend" (Tech Design §8) and is
**smaller than a new `PT_LOAD`**. It is authorized, subject to:

- same segment only, no new segment and no new page: `p_offset ≡ p_vaddr (mod page)` stays
  true, `p_filesz <= file size`, `p_memsz >= p_filesz`, end <= the next segment's start, no
  overlap;
- executable/read flags unchanged; NX, RELRO, canary, W^X preserved; no other header changed;
- the cave bytes must be proven unused: beyond the original `p_filesz` they are not mapped
  today, so verify that no section, symbol, relocation, unwind entry, or incoming edge
  references them, and record the filler bytes;
- record before/after program headers (`readelf -l` plus an independent LIEF view), the exact
  header fields changed, and the runtime probe output (mapping, permissions, byte comparison,
  executed instruction).

`§4.1` entries 5-6 were rewritten to this effect on 2026-10-22; the §4.1 text is authoritative.

### 11.3 Bounded-copy strategy is unavailable

`strlen` and `strncpy` are not in the PLT, so the guard computes the input length with an
inline loop and the repair stays strategy C. Do not add either function to `allowed_calls`
and do not add a new import (Tech Design §5/§8).

### 11.4 The six-case run is feasibility evidence, not acceptance

The six-case run is gate-3 evidence that the patched candidate behaves as the frozen oracle.
It is **not** V3 acceptance, not a V0/V3 pass, and not repair proof; the acceptance pipeline
still runs later. Because it executes a candidate, handoff 10 Decision 2's three isolation
preconditions apply (clean snapshot, job-time egress blocked, unprivileged user without
passwordless sudo). Record them with the run; without them the run is not evidence.

### 11.5 Gate 4

The `toolchain-v4-ready` snapshot is reported ready by M3. Remaining gate-4 blockers:
**M5's `routeb/` scripts** and team-guest access for a formal run (M5's gate 4 checklist
records no VM/snapshot/offline access). Target: M5 delivers the scripts or reports the
concrete blocker by **2026-10-23 12:00**; gate 4 then runs under the same isolation
preconditions. Gate 4 does not depend on gate 3.

**Confirmation log (follow-up).** 2026-10-22 — gate 3 recorded as CONDITIONALLY FEASIBLE
(work status, not pass); tail extension `p_filesz`/`p_memsz` to `0x401fff` authorized with
recorded headers and a runtime probe; no `strlen`/`strncpy` import; six-case run counts only
as gate-3 evidence; gate 4 blocker assigned to M5 (target 2026-10-23 12:00).

