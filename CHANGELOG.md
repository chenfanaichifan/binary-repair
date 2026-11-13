# Changelog

## 2026-11-13 — v6: two AI binary repair paths (assembly round-trip / direct bytes)

- New `asm_roundtrip` path: CAPSTONE disassembles the target ELF function to
  assembly text, the model returns replacement assembly, clang assembles it to
  a machine-code block, which is injected and function-entry redirected; then
  the deterministic gate verifies the patched ELF.  Supports ELF
  i386/x86_64/arm64.
- New `binary_direct` path: raw machine-code guard injection or same-length byte
  edits, fronted by a fail-closed Capstone/allowlist/injection/edits validator;
  at least one edit must hit the selected sink's length immediate.  No assembly
  text and no decompiled-C round trip.
- New ELF x86-64 guard fixture and runtime selection; x86-64 canary placement
  fixed for frames whose buffer ends just below the saved RBP.
- `POST /api/binary/ai-repair`, `GET /api/binary/ai-paths`, CLI `--ai-path`, and
  two `/binary` UI cards.  The deterministic gate remains the only acceptance
  authority; AI cannot promote a failed or incomplete gate.
- Runtime `buffer_match` evidence for bounded copies rejects structurally valid
  but semantically empty guards (for example a lone `ret`).
- Tests: `test_ai_binary_repair.py`, `test_ai_patch_validation.py`,
  `test_binary_ai_ui.py`, `test_ai_evidence_script.py`; scripted evidence
  `artifacts/ai-direct-binary-2026-11-13/` and acceptance record
  `docs/acceptance/ai-binary-repair-2026-11-13.md`.
- Verification follow-up: `scripts/verify_evidence.py` (reproducible fixture/
  source/bundle SHA-256 checks), readelf root-cause/claim-scope review
  (`docs/acceptance/verification-review-2026-11-13.md`), updated LIMITATIONS
  for the current matrix, PoC-not-in-gate and "no AI increment measured yet".

All notable changes to this project are documented here. This project follows a
simple semantic-versioning policy for delivery snapshots.

## [Unreleased]

### Added — v5 universal repair entry (2026-11-13)

- `app/services/repair_matrix.py`: single source of truth for the deterministic
  repair matrix, dispositions, sink classes and non-goals; `/api/binary/matrix`
  exposes it as English ASCII.
- Universal repair entry: `repair_any` / `scan_any` with explicit dispositions
  (`verified_patch`, `static_only_patch`, `not_verified`, `analysis_only`,
  `unsupported`, `rejected`, `invalid`), report schema v4 (`matrix`, `delivery`,
  `coverage`, `slices`, `warnings`; prior fields kept).
- **32-bit x86 repair** for ELF32 and PE32: Capstone x86-32 analyzer (cdecl
  frame/capacity), cdecl_x86 bounded-copy guards, ELF32 `PT_LOAD` / PE32
  `.brfix` injection, `E8`/`FF15` call resolution, and Unicorn x86-32 runtime
  evidence (`tier=emulated_run`, `engine=unicorn-i386`).
- Explicit opt-in **static-only delivery** for in-matrix candidates without
  runtime evidence; never counted as success and clearly labelled in API/CLI/UI.
- `/binary`「任意二进制修复」page (upload → scan → repair → disposition badge →
  download/report), sidebar entry, curated English i18n strings.
- CLI `scripts/repair_binary.py`: dispositions/verified/delivery in single and
  batch output, `--allow-static-only` semantics made explicit.
- New fixtures `elf-x86`, `pe-x86`, dynamic `elf-x86-dyn`, direct-IAT
  `pe-x86-iat`, `elf-x86-memcpy` and provenance; v5 acceptance record
  `docs/acceptance/binary-universal-v5-2026-11-13.md`.
- v5.1 follow-up: length-aware Unicorn modelling for memcpy/memmove immediate
  repairs (i386 verified path), dynamic ELF32 PLT and PE32 `FF15` direct-IAT
  coverage, ELF32 `extend-rx` fallback test, fat Mach-O slice reporting, and a
  one-function-per-candidate policy so every shipped action is covered by the
  runtime case that executes that function.
