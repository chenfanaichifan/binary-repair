# 227 — Lead decision: v1.2.1-rc1 security hold

Date: 2026-11-09

## Code

```text
release/v1.2.1 0d5791a
740 collected / 738 passed / 2 Linux-only skipped / 0 failed
browser e2e 12 passed
```

Security fixes:

```text
F1 mask only last 4; min 16 printable ASCII
A-1 unique temp + process lock + replace existence check
F2 evidence copy rejects assistant.key/.env/session.token
F3 masked tails removed from docs 216/218
F5 stale tmp fixed
```

## M2 record issue

`docs/handoffs/222` at `8f0d728` is contradictory:

```text
"Windows real-key UI: PASS"
...
"real-key Windows UI remains NOT RUN"
```

It also says the real key file was intentionally retained:

```text
清除 was NOT run in order to preserve the key for this verification.
```

Lead will not accept a final security record with this contradiction and a
retained real key.

## Decision

```text
HOLD public v1.2.1-rc1.
v1.2.1 stable: HOLD.
public main: v1.2.0 / 9439340 unchanged.
v1.1.3: frozen.
```

Before public rc:

```text
M2: clear the retained real key file
M2: correct record 222 to one unambiguous status
M2: re-run on 0d5791a (or state the tested version)
M4: then publish rc only, with Windows limitation/verification disclosed
```

The already-built public candidate is only a candidate; no public tag/release.
