// Reference repair for the reconstructed CWE121 badSink.
// This is a harness reference implementation, not model output: it exercises
// the structured failure_behavior contract plus the fixed controlled syscall
// templates (call br_write_stderr / call br_exit_group).
.intel_syntax noprefix
.text
push rbp
mov rbp, rsp
sub rsp, 0x80
mov qword ptr [rbp - 0x08], rdi
xor ecx, ecx
.Llen:
cmp ecx, 0x32
jae .Lreject
cmp byte ptr [rdi + rcx], 0
je .Lcopy
inc ecx
jmp .Llen
.Lcopy:
lea rdi, [rbp - 0x80]
mov rsi, qword ptr [rbp - 0x08]
call strcpy
mov rdi, qword ptr [rbp - 0x08]
call printLine
leave
ret
.Lreject:
call br_write_stderr
call br_exit_group
