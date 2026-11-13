// ELF32 x86 (static musl / cdecl) memcpy with an immediate length.
//
// The 16-byte stack buffer sits at the top of the callee frame, so the frame
// model gives capacity = ebp - (ebp - 0x10) = 0x10.  cdecl pushes the length
// first: memcpy(dst, src, 64) materialises 64 as a push imm32, which the i386
// analyzer turns into a ``memcpy_length`` sink whose immediate can be rewritten
// to the capacity in place.
//
// GNU as would shrink ``pushl $0x40`` to the imm8 form (6A 40), which cannot
// be rewritten in place; emit the canonical 68 id32 form explicitly.
//
// The fixture links its own small ``memcpy`` on purpose: static musl resolves a
// libc ``memcpy`` reference to the ``compiler_rt.memcpy.memcpyFast`` alias, and
// the v1 i386 analyzer deliberately keys repair sinks on the plain copy symbol
// names (fail closed for aliases it does not recognise).  Defining the callee
// locally keeps the fixture a single-function, single-sink positive.
.text
.globl vuln_copy
.type vuln_copy, @function
vuln_copy:
    pushl %ebp
    movl %esp, %ebp
    subl $0x20, %esp
    movl 8(%ebp), %eax
    .byte 0x68
    .long 0x00000040            # push imm32: memcpy length argument (64)
    pushl %eax
    leal -0x10(%ebp), %edx
    pushl %edx
    calll memcpy
    addl $12, %esp
    leave
    ret
.size vuln_copy, .-vuln_copy

.type memcpy, @function
memcpy:
    pushl %ebp
    movl %esp, %ebp
    movl 8(%ebp), %edi
    movl 12(%ebp), %esi
    movl 16(%ebp), %ecx
    rep movsb
    movl 8(%ebp), %eax
    leave
    ret
.size memcpy, .-memcpy
.section .note.GNU-stack,"",@progbits
