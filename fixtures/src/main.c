/* Minimal driver for the assembly copy fixtures.
 *
 * `vuln_copy` is implemented in the per-target assembly file and performs an
 * unbounded strcpy into a 16-byte stack buffer.  The buffer is placed at the
 * top of the callee frame so that the repair engine's frame model
 * (capacity = frame_top - destination) is exact.
 */
#include <stdio.h>

void vuln_copy(const char *src);

int main(int argc, char **argv) {
    if (argc > 1) {
        vuln_copy(argv[1]);
    }
    return 0;
}
