/* Heap destination capacity hard case: same-function malloc -> strcpy.
 *
 * Vulnerability
 * -------------
 * ``heap_bad`` copies argv[1] into a 16-byte heap block with an unbounded
 * strcpy.  A 64-byte input overruns the chunk and glibc aborts on ``free``, so
 * the unpatched binary is an observable crash (SIGABRT, nonzero exit).
 *
 * Repair target
 * -------------
 * The deterministic analyzer must recover the capacity (16) from the immediate
 * malloc argument and emit an ``unbounded_copy`` sink with
 * ``destination_kind == "heap"``.  The writer redirects the strcpy call into an
 * injected bounded-copy guard, which truncates at 15 bytes and NUL-terminates.
 * The guarded candidate therefore prints the truncated string and exits 0
 * (the guard returns 1 in eax on overflow, but this call site ignores the
 * strcpy return value exactly like the original code did; the guard has no
 * stderr and does not exit by itself).
 *
 * Deliberate shape
 * ----------------
 * There is intentionally no ``if (dst == NULL) exit(2)`` check between malloc
 * and strcpy: heap recovery is fail-closed on any branch between the
 * allocation and the copy, so a NULL check would (correctly) make the sink
 * unrecoverable.  This fixture is a single basic block on purpose.
 *
 * Build (inside the Lima guest; the built ELF is checked in at
 * fixtures/hard-cases/vuln-heap-malloc-x86_64.elf, ~16 KiB):
 *
 *   x86_64-linux-gnu-gcc-13 -O2 -g0 -fno-stack-protector \
 *       -fcf-protection=none -fno-plt -U_FORTIFY_SOURCE \
 *       -D_FORTIFY_SOURCE=0 -fno-pie -no-pie \
 *       -o /tmp/vuln-heap-malloc-x86_64.elf \
 *       fixtures/hard-cases/heap_capacity.c
 *
 * Build-flag rationale:
 * - ``-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0``: the host gcc enables
 *   _FORTIFY_SOURCE at -O2, which would rewrite the call as
 *   __strcpy_chk(dst, src, 16) and remove the plain strcpy the guard targets.
 * - ``-fno-plt``: calls become ``call *sym@GOTPCREL(%rip)`` (FF 15), which
 *   containers._elf_imports resolves through the GOT-slot relocations.  The
 *   default CET/x86-64 dynamic layout routes calls through ``.plt.sec``
 *   (endbr64 + jmp *GOT), which the current container parser does not resolve;
 *   that is a separate engine gap and this fixture deliberately avoids it so
 *   the heap-recovery feature can be tested on its own.
 * - Dynamic linking (not -static) keeps the fixture small (static glibc is
 *   ~775 KiB and routes strcpy through an IFUNC PLT stub that is not resolved
 *   either).
 * - ``-fcf-protection=none`` keeps the target function a clean single basic
 *   block without a leading endbr64.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void heap_bad(char *src)
{
    char *dst = (char *)malloc(16);
    strcpy(dst, src);
    puts(dst);
    free(dst);
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    heap_bad(argv[1]);
    return 0;
}
