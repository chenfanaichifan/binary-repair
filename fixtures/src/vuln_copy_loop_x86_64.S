// ELF x86-64 (SysV): inlined byte-copy loop into a 16-byte stack buffer.
//
// This is deliberately NOT a strcpy call: the deterministic analyzer's
// call-site patterns cannot see it, so the baseline reports analysis_only.
// The correct repair (targeted assembly benchmark) must replace the loop with
// a bounded copy and keep the calling convention.
.text
.globl vuln_copy
.type vuln_copy, @function
vuln_copy:
    pushq %rbp
    movq %rsp, %rbp
    subq $0x20, %rsp
    movq %rdi, %rsi
    leaq -0x10(%rbp), %rdi
    xorl %ecx, %ecx
.Lloop:
    movb (%rsi,%rcx), %al
    movb %al, (%rdi,%rcx)
    testb %al, %al
    je .Ldone
    incq %rcx
    jmp .Lloop
.Ldone:
    leave
    ret
.size vuln_copy, .-vuln_copy
.section .note.GNU-stack,"",@progbits