- Removed the historical ELF x86-64 verification fail-open path: a failed gate
  now clears `candidate_available` and returns no candidate.

### Added — v4 container-neutral repair (2026-11-13)

- `app/services/containers.py`: ELF/PE/Mach-O detection and imported-call
  resolution (ELF PLT/GOT, PE IAT + `jmp [rip+disp]`/`adrp-ldr-br` thunks,
  Mach-O stubs + bindings).
- `app/services/repair/`: frame-capacity analyzer, bounded-copy guards for
  SysV x86-64 / Win64 / AArch64, immediate clamping, executable-section
  injection and call redirection.
- PE x86-64/arm64 and Mach-O arm64/x86-64 now produce real repaired candidates
  (previously fail-closed); AArch64 ELF gains a guard strategy.
- `app/services/runtime/`: native Mach-O execution (ad-hoc re-sign) and
  Unicorn instruction-level evidence for PE/AArch64, plus a unified gate.
- Report schema v3 with actions, runtime cases and `verification.tier`.
- CLI `--batch`/`--allow-static-only`; `/api/binary/quick-repair` and the
  review path now accept every supported container.
- Reproducible fixtures (`fixtures/src`, `scripts/build_binary_fixtures.py`)
  and evidence (`scripts/capture_binary_evidence.py`). See
  `docs/acceptance/binary-universal-v4-2026-11-13.md`.

### Added

- Direct-ELF verification packet and read-only AI review: the engine report is
  turned into stable checks plus a `GateResult` from the existing acceptance
  rules, and `POST /api/binary/repair-review` can send that same packet to a
  configured model. The model may recommend `accept`/`hold`/`needs_more_checks`;
  an accept cannot promote a failed gate, a hold can veto a passing gate, and a
  candidate with missing runtime evidence is non-successful and not
  downloadable. The legacy `/api/binary/quick-repair` now fails closed on a
  failed gate. See `docs/architecture/ai-adjudication.md`.
- Reproducible direct-ELF AI review experiment:
  `scripts/demo_binary_ai_review.py` records baseline, with-review and scripted
  accept/hold controls for a passing case, an unsupported input, and a
  missing-evidence case. See
  `docs/acceptance/binary-ai-review-2026-11-12.md`.
- Ubuntu verification baseline documentation:
  `docs/operations/ubuntu-verification.md`.

- Inline code repair: paste a fenced (or code-like) snippet in the console and
  get a reviewable patch card with findings, a before/after diff, copy actions
  and a residual-risk note. Rules cover Python `shell=True`/Flask debug/yaml,
  C `strcpy`/`sprintf`/`gets`, JS `eval`/`innerHTML`/`child_process.exec` and
  hardcoded secrets. A configured provider contributes a validated model patch
  and falls back to rules on failure. The snippet is never executed; the API is
  `POST /api/code/repair`, CSRF-protected. See
  `docs/architecture/code-repair.md`.
- Chat rendering: fenced code becomes a copyable code block (language label +
  header); an unfenced code-like message is rendered the same way. Messages
  gained assistant/user avatars, and the console composer advertises "paste
  code to repair".
- Three-state theme: light, dark and follow-system. A pre-paint script avoids a
  white flash, `theme.js` persists the choice in `localStorage`, follows
  `prefers-color-scheme` while on "system", and every page carries the same
  three-button switch. Dark tokens cover the console, tables, code views,
  connectors and the landing hero.
- Server-side task history: `GET/PUT /api/history/<scope>` stores the per-task
  conversation in SQLite (`var/gui-history.db`); the console hydrates from the
  server, falls back to the local cache, and shows a sync badge. A task opened
  from another browser pointed at the same service restores the conversation.
  Drafts use a shared `draft` scope and reset with `?new=1`; a generation
  counter rejects stale tabs so a cleared draft cannot be resurrected. The
  token-bootstrap redirect now preserves `new`/`q`/`workspace`/`fixture`.
  See `docs/architecture/history.md`.
- Resizable/collapsible workspace: the global sidebar, the agent status panel
  (drag, keyboard arrows, double-click reset, persisted), the composer (native
  resize + auto-grow), and long code blocks (expand/collapse). “专注对话”
  hides the header, tabs and both side panels, with Esc to exit.
