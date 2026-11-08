# Review 12 — M4 verification (scope/bounded UI)

Date: 2026-11-08  
Commit under test: `16b2a42`  
Result: PASS (source + unit/HTTP tests); browser DOM not executed.

## Code

```text
16b2a42 touches only app/static/js/agent.js and tests/test_agent_console.py
agent-scope-bounded exists
scopeText = "unknown"
boundedText = "unknown"
no early return on missing scope/bounded
"超出边界" only for exceeded === true
no "通过" branch
```

## Tests

```text
tests/test_agent_console.py::test_scope_and_bounded_never_turn_missing_into_pass
tests/test_agent_console.py::test_comparison_is_only_shown_when_the_api_says_available
tests/test_agent_honesty.py
-> exit 0
```

## Page check

P1 job `9247357c54714546a7ff84891f7766f8` has no top-level scope/bounded;
the UI source therefore renders both as `unknown`. This was verified from the
rendered template/source path, not by executing a browser DOM.

## Verdict

```text
Review 12: PASS
```

## Not claimed

```text
scope/bounded satisfied: no
browser DOM execution: no
independence: M4 = Lead same operator
```
