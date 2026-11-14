/* Reviewed symbol-safe helper for the model-generated CWE121 patch.
 * The target has no fputs/exit imports; these are x86-64 syscalls. */
extern void printLine(const char *s);

static void br_fail(void)
{
    static const char msg[] = "ERROR: input exceeds destination capacity\n";
    register long rax __asm__("rax") = 1;
    register long rdi __asm__("rdi") = 2;
    register long rsi __asm__("rsi") = (long)msg;
    register long rdx __asm__("rdx") = (long)(sizeof(msg) - 1);
    __asm__ volatile("syscall" : "+r"(rax) : "r"(rdi), "r"(rsi), "r"(rdx)
                     : "rcx", "r11", "memory");
    rax = 60;
    rdi = 1;
    __asm__ volatile("syscall" :: "r"(rax), "r"(rdi) : "rcx", "r11", "memory");
    for (;;) { }
}

void CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(char *data)
{
    char dest[50];
    int i;
    int len = 0;

    while (data[len] != '\0') {
        len++;
    }

    if (len >= 50) {
        br_fail();
        return;
    }

    for (i = 0; i < len; i++) {
        dest[i] = data[i];
    }
    dest[len] = '\0';

    printLine(data);
    return;
}
