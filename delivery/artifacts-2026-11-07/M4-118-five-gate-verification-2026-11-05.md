# M4 — record 118 five-gate verification (2026-11-05)

**Verifier:** M4. **Same-person limitation:** M4 verifier = Lead, same operator;
role-separated verification, not an independent two-person signature.
**Scope:** verification of the delivered evidence package against the five gates.
M4 did **not** re-execute the build or trigger in the guest; the gates are
satisfied by the hash-bound transcripts, as defined.

---

## 0. Verdict

**All five gates pass. Record 118 moves from
`REPORTED, NOT VERIFIED` to `VERIFIED (rebuild evidence package)`.**

| Gate | Result |
|---|---|
| 1. Dual manifests | **PASS** — `06-SHA256SUMS` 5/5, `SHA256SUMS` 10/10, full coverage |
| 2. `02-build.txt` | **PASS** — `exit=0`, `c9c2632e…23c9`, 25,344 B, warning recorded |
| 3. `04-trigger.txt` | **PASS** — 1 + 50 + 200 = 251 runs, one distinct observation |
| 4. `01-window-and-isolation.txt` | **PASS** — uid 11, 0 `.lck`, boot 21:43, `~/cwe416` absent |
| 5. `07-rebuild.json` | **PASS** — 21/21 `build_json` column matches; only `window.is_baseline` differs by design |

The status upgrade is **scope-limited**: it says the delivered evidence is
internally consistent, hash-bound, and conformant to the canonical T30. It is
not a claim that M4 rebuilt the binary.

---

## 1. Gate 1 — dual manifests

```text
06-SHA256SUMS   01..05                      5/5 OK
SHA256SUMS      00..07, README, collect.sh  10/10 OK
```

- `06-SHA256SUMS` is the guest-side transport manifest over `01`–`05`.
- `SHA256SUMS` is the host-side manifest over the whole directory except itself.
- `06-SHA256SUMS` is itself covered by `SHA256SUMS`, so the two form a complete
  chain: `SHA256SUMS` → `06` → `01`–`05`.

**PASS.**

---

## 2. Gate 2 — build transcript

```text
exit=0
sha256=c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
size=25344
original.c:36:5: warning: pointer 'data' used after 'free' [-Wuse-after-free]
```

- the printed digest and size match the canonical `original.elf` blob (§6);
- the four input hashes match `build.json#fixture` and the canonical inputs;
- the `-Wuse-after-free` diagnostic is recorded, not suppressed.

**PASS.**

---

## 3. Gate 3 — trigger transcript

```text
single   : exit_code=0 stdout_hex=05040a stdout_len=3 stderr_len=0
50x      : exit_code=0 stdout_hex=05040a stdout_len=3 stderr_len=0
200x     : exit_code=0 stdout_hex=05040a stdout_len=3 stderr_len=0
ASLR on  : 10 runs, 10 distinct stdout values
```

- `1 + 50 + 200 = 251` runs;
- one distinct observation under `setarch -R`;
- the ASLR-on contrast shows why `setarch -R` is required (heap residue).

**PASS.**

---

## 4. Gate 4 — baseline-clean window

Two views, because a guest cannot see its own snapshot uid or `.lck` files:

| Fact | Source | Value |
|---|---|---|
| `snapshot.current` | `00-window-host.txt` (host re-read) | `"11"` |
| uid → name | `00-window-host.txt` | `snapshot7.uid = "11"` = `gate4-harness` |
| lock directories | `00-window-host.txt` | **0** |
| no VM running | `00-window-host.txt` | `Total running VMs: 0` |
| boot time | `01-window-and-isolation.txt` (guest) | `system boot 2026-11-05 21:43` |
| uptime at capture | `01` | `up 2 minutes` |
| `~/cwe416` | `01` | **absent** |
| home contents | `01` | `D`, `evaluator`, `repair-input`, `route-a` |
| moment-of-revert values | `07-rebuild.json#window` | revert exit 0, `snapshot.current "11"`, 0 locks |

