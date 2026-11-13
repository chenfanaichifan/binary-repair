/* Negative control: a valid 32-bit PE that is outside the repair matrix.
 *
 * The pipeline must detect it as PE/i386, report it as unsupported and never
 * write a candidate.  It intentionally contains an unbounded strcpy call so a
 * naive scanner cannot claim "nothing to repair".
 */
#include <string.h>

void control_copy(const char *s) {
    char buf[16];
    strcpy(buf, s);
}

int main(void) {
    control_copy("AAAAAAAA");
    return 0;
}