- Vulnerability explanations in code repair: every finding now carries a CWE
  id, plain-language explanation, impact, a “警醒” warning and reference links;
  a top-level warning box surfaces the primary lesson. The model prompt carries
  the same fields; the UI renders them with textContent.
- Workbench dashboard: the empty task list is replaced by a hero, quick-start
  cards, connector/plugin/history stats, an enriched empty state, and a
  methods/toolchain section. `GET /methods` documents the repair chain and
  tool matrix (Ghidra/Rizin, angr/Triton, Frida/GDB/QEMU, Diaphora/BinDiff,
  AFL++/syzkaller) with official links and verification caveats.
- Connector expansion: 17 probes across model/analysis/workflow/storage, with
  install guides, env-var copy, docs links and status filters. Analysis tools:
  Ghidra, Rizin, binutils, GDB, QEMU, Frida, angr, Triton; runtime: Docker.
  Plugins are a separate section with four tracked sample manifests
  (`plugins/`), a copyable schema and protocol docs.
- Landing v3: orbital hero, compact connector strip, a one-time sci-fi boot
  overlay (session-scoped, skipped for reduced motion and `?nointro=1`), and a
  balanced layout that fits 1280×800 without scrolling.
- Settings: `/settings` covers theme, density, body/code font size, animations,
  send key, auto-scroll, task sort, history sync, default workspace/mode,
  export/import, local-cache clearing and a generation-guarded server-history
  reset. Preferences stay in `localStorage["br.settings.v1"]` and apply through
  `data-density`, `data-motion`, `--chat-font-size` and `--code-font-size`.
  See `docs/reference/ui-settings.md`.
- Full usage guide: `/guide` is a ten-section operator manual (quick start,
  code repair, binary flow, tasks/workspaces, history, settings, connectors,
  methods, shortcuts, troubleshooting/boundaries), linked from the fixed
  sidebar of every workbench page and from the landing nav/footer.
- Task management: sidebar search, pin, rename and local-record delete;
  pinned/recent/name sorting respects settings. The workspace control switches
  the server-configured workspace for new sessions.
- Composer tools: the `+` menu can load multiple code/text files (400 KB each),
  accept drag/drop and paste files, insert fenced code, vulnerable snippets,
  an audit template, clear the conversation, or open the guide. Binary samples
  still go through the guided upload step.
- Command palette (`Ctrl/Cmd+K`): jump to any page, switch themes, or toggle the
  sidebar from every base page.
- Contrast pass: dark ghost buttons/notes, secondary tokens, send/avatar
  foregrounds and the demo banner were audited against WCAG ratios. The
  full-width amber demo strip is now a slim, muted `演示数据` disclosure with a
  boundary link.
- Launch consolidation: the workbench’s separate “新建修复内容” and “打开演示
  会话” entries are now one launch card with real/demo mode, demo scenarios
  (fresh/pending/success/failure) and an inline difference explainer. The
  landing page’s demo link is folded into the existing mode selector
  (`fixture=1` is carried automatically).
- Custom selects: settings uses an accessible sci-fi listbox (`custom-select.js`)
  instead of native `<select>` chrome, with keyboard navigation and dark/light
  styling; the underlying select stays as the settings value source.
- Nine-language UI shell: 简体中文/繁體中文/English/日本語/한국어/Français/
  Italiano/Português/Español, selected from the sidebar, landing or settings.
  Navigation, primary controls, headings and settings labels are localized;
  evidence and technical source text remain original to avoid mistranslation.
  See `docs/reference/i18n.md`.
- Evidence control room: `/api/jobs/{id}/evaluation` (coverage-only, no verdict),
  V0–V5 matrix, scorecard, obligation filters, attempt history, artifact
  fingerprints, raw JSON/export links and a resilient local fallback. Zero or
  missing denominators show N/A; `not_run` never becomes a pass.
- Light palette compromise: the first rainbow-style ambient was too busy; the
  final light theme uses a warm-to-cool porcelain paper, one faint iris wash,
  a barely-there sage undertone and quiet glass cards. Dark keeps the midnight
  identity. Semantic green/amber/red remain the only saturated colors in data.
