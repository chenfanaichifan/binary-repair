/* M2 cross-function fixture 2: global destination with a symbol-size capacity.
 *
 * store_out() copies into the file-scope g_out[16].  The capacity is not frame
 * geometry: it comes from the ELF STT_OBJECT symbol size (st_size = 16).  The
 * value being copied comes from the caller (argv[1] through main), so both the
 * object-capacity inference (E-04) and the cross-function source trace (E-02)
 * are needed.
 *
 * Build with fixtures/crossfn/build.sh (zig 0.17.1, no network):
 *   zig cc -target x86_64-linux-gnu -O0 -g0 -fno-pie -no-pie  *       -fno-stack-protector -o crossfn_global.elf crossfn_global.c
 *
 * Observed runtime behaviour is a Linux x86_64 concern; see README.md and the
 * PoC manifest (this host is macOS arm64, so runtime evidence is not_run here).
 */
#include <stdio.h>
#include <string.h>

/* Global destination: capacity 16 from the OBJECT symbol, not the frame. */
static char g_out[16];

static void store_out(const char *src)
{
    strcpy(g_out, src);
}

int main(int argc, char **argv)
{
    if (argc > 1)
        store_out(argv[1]);
    puts(g_out);
    return 0;
}
