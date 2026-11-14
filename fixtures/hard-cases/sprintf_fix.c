/* Reference repair for the sprintf hard case: reject input that does not fit
 * the 16-byte destination before the copy. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void sprintf_bad(char *src) {
    char dst[16];
    if (strlen(src) >= sizeof(dst)) {
        fputs("ERROR: input exceeds destination capacity\n", stderr);
        exit(1);
    }
    strcpy(dst, src);
    puts(dst);
}
