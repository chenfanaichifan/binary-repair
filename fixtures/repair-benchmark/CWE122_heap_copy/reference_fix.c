#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void cwe122_bad(const char *src)
{
    char *dst = (char *)malloc(16);
    if (dst == NULL) {
        exit(1);
    }
    if (strlen(src) >= 16) {
        fputs("ERROR: input exceeds destination capacity\n", stderr);
        free(dst);
        exit(1);
    }
    memcpy(dst, src, strlen(src) + 1);
    puts(dst);
    free(dst);
}
