# 141 — Two class-difference plans: CWE-121/argv vs CWE-416/none

Date: 2026-11-07  
Owner: Member 5 (schema, planner contracts, evidence interfaces)  
Status: planning artifact; no gate verdict, no merge, no tag.

## 1. Where the plans live

| Plan | Contract path | Fixture path |
|---|---|---|
| CWE-121 / argv | `fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json` | `fixtures/public/CWE121_src_char_declare_cpy_51b/` |
| CWE-416 / none | `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/contract.json` | `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/` |

Both are stored in this repository at the paths above. The branch and commit for
this plan are recorded by `git log --oneline -1 -- docs/handoffs/141-m5-class-difference-plan-2026-11-07.md`.

## 2. The two plans, side by side

The difference is structural, not a title string. At least these fields differ:

| Structural field | CWE-121 / argv | CWE-416 / none |
|---|---|---|
| `schema_version` | `2` | `3` |
| `input_mode` | `"argv"` (v2 default) | `"none"` (explicit) |
| `invalid_input_response` | present | **absent** |
| `invalid_stdout` | present | **absent** |
| `invalid_stderr` | present | **absent** |
| `invalid_exit_code` | present | **absent** |
| `max_valid_input_bytes` | present (`49`) | **absent** |
| `defect.cwe` | `CWE-121` | `CWE-416` |
| `defect.mechanism` | `bounds-check` | `lifetime` |
| `defect.bug_site` | `stack` | `heap` |
| valid cases | `4` | `1` |
| invalid cases | `2` | `0` (`not_applicable`) |
| V3 shape | `4/4` valid + `2/2` invalid | `1/1` valid, invalid `not_applicable` |

The first seven rows are contract-shape differences; the defect rows are
class/mechanism differences; the case rows are acceptance-shape differences.
Changing only `valid_behavior` text is not a second class.

## 3. CWE-121 / argv plan

```json
{
  "schema_version": 2,
  "target_entry": "...",
  "valid_domain": "argv strings of length 0..49",
  "invalid_input_response": "print the exact stderr line and exit 1",
  "invalid_stdout": "",
  "invalid_stderr": "ERROR: input exceeds destination capacity\n",
  "invalid_exit_code": 1,
  "max_valid_input_bytes": 49,
  "dest_capacity_bytes": 50,
  "capacity_includes_terminator": true
}
```

Tests:

```text
tests/valid.json: 4 cases
tests/invalid.json: 2 cases
```

## 4. CWE-416 / none plan

```json
{
  "schema_version": 3,
  "input_mode": "none",
  "target_entry": "CWE416_Use_After_Free__malloc_free_char_01_bad",
  "valid_domain": "no input: no argv, no stdin, no file",
  "valid_behavior": "exit 0 and print the 100-byte block it allocated",
  "dest_capacity_bytes": 100,
  "capacity_includes_terminator": true
}
```

The four rejection fields and `max_valid_input_bytes` are **structurally absent**;
they are not `null`, `""`, `0`, or a sentinel. Tests:

```text
tests/valid.json: 1 case
tests/invalid.json: absent
V3 invalid: not_applicable
```

## 5. What a planner must return

A plan for either class must carry at least:

```text
mode: deterministic | llm
steps: 1..6
kind: upload | question | review
questions: key, label, input, required, ascii, default
review step last
```

The class-specific difference must appear in the plan's steps/questions, not only
in a title. For CWE-416/none, the plan must ask for or state:

```text
no-input observation
invalid case is not applicable
V3 ceiling is 1/1
```

For CWE-121/argv, it must ask for or state:

```text
argv valid/invalid boundary
4 valid + 2 invalid
V3 is 4+2
```

## 6. Non-claims

```text
No V0-V5 pass is claimed here.
No T8.3 acceptance is claimed here.
No second usage implementation is added here.
```

## 7. Commit

```text
branch: m5/t83-deliverables-2026-11-07
commit: see `git log --follow -- docs/handoffs/141-m5-class-difference-plan-2026-11-07.md`
```
