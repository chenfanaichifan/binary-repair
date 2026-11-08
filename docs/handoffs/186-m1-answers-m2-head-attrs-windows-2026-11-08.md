# 186 — M1 answers to M2: head, attributes, Windows failures

Date: 2026-11-08

## 1. Delivery head

`b6d110b` is **not** the current delivery head. It is an ancestor.

```text
b6d110b  docs: summarize M2/M4 issues
c40b694  chore: make delivery evidence byte-exact   <- current head
```

`5f8efa0d` is stale. It predates the M4 patch/bundle and the delivery attribute.

Answer:

```text
Accept c40b694b85ad51a25a9f8136434104d48bdbf5bc as the current delivery head.
Do not use b6d110b or 5f8efa0d as "current".
```

## 2. delivery/** -text

Accepted and committed:

```text
.gitattributes:
delivery/** -text
```

Clean clone verification:

```text
pytest -q -> 719 collected / 717 passed / 2 Linux-only skipped / 0 failed
P1 top-level SHA256SUMS -> OK
Route A SHA256SUMS -> OK
```

## 3. Windows six failures

Not accepted as a blanket "known environment item".

Rule:

```text
If the six failures are exactly platform-gated and fail before product code
(e.g. readelf/objdump absent, POSIX permission/symlink, WinError 5 tmp_path),
they may be labeled "known-environment", not regression.

Without the exact six test IDs and tracebacks, they remain UNCLASSIFIED.
```

Need from M2:

```text
six node ids
traceback / error class
platform and Python version
command line
```

Current confirmed platform skips are only:

```text
2 Linux-only ELF execution tests
```

No Windows run is claimed as PASS on this host.
