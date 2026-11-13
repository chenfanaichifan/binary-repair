// Reference repair for fixtures/elf/vuln-loop-x86_64.elf.
// The loop is capped at capacity-1 and always NUL-terminates.
.intel_syntax noprefix
.text
.globl repair_entry
repair_entry:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov rsi, rdi
    lea rdi, [rbp-16]
    xor ecx, ecx
.Lloop:
    cmp ecx, 15
    jae .Ldone
    mov al, byte ptr [rsi+rcx]
    mov byte ptr [rdi+rcx], al
    test al, al
    je .Ldone
    inc ecx
    jmp .Lloop
.Ldone:
    mov byte ptr [rdi+rcx], 0
    leave
    ret
