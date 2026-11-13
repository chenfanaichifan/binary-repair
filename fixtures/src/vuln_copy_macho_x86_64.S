// Mach-O x86-64 (SysV): 16-byte buffer at rbp-0x10.
// capacity = frame_top (rbp) - destination (rbp - 0x10) = 0x10.
.text
.globl _vuln_copy
_vuln_copy:
    pushq %rbp
    movq %rsp, %rbp
    subq $0x20, %rsp
    movq %rdi, %rsi
    leaq -0x10(%rbp), %rdi
    callq _strcpy
    leaq -0x10(%rbp), %rdi
    callq _puts
    leave
    retq
