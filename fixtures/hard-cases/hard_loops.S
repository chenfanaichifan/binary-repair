/* Five inlined-copy hard cases.  No libc call in any target function; the
 * deterministic analyzer's call-site/template rules cannot see these loops. */
.text

.globl vuln_loop16
.type vuln_loop16, @function
vuln_loop16:
    pushq %rbp
    movq %rsp, %rbp
    subq $0x20, %rsp
    movq %rdi, %rsi
    leaq -0x10(%rbp), %rdi
    xorl %ecx, %ecx
.L16:
    movb (%rsi,%rcx), %al
    movb %al, (%rdi,%rcx)
    testb %al, %al
    je .L16done
    incq %rcx
    jmp .L16
.L16done:
    leave
    ret
.size vuln_loop16, .-vuln_loop16

.globl vuln_loop32
.type vuln_loop32, @function
vuln_loop32:
    pushq %rbp
    movq %rsp, %rbp
    subq $0x40, %rsp
    movq %rdi, %rsi
    leaq -0x20(%rbp), %rdi
    xorl %ecx, %ecx
.L32:
    movb (%rsi,%rcx), %al
    movb %al, (%rdi,%rcx)
    testb %al, %al
    je .L32done
    incq %rcx
    jmp .L32
.L32done:
    leave
    ret
.size vuln_loop32, .-vuln_loop32

.globl vuln_loop_offbyone
.type vuln_loop_offbyone, @function
vuln_loop_offbyone:
    pushq %rbp
    movq %rsp, %rbp
    subq $0x20, %rsp
    movq %rdi, %rsi
    leaq -0x10(%rbp), %rdi
    xorl %ecx, %ecx
.Loff:
    cmpq $0x10, %rcx
    jae .Loffdone
    movb (%rsi,%rcx), %al
    movb %al, (%rdi,%rcx)
    incq %rcx
    jmp .Loff
.Loffdone:
    movb $0, (%rdi,%rcx)
    leave
    ret
.size vuln_loop_offbyone, .-vuln_loop_offbyone

.globl vuln_loop_reverse
.type vuln_loop_reverse, @function
vuln_loop_reverse:
    pushq %rbp
    movq %rsp, %rbp
    subq $0x20, %rsp
    movq %rdi, %rsi
    leaq -0x10(%rbp), %rdi
    xorl %ecx, %ecx
.Lrev:
    movb (%rsi,%rcx), %al
    movb %al, (%rdi,%rcx)
    testb %al, %al
    je .Lrevdone
    incq %rcx
    jmp .Lrev
.Lrevdone:
    leave
    ret
.size vuln_loop_reverse, .-vuln_loop_reverse

.globl vuln_loop_newline
.type vuln_loop_newline, @function
vuln_loop_newline:
    pushq %rbp
    movq %rsp, %rbp
    subq $0x20, %rsp
    movq %rdi, %rsi
    leaq -0x10(%rbp), %rdi
    xorl %ecx, %ecx
.Lnl:
    movb (%rsi,%rcx), %al
    movb %al, (%rdi,%rcx)
    testb %al, %al
    je .Lnldone
    cmpb $10, %al
    je .Lnldone
    incq %rcx
    jmp .Lnl
.Lnldone:
    leave
    ret
.size vuln_loop_newline, .-vuln_loop_newline

.section .note.GNU-stack,"",@progbits
