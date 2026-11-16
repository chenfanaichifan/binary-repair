# GUI end-to-end evidence — capacity-check quick repair (marcx + PoC manifest)

Date: 2026-11-14 (Asia/Shanghai).  Host: macOS arm64 + running Lima VM
`binaryrepair` (aarch64 Ubuntu; x86_64 target executed through the guest's
qemu-user/binfmt).  GUI: `app.main:app` under uvicorn on a spare loopback port.
Browser: Google Chrome headless driven over the repo's CDP helpers
(`tests/e2e/cdp.py`, `tests/e2e/conftest.py`).

This directory records one **real** end-to-end run of the task-4 acceptance
criterion: upload the marcx fixture plus the PoC/regression manifest through the
`/agent` quick-repair card, let the real backend produce and verify a capacity
candidate, and confirm the page renders the passed check table and a download.

## Inputs

| Input | Value |
|---|---|
| Original binary | `fixtures/elf/vuln-capacity-confusion-x86_64.elf` (marcx), sha256 `72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5` |
| PoC/regression manifest | `fixtures/poc/marcx-capacity.json`, `schema_version: 1`, 4 `poc` + 10 `regression` cases, archives embedded as base64 `files` |
| Candidate produced | sha256 `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2` (16-byte rewrite at file offset `0x20d9`, plus the recorded `.rodata` message alignment) |
| Runner | Lima VM `binaryrepair`, `limactl`; tier `emulated_run` |

## Command

```bash
.venv/bin/python artifacts/marcx-capacity-gui-2026-11-14/verify_gui_capacity.py
```

The script starts the real app (`start_gui`, mock controller backend, isolated
`BINARYREPAIR_DATA_DIR`, fixed e2e session token), POSTs the same files directly
to `/api/binary/repair-review` (saving `repair-review-response.json`), then drives
Chrome: `/agent/new?plan=fixture` -> upload marcx via
`[data-testid="agent-file-input"]` -> three guided steps -> review card -> choose
`marcx-capacity.json` in `[data-testid="agent-poc-manifest"]` -> click
`[data-testid="agent-quick-repair"]`.  It fails non-zero unless
`decision.success === true`, `patch.capacity` / `runtime.evidence` /
`runtime.tier` / `runtime.contract` are all `passed`, and the download link is
rendered.

Note on the page banner: the URL uses `?plan=fixture` only so the guided plan can
be reached offline; the repair request, candidate bytes and runtime evidence are
**not** fixture data — they come from the real local backend and the real Lima
guest execution.

## Result (2026-11-14 15:38 local)

Direct API response (`repair-review-response.json`):

- `decision.success = true`, `outcome = success_within_scope`,
  `reason = "all_required_checks_passed"`,
  `evidence_sha256 = 7c826283e67c553e4263cd941b05e337752a9127ca02fc92145ea4cd7d240371`.
- `report.strategy = "capacity"`, `report.mode = "capacity-check"`,
  `report.disposition = "verified_patch"`, `report.status = "patched"`,
  `patched_sha256 = 93e27f2f…b033a2`.
- `verification.gate`: `required_checks = 14`, `required_not_run = 0`,
  `success = true`; scope `runtime_tier = "emulated_run"`,
  `runtime_verdict = "pass"`.

All 14 required checks `passed`:

```text
format=passed  candidate.present=passed  candidate.identity.original=passed
candidate.identity.patched=passed  container.reparse=passed  repair.action=passed
patch.capacity=passed        detail: actions=1 sites=0x4020d9 registers=ebx->r12d
runtime.evidence=passed      detail: runner=limactl tier=emulated_run source=poc_manifest
runtime.tier=passed          detail: tier=emulated_run runner=limactl source=poc_manifest
runtime.contract=passed      detail: poc differential status=pass tier=emulated_run runner=limactl
poc.native.available=passed  status=pass runner=limactl
poc.native.original_failure=passed  cases=4 status=pass
poc.native.candidate_pass=passed    cases=4 status=pass
poc.native.regression=passed        cases=20 status=pass
```

Rendered page (`agent-quick-result.png`, DOM assertions in `gui-assertions.json`):

- Card title: `一键修复完成（通过确定性验收）`.
- Chips: `策略 capacity-check`, `gate success_within_scope`,
  `运行时 guest/emulated`, `runner limactl`.
- Check table prints the backend `detail` text verbatim for every row, including
  `patch.capacity` (`actions=1 sites=0x4020d9 registers=ebx->r12d`) and
  `runtime.evidence` / `runtime.tier` / `runtime.contract`
  (`runner=limactl tier=emulated_run source=poc_manifest`,
  `poc differential status=pass …`).
- `[data-testid="agent-quick-download"]` is present ("下载修复后的 ELF", data URL)
  only because success is true.
- AI review was not requested; no AI evidence or verdict is rendered.

Screenshots:

| File | What it shows |
|---|---|
| `agent-review-card.png` | Quick-repair review card with the optional `PoC / 回归用例清单（可选，JSON）` picker (`agent-poc-manifest`, `.json`) and "已选择：marcx-capacity.json"; 一键修复 button enabled without a manifest |
| `agent-quick-result.png` | Result card: strategy/tier/runner chips, all 14 passed checks with backend details, download link |

## File digests (SHA-256)

```text
6fda5f94ddd6de739b620e55c90e880feb4fe8c40c4512fc23c22451ac683643  agent-quick-result.png
0c3b563d48d16adeddf08accdd973c4388ad236c634dccd260cb9fe3b8ffd3c5  agent-review-card.png
2f3c0a15f70d4971db80c7129be116fa2fa412302d82437bc2c2cdad7432442d  gui-assertions.json
34556dd971ca8afb6129a41d2115cae3a77b1ffddc929599e8cf6c587d22911f  repair-review-response.json
6b783c5579cbf39c8bd451b0f6009e50e874c29f48b422e8f7c8ea6298fe9c19  verify_gui_capacity.py
```

## Boundary / limitations

- This evidence is scoped to: container reparse, the recorded and byte-derived
  patch, and the PoC/regression cases in `fixtures/poc/marcx-capacity.json`
  executed in the stated guest runtime.  It is **not** a whole-program proof.
- `verified_patch` here depends on the supplied manifest and a runnable guest;
  without either, the same card would show a held candidate and no download.
- The class is bounded to ELF64 x86-64 and the reviewed duplicated
  capacity-check shape; see `docs/architecture/capacity-check-repair.md`.