- Light/dark material pass: warm porcelain/iris/teal ambient with translucent
  glass cards and an animated aurora in light mode; midnight/cyan-violet ambient
  in dark mode. Page transitions respect reduced motion.
- Full UI copy localization: auto-extracted long-form page strings (1274 source
  segments) now translate alongside curated nav/settings labels, including the
  guide, methods, connectors, result/evidence and agent guidance. Technical
  values, code and evidence identifiers stay original.
- C overflow coverage: five deterministic rules for off-by-one loops, custom
  safe-copy NUL off-by-one, heap length-field copies, sprintf, and signed-to-
  unsigned memcpy lengths. Each emits a CWE and a reviewable patch; the
  limits of regex-level analysis are documented in
  `docs/reference/buffer-overflow-patterns.md`.
- Rich manual: `/guide` now has twelve sections, an inline evidence-chain SVG,
  step tables, verification-level table, troubleshooting matrix, security
  checklist and official tool links.
- Responsive structure: a mobile top bar + off-canvas drawer replaces the
  stacked full sidebar; desktop spacing/labels were tightened. Page navigation
  uses a restrained scan/iris transition (disabled by reduced motion or the
  animations-off setting).
- Team sharing: `START-HERE.md`, Windows `start-gui.ps1`/`.bat`, a current
  `docs/showcase/` screenshot set and `SHARE-WECHAT.md`. The host gate accepts
  explicit `BINARYREPAIR_ALLOWED_HOSTS` entries plus an opt-in
  `BINARYREPAIR_ALLOW_TUNNEL=1` for temporary ngrok domains, so a dedicated
  mock demo instance can be shared without weakening the default local-only
  boundary. `start-gui.sh` honors `BINARYREPAIR_HOST` for LAN runs.

### Changed

- The form intake is retired. `/jobs/new` is a 303 redirect to `/agent/new`;
  the setup template, wizard script and hand-drawn stylesheet are deleted. The
  console is the single intake and the sidebar/landing CTA reads
  "新建修复内容". The API path `POST /jobs` stays for the console.
- Landing page rebuilt on one 880 px column: branded top bar, clearer hero
  hierarchy, a one-line "口径" strip, and height-aware spacing so a 1280×800
  viewport fits without scrolling. Test hooks, labels and the composer
  behaviour are unchanged.
- Console polling indicator reads "待命" until a job is selected, so the header
  no longer shows "未选择任务" twice.

### Fixed

- Ubuntu fixture execution no longer depends on Git mode. The CWE121 V0 test
  writes a 0644 source copy, stages it with `chmod 0755`, verifies bytes/hash and
  runs only the staged copy; the workflow reruns that targeted case before the
  `if: always()` full suite. This removes the `PermissionError` on `original.elf`
  without changing the fixture or skipping the test.
- `/agent/new` no longer answers "计划服务未接通 (assistant_endpoint_missing)"
  in the default `mock` backend. `MockBackend.get_plan` now uses the same
  in-process planner seam as `local` (deterministic without a provider key, the
  LLM branch with one), so a first-run GUI can produce a plan. The 503 contract
  is unchanged for a backend that genuinely has no plan route.
- The workspace/mode dropdown no longer renders behind the composer. The entry
  animation left `transform: translateY(0)` on the selector row, which created
  a stacking context and trapped the menu's `z-index`; `ds-rise` now ends on
  `transform: none`, and the selector row carries its own `z-index`.

## [1.2.0] — 2026-11-09

### Added

- Upload gate: hide the repaired-ELF upload controls when the page is not
  served over HTTP(S), and reject files above 64 MiB in the browser before any
  request is sent. The server-side 413 remains the backstop.
- P1 Review 12 fresh browser replay evidence (12 passed) in the public record.
- M4 browser verification for HTTP, `file://` and the 65 MiB rejection path.

### Changed

- Renamed duplicate record `196-m2...` to `196b-m2...`; updated the `198`
  reference.
- Updated status/README for v1.2.0: 730 collected / 728 passed / 2 Linux-only
  skipped / 0 failed.

### Verification

