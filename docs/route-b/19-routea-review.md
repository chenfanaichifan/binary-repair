# routea review — canonical contract and schema-2 manifest

**Reviewed:** main `c1b973d` (M5-owned `routea/`), 2026-10-22.

## Reviewed changes

| File | Change | Verdict |
|---|---|---|
| `routea/worker.py` | `EditManifest` now emits schema 2: `displaced`, `added`, `intervals`, `header_changes`, `writer`, `termination`, `tool_versions` | OK; no ELF behavior change |
| `routea/cave.py` | schema-2 manifest population; header offsets/old-new sizes; added code/data hashes; call-site `original_hex`; `write(2)`/`exit_group(1)` declared | OK; candidate bytes unchanged (`c4a159…`) |
| `routea/cave.py` | `_phdr_offset` helper for program-header file offset | OK; tested |
| `routea/out/edit-manifest.json` | regenerated schema 2 | OK |

Tests: `tests/test_routea_cave.py`, `tests/test_routea_manifest.py`,
`tests/test_fixture_contract.py` — full suite **162 passed, 2 skipped**.

## Not reviewed

M4's design branch `member-4-routea-gate3` @ `7977bac` is **not fetchable**
(`git cat-file` fails; no remote ref). Its `routea/audit.py`, `cave.py`,
`tests`, and `contract.route-a-v1.json` are not merged or reviewed. M4 should
push that branch or hand over a patch; until then no review claim is made.

## Evidence policy

- Sole gate-3 candidate: `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`;
- M4's earlier `f3cb9cbb…` (fprintf writer) is superseded; not a second evidence;
- no M5 push will add another candidate or a second contract hash;
- canonical contract: `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`;
- handoff zip: `dist/m5-routea-c4a159-2026-10-22.zip`, SHA-256
  `957d73d4284a4e5ced27de451bacdfe8956751232bd4a1fa5aa6454dccdc108e`.

## Gate 3 impact

Handoff 11 §3 item 2 is now complete (schema-2 displaced/added/header fields).
Item 3 still needs LIEF/NX/RELRO/canary views; item 4 needs the reverted-snapshot
6/6; item 5 isolation is missing; item 6 needs the formal bundle. Gate 3 remains
**CONDITIONALLY FEASIBLE**.
