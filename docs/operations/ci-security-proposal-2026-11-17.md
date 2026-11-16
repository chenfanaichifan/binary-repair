# Proposal: CI and pre-commit secret scanning (2026-11-17)

Status: P2 proposal. Owner: M4. **Not applied** - no CI workflow, pre-commit
config or repository policy file was modified. This document is a decision input
for the Lead; the scanner it references is already added as an opt-in repository
script.

Background: master report section 1.5.1 / 6.2 B9 treats all provider keys pasted
into chat/session logs as compromised (rotation is tracked in
`security-key-rotation-2026-11-17.md`). Prevention needs a scanner in the commit
path and in CI. The current repository has no secret-scanning step; the only
scan is the workspace tool `tools/handoff/scan-secrets.sh`, which is outside the
repo and not run by CI.

## 1. Delivered building block (no policy change)

`binary-repair-gui/scripts/security/scan-secrets.py` (offline, no dependencies,
ASCII) is a repository-owned mirror of the handoff scanner:
- masked output only (first 5 + last 2 chars); `--show-context` replaces the
  secret with `<REDACTED>` and prints the surrounding line;
- known/allowlisted values are SHA-256 digests, never plaintext;
- skips `.git`, `.venv`, `node_modules`, `datasets`, `backup`, `delivery/zh`,
  binary/archive suffixes and files larger than 2 MB;
- exit code 0 = clean, 1 = candidates, 2 = usage error.

Local check on the current tree:
```
cd binary-repair-gui
.venv/bin/python scripts/security/scan-secrets.py docs
=> total candidates: 0 (exit 0)

.venv/bin/python scripts/security/scan-secrets.py tests
=> total candidates: 12 (all synthetic unit-test fixtures, see below)
```

## 2. Proposed CI step (patch draft - Lead applies)

Add one step to each job that already runs the static checks (both `ci` and
`coverage-gate` in `.github/workflows/ci.yml`), right after the markdown
language step:

```yaml
      - name: Secret scan (masked, offline)
        run: python scripts/security/scan-secrets.py --show-context
```

Optional hardening (recommended for the release job only):
```yaml
      - name: Secret scan (release tree, hard fail)
        run: python scripts/security/scan-secrets.py --show-context .
```

Notes:
- No new dependency and no network access are required; the step runs in the
  same Python 3.11 environment.
- The step is deterministic and fast (about a second on this tree).
- Keep the job name and step name stable so branch protection can require it.

## 3. Proposed pre-commit hook (patch draft - Lead applies)

Option A - `.pre-commit-config.yaml` at the repository root:
```yaml
repos:
  - repo: local
    hooks:
      - id: secret-scan
        name: masked secret scan
        entry: python scripts/security/scan-secrets.py --show-context
        language: system
        pass_filenames: false
        stages: [pre-commit]
```
Option B - plain Git hook (no pre-commit dependency) installed by a small
`scripts/security/install-git-hooks.sh` wrapper; the Lead can choose the
lighter option. Option A is preferred because it is declarative and works on
macOS/Linux with no extra setup beyond `pre-commit install`.

Rollout recommendation:
1. first release cycle: run warn-only (scanner exit code ignored, report
   printed) so contributors can clean fixtures;
2. then make it blocking (CI + hook);
3. document the rule in `CONTRIBUTING.md` (one line: "never commit keys; use
   placeholders; run scripts/security/scan-secrets.py").

## 4. Blocker to make the CI step green: test fixtures

The 12 existing candidates are synthetic unit-test values in
`tests/test_assistant_key_store.py` (6), `tests/test_assistant_key_api.py` (2),
`tests/test_model_payload.py` (1), `tests/test_assistant_llm.py` (1),
`tests/test_connectors.py` (2). They are not live credentials, but they match the
scanner pattern. Two clean options (pick one; the code owner decides):

- Preferred: rewrite the fixtures to obviously fake values that do not match a
  real provider shape - for example, assemble the value at runtime in the test
  from parts (a literal marker plus a clearly non-key suffix) instead of storing
  a full token-shaped string in the file. Note: this proposal originally quoted
  one such literal example and the scanner correctly flagged this very
  document; the example was removed rather than allowlisted. This keeps CI
  strict with no exception list.
- Alternative: add their SHA-256 digests to `KNOWN_SHA256` in the scanner with
  a comment naming the test file; weaker because it creates an allowlist.

Do not weaken the scanner by adding broad ignore patterns; keep it fail-closed.

## 5. Verification checklist after the Lead applies the patches

1. `.venv/bin/python scripts/security/scan-secrets.py --show-context .` -> 0
   candidates (after fixture cleanup).
2. Deliberate test: create a temp branch/copy with a fake pattern that is not in
   the allowlist (e.g. a string matching the `sk-` rule) and confirm CI fails
   and prints only masked output.
3. Confirm the hook rejects a staged file containing the same synthetic pattern
   and the error message contains no secret value.
4. Confirm CI logs never print the raw candidate: grep the job log for the
   synthetic value - it must not appear (only the masked form).
5. Re-run `tools/handoff/check-env.sh` (workspace) and the markdown language
   gate; both must stay green.

## 6. Boundaries

- A regex scanner is a heuristic: it will not catch every credential format and
  may miss keys split across lines or stored in binary files. It reduces
  recurrence risk; it does not replace rotation.
- The scanner deliberately skips `delivery/zh` (out of the ASCII docs gate but
  still text) - if that tree is ever published, add it back to the scan roots.
- This proposal does not modify `.github/`, `.pre-commit-config.yaml` or any
  policy file; M4's write scope covers only the scanner script and these ops
  docs, and CI changes are Lead decisions.
