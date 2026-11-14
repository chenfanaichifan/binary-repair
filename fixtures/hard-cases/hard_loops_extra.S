.text
.globl vuln_loop8
.type vuln_loop8, @function
vuln_loop8:
    pushq %rbp
    movq %rsp, %rbp
    subq $0x10, %rsp
    movq %rdi, %rsi
    leaq -0x8(%rbp), %rdi
    xorl %ecx, %ecx
.L8:
    movb (%rsi,%rcx), %al
    movb %al, (%rdi,%rcx)
    testb %al, %al
    je .L8done
    incq %rcx
    jmp .L8
.L8done:
    leave
    ret
.size vuln_loop8, .-vuln_loop8

.globl vuln_loop64
.type vuln_loop64, @function
vuln_loop64:
    pushq %rbp
    movq %rsp, %rbp
    subq $0x80, %rsp
    movq %rdi, %rsi
    leaq -0x40(%rbp), %rdi
    xorl %ecx, %ecx
.L64:
    movb (%rsi,%rcx), %al
    movb %al, (%rdi,%rcx)
    testb %al, %al
    je .L64done
    incq %rcx
    jmp .L64
.L64done:
    leave
    ret
.size vuln_loop64, .-vuln_loop64
.section .note.GNU-stack,"",@progbits
