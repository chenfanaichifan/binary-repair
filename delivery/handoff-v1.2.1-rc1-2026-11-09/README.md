# BinaryRepair v1.2.1-rc1 handoff — aligned with public rc1

Status: **aligned with public `v1.2.1-rc1` / `d7d20f4`.**

```text
source        3418491
M2 public    0f4196d
public candidate d7d20f4ff2f920b5cfec5e81e3c4377529a9885a
tag           v1.2.1-rc1
tag object    f5346978b46622c6c582e13d7cf6330f72e638f3
release       https://github.com/leesirleesirlee-star/Binary_Repair/releases/tag/v1.2.1-rc1
public main   9439340 / v1.2.0
v1.1.3        367d29b frozen
```

This handoff is aligned with public v1.2.1-rc1 / `d7d20f4`.
It supersedes the A source snapshot from `99d1550` / `67476c8` and includes
N8/N9/N10/N11. A remains a source-only historical snapshot, not public rc1.

Verification:

```text
741 collected / 739 passed / 2 Linux-only skipped / 0 failed
browser e2e 12 passed
signed receipt db99eb0

public-tree verification (docs/handoffs/230):
P0 acceptance 17/17 PASS
browser e2e 12/12 passed (35.98s)
Windows public-tree full: 741 collected / 0 failed / 13 skipped
```

`SHA256SUMS` is LF-only and verifies 30/30 directly, without CRLF normalization.

The handoff zip SHA-256 is in `../handoff-v1.2.1-rc1-2026-11-09.zip.sha256`
(outside the archive to avoid a self-referential hash).

Docs included:

```text
222, 228, 229, 232, 233, 234, 235
(plus 216, 218, 220, 221, 226, 230, 236, 237)
```

Limitations:

```text
N-10 accepted limitation
Windows real-key cross-head 8f0908a
0d/99d real-key NOT RUN
v1.2.1 stable remains HOLD
```

Boundaries:

```text
public rc1 tag  v1.2.1-rc1 -> f5346978... -> d7d20f4
public main     9439340 / v1.2.0
v1.1.3          367d29b frozen
A snapshot      v1.2.1-rc1-source-99d1550 -> 67476c8 (source only)
```
