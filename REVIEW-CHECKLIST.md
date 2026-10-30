# Review Checklist

Do not mark work complete until the relevant checks pass. Record outcomes honestly: an unrun check is untested, not passed. Nothing here has been run yet — this list describes what to check, not evidence of a passing result.

## Basic Checks

- [ ] Diff is focused on the requested task.
- [ ] No unrelated files were rewritten.
- [ ] No secrets, tokens, API keys, private logs, or client binaries were exposed — in code, commits, logs, reports, or model prompts.
- [ ] Protected actions, if taken, were covered by the user's authorization as defined in AGENTS.md.
- [ ] Tests/typecheck/lint passed, or each failure is explained rather than hidden.
- [ ] The affected GUI journey was checked in a browser (Chromium/Chrome primary, Firefox smoke) when the change is user-visible.
- [ ] `MEMORY.md` was updated if the phase, a decision, or a known issue changed.
- [ ] Every command quoted in a report was actually run, with its observed result; proposed commands are labelled unverified.

## Domain Safety

These replace generic web-app security checks, because this project runs untrusted binaries.

- [ ] No uploaded binary was executed, and no model-generated C was compiled, on the host.
- [ ] Untrusted artifacts were exercised only through the guest broker, and the guest snapshot was reset between test runs so a candidate cannot alter a later test's oracle.
- [ ] The original input was preserved read-only; each route wrote to its own candidate copy.
- [ ] Worker/broker inputs are typed manifests and artifact IDs, never shell strings; tool arguments are passed as argument arrays built from validated values.
- [ ] Output size, execution time, and filesystem scope limits were applied to guest work.
- [ ] Transfer and export reject symlinks, path traversal, device files, oversized output, and unexpected names.
- [ ] Original source, DWARF/source paths, reference fixes, and evaluator annotations are absent from repair inputs and model prompts.
- [ ] Dependency audit run (`pip-audit` or equivalent — currently unverified in this project); no unaddressed high-severity findings.
- [ ] Uploaded content is validated by content, not extension, with streamed size limits and quotas; archive extraction stays rejected.
- [ ] Local-service protection was tested even though the service is loopback-only: missing session token, cross-origin POST, and reusable bootstrap token are all rejected. Host and Origin are validated and CSRF is enforced on state-changing requests.
- [ ] Untrusted output is rendered through template escaping and DOM `textContent`; worker-supplied HTML is never displayed as active content. CSP, `nosniff`, and frame restrictions are set.
- [ ] Downloads are forced attachments with safe filenames; export bundles are built from registered relative paths plus an independently generated hash manifest, not from arbitrary job-directory contents.

## AI Checks

Use for anything touching the product's DeepSeek integration, prompts, contracts, or acceptance.

- [ ] Model-visible data is documented, and only the minimum needed context was sent — not all job artifacts.
- [ ] Binary-derived excerpts, decompiler output, generated code, and guest output were treated as untrusted data; embedded strings did not alter permissions, tools, or scope.
- [ ] Candidate payloads carry no executable host commands, requested permissions, credentials, or claimed proof results, and extra fields are rejected.
- [ ] Hashes, integer ranges, target membership, string sizes, and route-specific fields were validated locally; provider JSON mode was not trusted as schema validity.
- [ ] Negative scenarios behaved correctly: malformed candidate, wrong architecture or input identity, insufficient safe placement, failing regression, solver timeout/unknown, provider failure, injection strings, unauthorized client-data transfer, exhausted retries, cancellation.
- [ ] Logs, events, and traces contain no secrets, API keys, session tokens, or confidential content.
- [ ] Provider retention/training terms, region, and gateway forwarding were checked before any material beyond public fixtures was involved.
- [ ] A deterministic baseline result, if shown, is labelled as an evaluation mode and never as a successful AI-assisted route.

## Acceptance And Evidence

- [ ] Required evidence is present for every gate V0–V5 that applies to the change; missing, unknown, or unrun required obligations produce `not_run`/`inconclusive`, never `success_within_scope`.
- [ ] Failed required behavioural or compatibility checks reject the candidate; a counterexample is never averaged away.
- [ ] Success labels originate in the acceptance engine, not in a template or route handler, and they display their scope, bounds, and assumptions.
- [ ] Structural/placement audit covers overwritten instructions, incoming edges, RIP-relative operands, branch reach, register/flag preservation, stack alignment, loadable-segment permissions, relocations, and every changed interval and mapping.
- [ ] Route B's unchanged round trip is demonstrated before any security edit; the known defect remains observable after it.
- [ ] The symbolic report states its bounded domain, models, hooks, assumptions, state accounting, and unresolved exploration — and never reads as a whole-program proof.
- [ ] Failed or inconclusive artifacts are labelled diagnostic candidates, and exports state that they are not production approval.
- [ ] Provided unsupported/error/inconclusive scenarios received the correct label.

## Final Evidence

The final response should include:

- Files changed
- Commands run, with observed results
- Test/typecheck/lint/build results
- Browser flow results for GUI changes
- AI/tool evaluation results where applicable
- Remaining risks and any unverified claim