**Limitation, stated not hidden:** `00` is a read taken **after** the window
closed, not a sample at the moment of revert. What it establishes is that
nothing has moved since. The moment-of-revert values are those recorded in `07`;
`01` ties the build to the 21:43 boot. Together they support the baseline-clean
claim.

**PASS, with the post-window re-read limitation.**

---

## 5. Gate 5 — conformance against canonical T30

Independent comparison of `07-rebuild.json`'s 21 conformance rows against the
canonical `T30/build.json` at `c274893`:

```text
rows: 21   matched: 21   mismatches: []
verdict differs: ['window.is_baseline']
```

- every `build_json` column value matches the canonical record;
- the single `differs` verdict is `window.is_baseline`: canonical **false**
  (uid 14), this run **true** (uid 11) — the purpose of the exercise;
- `07`'s own summary (`tabulated 21, match 20, differs 1`) is accurate.

**PASS.**

---

## 6. T30 canonical path and `c274893` blob

| Check | Result |
|---|---|
| commit `c274893` | `c274893d3cc495fd8c1cbc9e28847b565b341f7e` — `feat(t30): CWE416 fixture built in the guest, with a deterministic trigger` |
| canonical path | `docs/handoffs/evidence/T30/` — **11 files** |
| `build/original.elf` blob | SHA-256 `c9c2632e…23c9`, size **25,344** |
| `build/build.sh` blob | SHA-256 `6e33c825…30a9` |
| `build/original.c` blob | `fa84a6bb…7f42e` |
| `build/harness.c` blob | `cef8f533…63a9` |
| `build/trigger.sh` blob | `01cce3c7…6409` |

All four source/script blobs match the inputs declared in
`01-window-and-isolation.txt` and used by `02-build.txt`. **PASS.**

### 6.1 Canonical vs the earlier M3 ZIP

The `M3-T30-CWE416-fixture.zip` in this workspace is an **earlier packaging**:

| File | M3 ZIP | canonical `c274893` |
|---|---|---|
| `build.sh` | `53bc605f…` | **`6e33c825…`** |
| `build.json` | `327b4cdd…` | **`0d143db3…`** |
| `original.c` / `harness.c` / `original.elf` | same hashes | same hashes |

The canonical `build.json` adds `build.build_script.invocation`,
`build.script_output_contract`, and `output.reported_by_script`; the core
artifact identity is unchanged. **Record 118 used the canonical build.sh
(`6e33c825`), not the ZIP's.** The ZIP is superseded for the build script and
must not be used as the T30 recipe baseline.

---

## 7. Status and scope

```text
118: REPORTED, NOT VERIFIED -> VERIFIED (rebuild evidence package)
```

What this means:

- the five gates pass on the delivered, hash-bound evidence;
- the rebuild is conformant to the canonical T30 at `c274893`;
- the window was baseline-clean (with the post-window re-read limitation).

What it does **not** mean:

- M4 did not rebuild the binary or re-run the trigger in the guest;
- no V0–V5 gate is promoted (no candidate, no contract);
- T8.3 remains blocked.

---

## 8. Boundaries

| Boundary | Status |
|---|---|
| Record 91 | **unchanged** |
| Same operator | M4 = Lead; role-separated, not an independent two-person signature |
| Review items 9/10/11/12 | **separate work** |
| Merge / tag / live success | **none** |
| V0–V5 / T8.3 | **not promoted** |

---

## 9. Evidence

| File | Content |
|---|---|
| `M4-118-and-schema-consistency-evidence-2026-11-05.txt` | commands and outputs for gates 1–5, the canonical blob checks, and the intake probe |
| `probe_conformance.py` | independent 21-row comparison |
| `M1-T30-118-evidence-2026-11-05/t30-rebuild-2026-11-05/` | the evidence package |
| `M1-T30-118-evidence-2026-11-05/VERIFICATION.txt` | M1's own verification notes |
