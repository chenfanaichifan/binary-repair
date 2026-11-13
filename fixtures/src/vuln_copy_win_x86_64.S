// PE x86-64 (Win64): 16-byte buffer at rsp+0x28.
// capacity = frame_top (rsp + 0x38) - destination (rsp + 0x28) = 0x10.
// The 0x20 shadow space lives at [rsp, rsp+0x20); the buffer sits above it.
.text
.globl vuln_copy
vuln_copy:
    subq $0x38, %rsp
    movq %rcx, %rdx
    leaq 0x28(%rsp), %rcx
    callq strcpy
    leaq 0x28(%rsp), %rcx
    callq puts
    addq $0x38, %rsp
    retq
