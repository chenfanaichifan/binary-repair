/* Reference repair for the heap canary case: reject input that does not fit
 * data[16] before the copy. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void heap_bad(char *src)
{
    if (strlen(src) >= 16) exit(0); /* safe, no guard corruption */
    char *data = (char *)malloc(16);
    if (data == NULL) exit(2);
    strcpy(data, src);
    puts(data);
    free(data);
}
