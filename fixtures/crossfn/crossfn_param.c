/* M2 cross-function fixture 1: the vulnerable capacity lives in the caller.
 *
 * copy_payload() performs the unbounded strcpy and only ever sees an opaque
 * destination pointer.  A same-function/leaf-only analyzer cannot recover a
 * capacity for this call: the destination is
 *   path A - wrapper()'s 16-byte stack buffer (capacity = frame geometry), or
 *   path B - ret_buffer()'s return value, a static s_ret[16]
 *            (capacity = ELF STT_OBJECT symbol size).
 * A cross-function prototype must walk back through the call edge and through
 * the return-value edge to recover those capacities.
 *
 * Build with fixtures/crossfn/build.sh (zig 0.17.1, no network):
 *   zig cc -target x86_64-linux-gnu -O0 -g0 -fno-pie -no-pie  *       -fno-stack-protector -o crossfn_param.elf crossfn_param.c
 *
 * Observed runtime behaviour is a Linux x86_64 concern; see README.md and the
 * PoC manifest (this host is macOS arm64, so runtime evidence is not_run here).
 */
#include <stdio.h>
#include <string.h>

/* The sink: destination capacity is unknown inside this function. */
static void copy_payload(char *dst, const char *src)
{
    strcpy(dst, src);
}

/* Path A: 16-byte caller stack buffer, copied through a pointer alias. */
static void wrapper(const char *src)
{
    char buf[16];
    char *alias = buf;
    copy_payload(alias, src);
    puts(buf);
}

/* Path B: 16-byte static buffer returned by a helper. */
static char s_ret[16];

static char *ret_buffer(void)
{
    return s_ret;
}

static void wrapper2(const char *src)
{
    char *dst = ret_buffer();
    copy_payload(dst, src);
    puts(dst);
}

int main(int argc, char **argv)
{
    if (argc > 1) {
        wrapper(argv[1]);
        wrapper2(argv[1]);
    }
    return 0;
}
