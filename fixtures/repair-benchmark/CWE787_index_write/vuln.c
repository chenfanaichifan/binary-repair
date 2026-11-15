#include <stdio.h>
#include <stdlib.h>

void cwe787_bad(const char *src)
{
    char dst[16];
    int index = atoi(src);
    if (index < 0) {
        return;
    }
    dst[index] = 'X';
    puts("ok");
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s <index>\n", argv[0]);
        return 2;
    }
    cwe787_bad(argv[1]);
    return 0;
}
