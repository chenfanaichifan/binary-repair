// Mach-O arm64: 16-byte stack buffer at the top of the callee frame.
// capacity = frame_top (sp + 0x20) - destination (sp + 0x10) = 0x10.
.text
.globl _vuln_copy
_vuln_copy:
    sub sp, sp, #0x20
    str x30, [sp]
    mov x1, x0
    add x0, sp, #0x10
    bl _strcpy
    add x0, sp, #0x10
    bl _puts
    ldr x30, [sp]
    add sp, sp, #0x20
    ret
