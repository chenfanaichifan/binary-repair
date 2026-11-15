#include <stdio.h>
#include <stdlib.h>

void cwe787_bad(const char *src)
{
    char dst[16];
    int index = atoi(src);
    if (index < 0 || index >= 16) {
        return;
    }
    dst[index] = 'X';
    puts("ok");
}
