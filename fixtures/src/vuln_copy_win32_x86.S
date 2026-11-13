// PE32 x86 (MinGW / cdecl): 16-byte buffer at ebp-0x10.
// capacity = frame_top (ebp) - destination (ebp - 0x10) = 0x10.
//
// MinGW decorates 32-bit C symbols with a leading underscore, so the exported
// fixture function is `_vuln_copy` and libc references are `_strcpy`/`_puts`.
.text
.globl _vuln_copy
_vuln_copy:
    pushl %ebp
    movl %esp, %ebp
    subl $0x20, %esp
    movl 8(%ebp), %eax
    leal -0x10(%ebp), %edx
    pushl %eax
    pushl %edx
    calll _strcpy
    addl $8, %esp
    leal -0x10(%ebp), %eax
    pushl %eax
    calll _puts
    addl $4, %esp
    leave
    ret
