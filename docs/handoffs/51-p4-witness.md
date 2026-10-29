# 51 — P4 package witness (M4 decision pending)

**Package:** `P4-package-2026-10-29.zip`
**SHA-256:** `427dd71d3b94ca7b12dfce3a4031611f9bb6a0d7ce986d6d96fe9b6a762b2dd4`
**checker:** PASS (15 files / 15 sums, `5c7ab9aa…`)

Observed:

```text
native manifest-compare.json: present, gate4_pass=true, 6/6
case-01..06: derived, runner_native=false, derived_from=manifest-compare.json
gate4-status.json: gate4="pass"
```

Missing:

```text
runner-native six-case raw: absent
candidate.elf/original.elf: not in package; hashes.json carries candidate/sha
```

M5 witness only: checker PASS and native manifest present; **no `gate4_pass`**.
M4 decides whether `manifest-compare.json` is sufficient native evidence; until
then P4 remains NOT a formal Gate 4 pass.
