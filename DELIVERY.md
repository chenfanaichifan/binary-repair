# Final delivery snapshot

Branch: `workbench-v3`  
Final UI commit: `6eea41d`; i18n/theme fix commit follows  
Test run: **810 passed / 2 skipped / 1 known macOS `readelf` failure**  
Known failure: `tests/test_routeb_executor.py::test_static_routeb_bundle`
(macOS `readelf` is unavailable; not an application regression).

## What changed in this delivery

- One launch card for **live task / demo session**, with fresh/pending/success/failure
  demo scenarios and an inline difference explainer; the old separate demo entry
  is gone. The landing demo link is folded into the existing mode selector.
- Accessible **sci-fi custom selects** replace native select chrome in Settings.
- **Nine UI languages**: 简体中文 / 繁體中文 / English / 日本語 / 한국어 /
  Français / Italiano / Português / Español. Navigation, primary controls,
  headings, settings labels and descriptions are localized; evidence and
  technical source text stay original. See `docs/reference/i18n.md`.
- Evidence control room: scorecard, V0–V5 matrix, obligations/filters,
  attempt history, artifacts/fingerprints, raw JSON and export links; backed by
  a read-only `/api/jobs/{id}/evaluation` coverage endpoint. It never derives a
  verdict; missing denominators stay N/A.
- Full-shell localization: 1274 auto-extracted rendered segments plus curated
  labels across nine languages. Technical identifiers, code and verdict values
  stay original.
- Rebuilt **`/guide`** with twelve sections, an evidence-chain SVG, step tables,
  V0–V5 verification levels, troubleshooting, security checklist and official
  CWE/Ghidra/angr/Frida/QEMU links.
- Responsive **top bar + off-canvas drawer** replaces the stacked mobile
  sidebar; desktop type/spacing was tightened around a ChatGPT/Claude-like
  hierarchy.
- Ambient material: light porcelain/iris/teal translucent glass, dark
  midnight/cyan-violet aurora; both animated and reduced-motion aware.
- Restrained **page-transition** scan/iris effect, respecting reduced motion and
  the animations-off setting.
- Current screenshots in `docs/showcase/`.

## Share package

The clean runtime ZIP is built outside this repository (it contains a `.venv`-free
runtime tree, not git metadata):

```text
WeChat-Share/BinaryRepair-Workbench-2026-11-12.zip
```

It was smoke-tested from a fresh directory on port 8125: `/healthz`, landing,
`/agent` launch card, expanded result/evidence markup, `/guide` SVG and
i18n assets all load. The package excludes
`.git`, `.venv`, history databases, tests, caches and provider keys.

## Public demo

A dedicated mock instance runs separately from the local 8123 instance:

- data directory: `/tmp/binaryrepair-wechat-demo`
- port: `8124`
- public tunnel: ngrok, token-gated
- backend: `mock` (synthetic fixtures; no real repair execution)

The token and live URL are intentionally **not** committed to Git; they are in
`WeChat-Share/群消息-可直接粘贴.txt` for the actual group share.

## Verification

```bash
cd binary-repair-gui
.venv/bin/python -m pytest
```

- Unit/security/route tests: 810 passed, 2 skipped.
- The one failure is the known macOS `readelf` environment limitation.
- Browser smoke: language switch (zh/en/ja/zh), custom select, mobile drawer,
  page transition, live/demo launch modes, expanded result/evidence panel,
  public health and landing.
- Quality/efficiency probe: `scripts/benchmark_repair.py`;
  report [`docs/acceptance/repair-evaluation-2026-11-12.md`](docs/acceptance/repair-evaluation-2026-11-12.md).
