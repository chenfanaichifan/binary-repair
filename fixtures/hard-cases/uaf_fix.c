/* Reference repair: read the block before free() (or do not free it). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void CWE416_Use_After_Free__malloc_free_char_01_bad(void)
{
    char *data = (char *)malloc(100);
    if (data == NULL) exit(1);
    memset(data, 'A', 99);
    data[99] = '\0';
    printf("%s\n", data);
    free(data); /* the read happens before free; no use-after-free */
}
