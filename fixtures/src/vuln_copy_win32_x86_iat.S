// PE32 x86 (MinGW / cdecl) with a *direct* IAT import call.
//
// Unlike vuln_copy_win32_x86.S (which calls the `_strcpy` import thunk), this
// fixture branches straight through the import address table:
//
//     calll *__imp__strcpy     ->  FF 15 <abs32 IAT slot>
//
// That makes the call site a 6-byte instruction; the repair writer replaces it
// with a 5-byte E8 rel32 plus one NOP.
.text
.globl _vuln_copy
_vuln_copy:
    pushl %ebp
    movl %esp, %ebp
    subl $0x20, %esp
    movl 8(%ebp), %eax
    leal -0x10(%ebp), %edx
    pushl %eax
    pushl %edx
    calll *__imp__strcpy
    addl $8, %esp
    leal -0x10(%ebp), %eax
    pushl %eax
    calll _puts
    addl $4, %esp
    leave
    ret
