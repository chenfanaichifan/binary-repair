# Security: API key rotation and secret-scanning record (2026-11-17)

Status: P0 remediation record. Owner: M4 (security/backup/governance).
Scope: every provider credential that appeared in plaintext in chat/session logs
or in workspace materials is treated as **already compromised** and must be
rotated/revoked. This document intentionally contains **no key values, no key
prefixes and no key fragments**; every hit below is reported by provider,
location type and (where applicable) masked scanner output only.

Policy reference: master report section 1.5.1 and 6.2 B9 (P0 security), and the
repository rule "no plaintext keys in repo/docs/evidence".

## 1. Compromised credential inventory (values never recorded)

| # | Provider | Purpose in project | Env var / storage name | Where it appeared (location type) | State |
|---|---|---|---|---|---|
| K1 | SiliconFlow CN (api.siliconflow.cn) | CN multi-model probes/benchmark (Qwen3-8B / Qwen2.5-7B-Instruct) | `SILICONFLOW_API_KEY` | 1) chat/session logs on the authoring host (DSH session store); 2) operator shell environment during runs | COMPROMISED - rotate |
| K2 | SiliconFlow International (api.siliconflow.com) | international provider identity probes | `SILICONFLOW_API_KEY` (intl base URL) | chat/session logs; probe runs recorded in evidence (key itself not in evidence) | COMPROMISED - rotate (account also reports HTTP 402 insufficient balance) |
| K3 | Alibaba Cloud Bailian / DashScope | Qwen provider arm (`BINARYREPAIR_PROVIDER=dashscope`) | `DASHSCOPE_API_KEY` | chat/session logs; planning docs reference the key as "to be configured" (no value in repo) | COMPROMISED - rotate |
| K4 | DeepSeek platform (api.deepseek.com) | primary repair model (deepseek-chat / flash) and GUI assistant provider | `DEEPSEEK_API_KEY`, `BINARYREPAIR_ASSISTANT_PROVIDER_KEY`, GUI key store `binary-repair-gui/var/assistant.key` | 1) chat/session logs; 2) local GUI key store file on the authoring host (mode 0600, git-ignored, 55-byte file present at audit time) | COMPROMISED - rotate + replace GUI-stored key |

Notes:
- No fifth-provider key was evidenced. SiliconFlow international was blocked by
  account balance (HTTP 402); DashScope had no key configured in the gated
  provider matrix. Only the four credential slots above need disposal.
- The repository itself, its docs, evidence files and app/scripts were scanned
  clean (section 3). The leak surface is the local session/chat history plus the
  operator-side environment and the local GUI key store, not the git tree.

## 2. Rotation / revocation runbook (owner or user must execute)

All four items require console access and are therefore **blocked_by=owner**;
no automated rotation is possible from this workspace (no provider admin
credentials, and creating/rotating keys is explicitly out of scope for agents).

For each provider: revoke first (assume compromise), then issue one new key,
store it only in the operator environment or the GUI store, and re-run the
minimal identity probe.

### K1/K2 SiliconFlow (CN + International)
1. Sign in to the SiliconFlow console for the affected region and open the
   account's API key page (Console -> Account / API Keys).
2. Revoke every key created before 2026-11-17; do not keep "unused" legacy keys.
3. Create one replacement key per region (CN and International accounts are
   separate; rotate both if the same key was pasted into either console).
4. CN replacement: export `SILICONFLOW_API_KEY` locally, `BINARYREPAIR_PROVIDER=siliconflow`,
   base URL `https://api.siliconflow.cn/v1`.
5. International replacement: same variable, intl base URL
   `https://api.siliconflow.com/v1`; note the account currently returns HTTP 402
   (insufficient balance), so identity-only probing is expected until topped up.
6. Verification (operator, one-off, not committed): run the repository's
   provider identity probe (or a one-line `GET /v1/models`) with the new key,
   confirm the response arrives, then delete the throwaway shell/script and the
   history entry that contains the test invocation. Do not paste the key into
   any tracked file, evidence artifact, screenshot or chat message.
