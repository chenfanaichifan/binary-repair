# Assembly diagnostic feedback: CWE-787 now verified (2026-11-16)

The prior CWE-787 failure was an opaque assembler `^`. P10 now reports
absolute branch targets and assembler diagnostics with line/token, asks the
model for a local-label block, and only injects after a complete revalidation.

DeepSeek flash final result: `cwe787-index-write` **VERIFIED** (candidate and
manifest in this bundle).  No text rewriting was used on the model assembly.
