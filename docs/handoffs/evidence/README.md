# Evidence package store (`docs/handoffs/evidence/`)

One directory per delivered handoff package, named exactly as the handoff id:
`docs/handoffs/evidence/P4-2026-10-30/`, `.../P3A-2026-10-30/`, etc.

Each package must contain:

```text
handoff.json        schema in scripts/check_handoff.py (interface_version 1)
SHA256SUMS          standard "sha256sum" format, sorted bytewise, covers every file except itself
logs/               raw command output (stdout/stderr), timestamps
<evidence files>    every file listed in handoff.json artifacts
```

Validate before committing or notifying the consumer:

```text
python scripts/check_handoff.py docs/handoffs/evidence/<id> --expect-from M3 --expect-to M5
```

Rules:

- **Commit the metadata and small logs.** They are the shared truth; chat messages are only notifications.
- **Do not commit secrets, `.env`, API keys, client binaries, or confidential derived content.** Public-fixture-derived artifacts may be committed only if small and clearly labelled; otherwise record the file name and hash in `handoff.json` and transfer it through the agreed channel.
- **Never edit a delivered package.** Republish as a new id (`P4b-...`) and keep the old one for history.
- A package that fails the validator is not a delivery; fix it or publish a `blocked` package with the exact external condition.
- The consumer (M5) may write a verdict file (`docs/handoffs/39-m5-to-m3-<id>.md`) but must not modify the package.