7. After verification, remove the old key from the local shell profile / `.env`
   (if any); `.env` must stay untracked (it is in .gitignore).

### K3 Alibaba Cloud Bailian / DashScope
1. Sign in to the Alibaba Cloud Bailian (Model Studio) console for the account.
2. Go to the API-KEY management page, revoke all pre-2026-11-17 keys.
3. Create one replacement key; export `DASHSCOPE_API_KEY` only in the local
   operator environment and `BINARYREPAIR_PROVIDER=dashscope`.
4. Verification: minimal `/compatible-mode/v1/models` (or `/v1/models`) call,
   confirm 200 and expected model identity; destroy the test script and its
   history immediately afterwards.

### K4 DeepSeek
1. Sign in to platform.deepseek.com -> API keys; revoke every pre-2026-11-17 key.
2. Create one replacement key for the CLI/benchmark path (`DEEPSEEK_API_KEY` or
   `BINARYREPAIR_ASSISTANT_PROVIDER_KEY`).
3. **Replace the GUI-stored key**: the local key store is
   `binary-repair-gui/var/assistant.key` (0600, git-ignored). Either clear it
   (delete the file; it is recreated when a key is saved) and save the new key
   through the operator UI, or overwrite it through the UI save flow. Do not
   copy the file into any backup, chat, report or artifact bundle.
4. Verification: run one minimal assistant request through the GUI/CLI with the
   new key, confirm a normal model response and that
   `var/model_calls.jsonl` (if enabled) contains no key material; then close the
   session. Keep `BINARYREPAIR_STORE_RAW=0`.
5. Confirm no billing alarms from the revoked keys (DeepSeek console usage page).

### Cross-provider clean-up after rotation
- Purge pasted keys from local chat/session history (the DSH session store under
  the user home, ~158 MB at audit time). These logs are outside the repository
  and were not copied into it; deleting them is a user decision because they
  also contain the project's session history used for the handoff review.
- Search local shell history and any local `.env` for the revoked names and
  remove the lines.
- Treat any screenshot, PDF or chat export that showed a key as compromised
  material: do not publish it; regenerate if it is needed for a deliverable.

## 3. Secret-scan record (masked, reproducible)

Tool: `tools/handoff/scan-secrets.sh` (workspace tool area). It prints masked
locations only, never values; exit 1 means candidates found.

### 3.1 Repository docs / scripts / app / review (specified P0 coverage)
```
tools/handoff/scan-secrets.sh binary-repair-gui/docs binary-repair-gui/scripts binary-repair-gui/app review/
=> total candidates: 0 ; exit code 0
log: .tmp/handoff/m4/scan-secrets-main.log
```

### 3.2 Whole repository tree (extended, masked)
```
SHOW_CONTEXT=1 tools/handoff/scan-secrets.sh binary-repair-gui
=> total candidates: 12 ; all in tests/ synthetic fixtures ; exit code 1
log: .tmp/handoff/m4/scan-secrets-fullrepo.log
```
All 12 hits are unit-test fixtures, not live credentials (candidate lengths
19-33 chars; live provider keys seen in this project are >45 chars; contexts are
`raw_key = ...`, `save_key(...)`, `setenv(...)` test setup). Masked hit list
(file:line + tool-masked token):
```
tests/test_assistant_key_store.py:14  sk-te...ef
tests/test_assistant_key_store.py:37  sk-st...89
tests/test_assistant_key_store.py:44  sk-ab...34
tests/test_assistant_key_store.py:57  sk-ab...op
tests/test_assistant_key_store.py:63  sk-st...ef
tests/test_assistant_key_store.py:64  sk-st...ef
tests/test_model_payload.py:24        sk-te...ef
tests/test_assistant_llm.py:616       sk-SE...AK
tests/test_assistant_key_api.py:24    sk-ap...ef
tests/test_assistant_key_api.py:54    sk-pr...89
tests/test_connectors.py:69           sk-sh...ar
tests/test_connectors.py:72           sk-sh...ar
```
Recommendation (non-blocking, follow-up for the owning code owner): build these
fixtures from an obviously fake marker (e.g. an `sk-test-...` string) so that a
future strict CI scanner can run without an allowlist. Do not "fix" the current
release gate by adding these files to a broad ignore list.

