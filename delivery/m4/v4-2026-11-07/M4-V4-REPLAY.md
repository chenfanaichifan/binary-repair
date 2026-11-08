# M4 V4 replay evidence — 2026-11-07

**Head:** `d3993555c30328d14650f004c5db8fb418aa6668` (pre-M2)
**Guest:** `binrepair-vm` at `10.11.0.132:2222`, user `m4verify` (uid 1004, no sudo)
**V4 gate status:** `not_run` for the Gate 0/D5 round — replay matched, but at
that time no M4 marker existed. A later post-Gate-0 marker is recorded in
`M4-V4-MARKER.md` and record 150; this summary remains the historical 146 record.

## 1. Login and environment

`ssh` with `IdentitiesOnly=yes` and the local `FZfxZXkW…DQQ` key succeeded.

```text
uid=1004(m4verify) gid=1004(m4verify) groups=1004(m4verify)
binrepair-vm
Linux ... 6.8.0-147-generic ... x86_64
sudo -n true -> exit 1 (password required; no sudo)
```

## 2. Handoff self-check

```sh
cd /opt/binrepair-handoff/M4-v4-handoff-2026-11-06
sha256sum -c SHA256SUMS      # 12/12 OK
sh verify_all.sh             # ALL PASS: 3/3
```

`verify_all.log` is archived beside this file (SHA256
`8379b79c74f772d1d46cc77d4c67ae08800ff2ec7fca72dcea09caf61747911d`).

The three steps were:

1. 12 files match `SHA256SUMS`;
2. 18/18 environment checks match the 2026-11-06 recipe;
3. end-to-end harness output is byte-identical to
   `9c6eeda7684f2e405fbceb83fec4a3962687559b1d35e738431c631b7d58ca8c`,
   `known_good holds`, `known_bad violated`, replay runs 2 identical.

## 3. T8.3 replay

```sh
cd /opt/binrepair-handoff/T8.3-evidence-2026-11-06
/opt/angr-venv/bin/python v4/v4_harness.py \
  --candidate candidate/candidate.elf \
  --original fixture/original.elf \
  --contract fixture/contract.json \
  --out /tmp/m4-replay.json \
  --replay-runs 2
```

Observed:

| Field | Value |
|---|---|
| exit | 0 |
| `/tmp/m4-replay.json` size | 5172 bytes |
| output SHA256 | `9c6eeda7684f2e405fbceb83fec4a3962687559b1d35e738431c631b7d58ca8c` |
| replay runs | 2 |
| replay identical | true |
| replay digest (both) | `cb2137a20d838e3f48e02f2d38f258487ddc3a588a371970d9ef41b63304cb14` |
| candidate | `holds` (unsat=1) |
| original | `violated` (sat=1) |
| scope | `model` |
| complete | true |
| unknown / timeouts | 0 / 0 |
| steps | 25 |

The local byte copy is `m4-replay.json` in this directory, SHA256
`9c6eeda…ca8c`.

## 4. Gate interpretation

M3's rule stands: logging in, passing `verify_all.sh`, and reproducing the
digest do **not** make V4 a gate pass. `marker_path` remains `null` until M1
names the marker file. No `verified_by` was written.

Machine-readable status: `delivery/m4/acceptance-d3993555c303-pre-m2/V4-REPLAY-STATUS.json`.

## 5. Boundaries

- No private key was copied to the guest, logged, or sent.
- No `sudo` was obtained; the command above exited 1 as expected.
- This is model-scope evidence, not a binary-level proof.
- M2 `06eb7ee` is still missing, so final-head acceptance is still blocked.
