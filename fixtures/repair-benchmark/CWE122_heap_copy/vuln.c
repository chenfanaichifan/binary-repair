#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void cwe122_bad(const char *src)
{
    char *dst = (char *)malloc(16);
    if (dst == NULL) {
        exit(1);
    }
    memcpy(dst, src, strlen(src) + 1);
    puts(dst);
    free(dst);
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s <input>\n", argv[0]);
        return 2;
    }
    cwe122_bad(argv[1]);
    return 0;
}
