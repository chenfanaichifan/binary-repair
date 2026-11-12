# AArch64 ELF direct repair

`app/services/arm64_repair.py` decodes AArch64 `.text` with capstone and patches
the MOVZ immediate word in place.

Recognized shape:

```asm
sub sp, sp, #0x20
mov w2, #0x100
mov w8, #63      ; read
svc #0
```

The `mov w2, #0x100` word is rewritten to `mov w2, #0x20`. No assembly text is
reassembled.

Tests: `tests/test_arm64_repair.py`.

Limits:

- immediate MOVZ only;
- no AArch64 runtime emulator yet (static verification only);
- no code cave/segment injection for AArch64;
- register/indirect lengths remain unsupported.
