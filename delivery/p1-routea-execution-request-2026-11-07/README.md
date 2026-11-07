# P1 Route A execution request

Candidate is already patched; do not re-patch on the guest unless verifying.

```text
original  c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
candidate 2a96b1083f23a0885ef6152dee39c48648d496a7a026e37ccfb31382c412970e
```

Required guest run:

```text
execute candidate with no input
stdout == 100 A bytes + LF
exit 0
stderr empty
```

Return a Route A result bundle with V0/V1/V2/V3/V5 evidence and the raw run log.
Do not write `verified_by`; do not modify Route B/V5 evidence.
