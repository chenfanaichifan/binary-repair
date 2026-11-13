// Windows ARM64 / Linux AArch64: 16-byte buffer at sp+0x10.
// capacity = frame_top (sp + 0x20) - destination (sp + 0x10) = 0x10.
// Both PE/COFF and ELF for AArch64 spell these symbols without a leading
// underscore, so one source serves both targets.
.text
.globl vuln_copy
vuln_copy:
    sub sp, sp, #0x20
    str x30, [sp]
    mov x1, x0
    add x0, sp, #0x10
    bl strcpy
    add x0, sp, #0x10
    bl puts
    ldr x30, [sp]
    add sp, sp, #0x20
    ret
