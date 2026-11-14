.intel_syntax noprefix
.text
.globl repair_entry
repair_entry:
    push rbp
    mov rbp, rsp
    sub rsp, 0x80
    mov rsi, rdi
    lea rdi, [rbp-8]
    xor ecx, ecx
.Lloop:
    cmp ecx, 7
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