### 3.2b Re-scan after the docs relocation (HEAD ae89f88)
After the Lead moved the Chinese delivery documents to `delivery/zh/`, the whole
repository was re-scanned (this scanner does not skip `delivery/zh`, so the
copied Chinese docs were covered): same 12 synthetic test-fixture candidates,
0 real credentials, 0 known-value hits. Log:
`.tmp/handoff/m4/scan-secrets-postmove.log`.

### 3.3 Workspace materials (training/handoff exports; extended)
```
tools/handoff/scan-secrets.sh handoff/BinaryRepair-Linux-Handoff-2026-11-13-v7 handoff/final-verification-2026-11-13 WeChat-Share binary-repair-gui/README.md binary-repair-gui/DELIVERY.md binary-repair-gui/CONSOLIDATION.md binary-repair-gui/START-HERE.md binary-repair-gui/.env.example binary-repair-gui/docs/handoff
=> total candidates: 13 ; all synthetic fixtures quoted from the same tests (the
   audit-evidence.md hit is the audit document quoting the fixture) ; exit 1
log: .tmp/handoff/m4/scan-secrets-extended.log
```
No real credential was found in the workspace materials that were scanned.

### 3.4 Scanner hardening (tool repair, performed by M4)
The local scanner previously kept two known (already-compromised) demo values
inline as plaintext in its allowlist. They are now stored **only as SHA-256
digests**, so the tool itself no longer contains key material. A new
`SHOW_CONTEXT=1` mode prints the matching source line with the secret replaced by
`<REDACTED>`, which lets a reviewer classify hits without exposing values; a
`REPORT_KNOWN=1` mode reports previously allowlisted values by digest prefix
only. Default behavior and exit codes are unchanged (check-env still passes).

### 3.5 Not run (explicit)
- `handoff/archive` (workspace history archive, ~1.5 GB): not exhaustively
  text-scanned; most members are binary/compressed archive payloads. It is
  local material outside the delivery tree and must never be published; rotation
  of K1-K4 makes any historic copy worthless.
- User-home DSH session store (~/.dsh/sessions, ~158 MB): not scanned or copied;
  it is outside the repository and outside this task's write scope. It is the
  primary leak location for K1-K4 and is covered by the rotation actions above.
- Live provider APIs: not called (no valid/authorized keys; live model calls
  would cost money and were not authorized).

## 4. Prevention: recommended controls (proposal only; CI not modified)

Draft for the Lead to apply (full patch sketch in
`ci-security-proposal-2026-11-17.md`):
1. Add a CI job running the repository-owned scanner (mirror of
   `tools/handoff/scan-secrets.sh` with the SHA-256 allowlist) over tracked
   files, failing the build on any candidate; keep the allowlist to digests.
2. Add a pre-commit hook (same script, staged files only) so a key is rejected
   before it reaches a commit; make the hook opt-in for the first release and
   documented in `CONTRIBUTING.md`.
3. Keep `.env.example` placeholders clearly fake and non-matching
   (e.g. `sk-your-key-here` is fine); never allow a real-value test fixture.
4. Rotate on any suspected exposure; store keys only in the operator
   environment or the 0600 GUI store; never in evidence, prompts or logs.
5. Add the scan command to the release checklist
   (`release-evidence-procedure.md` is owned by the release owner, not M4).

## 5. Status summary

- P0-1 scan: **done** (repo clean in the specified scope; synthetic fixtures
  itemized above).
- P0-1 rotation: **blocked_by=owner / user** (console access; K1-K4 + GUI store).
  Lead decision (2026-11-16): rotation stays an owner/user action; M4 delivers the
  inventory and runbook only, and must not claim it as done until the owner
  records completion.
- Scanner plaintext allowlist: **fixed** (digests only; check-env re-verified).
- No key value, prefix or fragment is recorded in this document, in the repo,
  or in the M4 report.