- `artifacts/**/SHA256SUMS` direct: 201/201 OK.
- Browser e2e: 12 passed.
- `v1.1.3` and earlier tags remain unchanged.

## [1.1.3] — 2026-11-08

### Fixed

- Restored curated test paths that regressed in v1.1.2:
  `artifacts/legacy-m5-evidence`, `artifacts/cwe416-124-v4-rerun-2026-11-06`,
  and `docs/reference/interfaces/artifact-roles-v1.md`.
- Full clean-clone suite: 729 collected / 727 passed / 2 Linux-only skipped / 0 failed.

## [1.1.2] — 2026-11-08

### Added

- Comparison UI: renders case-level `same` / `different` / `not_run` evidence and
  summary counts from the GUI comparison JSON route.
- Comparison route fail-closed validation for schema, case IDs, kinds, verdicts,
  hashes and per-side output completeness.

### Changed

- Updated README and final status for the comparison UI and the recorded
  `729 collected / 727 passed / 2 Linux-only skipped` suite.
- Added M1/M2/M4 comparison records 193–199 to the development history.

### Verification

- Full clean suite: 729 collected / 727 passed / 2 Linux-only skipped / 0 failed.
- `artifacts/**/SHA256SUMS` direct: 201/201 OK.
- Tag `v1.1.1` and earlier releases remain unchanged.

## [1.1.1] — 2026-11-08

### Fixed

- Added the repaired-ELF upload/download entry (`operator_deliverable`; never
  executed and never acceptance evidence).
- Normalized artifact `SHA256SUMS` to LF; direct `shasum -c` now passes.
- Restored curated test paths (`artifacts/legacy-m5-evidence`, `artifacts/p1-routea-kit`)
  and the 124 candidate path.
- Full clean-clone suite: 717 passed / 2 Linux-only skipped / 0 failed.

## [1.1.0] — 2026-11-08

### Added

- Current accepted delivery state: T8.3 complete, P1 `success_within_scope`,
  P2 acceptance passed.
- Canonical evidence under `artifacts/`, including P1, Route A V4, 124 rerun,
  V5 original logs, M4 marker/revalidation and recorded test/e2e logs.
- Public repository organization: documentation map, contribution guide,
  security policy, issue/PR templates, changelog and citation metadata.

### Changed

- Moved canonical evidence from `delivery/` to `artifacts/`.
- Reorganized documentation into overview, architecture, acceptance, operations,
  reference, development and archive sections.
- Updated README, repository map and file guide for the curated snapshot.
- Preserved the original Review 9–12 provenance: the original text is still a
  canonical reconstruction, not a recovered verbatim document.

### Fixed

- Restored the byte-exact V5 replay logs and two test-mutated evidence files in
  the curated snapshot; all `artifacts/**/SHA256SUMS` verify.
- Removed development-only caches/temporary trees from the public release tree.

## [1.0.0] — 2026-10-31

Initial public MVP snapshot imported from the original development repository's
`mvp-2026-10-31` state. This tag is retained as history and is superseded by
1.1.0.

## Version policy

- `v1.0.0` is the historical initial snapshot; do not retag it.
- `v1.1.0` is the organized delivery snapshot.
- `v1.1.1` is the curated test/upload fix.
- `v1.1.2` is the comparison-UI snapshot.
- `v1.1.3` is the v1.1.2 path hotfix.
- `v1.2.0` is the current upload-gate / P1 replay snapshot.
- Future changes that alter accepted behavior or evidence scope should use a new
  version and a new annotated tag rather than moving an existing tag.

- Overflow AI upgrade: 12 labeled seeds across six CWE families, 1,200
  synthetic variants, offline pseudo-label training, a pure-Python runtime
  candidate memory, compile/surface validation and an honest held-out report.
  Synthetic accuracy is 1.0 but leave-one-seed-out is 0.25; rules remain the
  authoritative detector. See `docs/acceptance/overflow-ai-2026-11-12.md`.

- Bounded AI adjudication: one-way veto, model-verdict guard, key-binding
  preflight, bounded supervisor and simulation API; AI can never promote a
  failed deterministic gate to success.
- Public v1.2.1 docs patch carried in `artifacts/delivery/`.
