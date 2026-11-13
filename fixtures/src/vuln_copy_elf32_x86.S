// ELF32 x86 (SysV i386 / cdecl): 16-byte buffer at ebp-0x10.
// capacity = frame_top (ebp) - destination (ebp - 0x10) = 0x10.
//
// The 32-bit SysV ABI passes arguments on the stack: the destination is the
// last push before the call.  Both pushes are visible to the i386 analyzer's
// stack-argument model, so the sink stays exactly recoverable.
.text
.globl vuln_copy
.type vuln_copy, @function
vuln_copy:
    pushl %ebp
    movl %esp, %ebp
    subl $0x20, %esp
    movl 8(%ebp), %eax
    leal -0x10(%ebp), %edx
    pushl %eax
    pushl %edx
    calll strcpy
    addl $8, %esp
    leal -0x10(%ebp), %eax
    pushl %eax
    calll puts
    addl $4, %esp
    leave
    ret
.size vuln_copy, .-vuln_copy
.section .note.GNU-stack,"",@progbits
