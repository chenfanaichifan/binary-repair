# Cross-binary benchmark expansion (2026-11-16)

Added CWE-125/190/476/134 fixtures with independent PoC, regression, reference
and build metadata, plus dev/hidden split.

DeepSeek flash first run after prompt/schema fixes:

| case | split | result |
|---|---|---|
| cwe125-oob-read | dev | VERIFIED |
| cwe190-integer-overflow | dev | VERIFIED |
| cwe476-null-deref | hidden | VERIFIED |
| cwe134-format-string | hidden | PLAN_INVALID |

The benchmark now has 8 binaries and 7 CWE classes; the hidden CWE-476 case is
the first hidden-split AI verified result.  CWE-134 remains a negative result.
