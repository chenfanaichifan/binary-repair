/* Reference repair for the reconstructed CWE121 badSink: reject input whose
 * length exceeds dest[50] before the copy, with the contract's stderr/exit. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void badSink(char *data)
{
    char dest[50] = "";
    if (strlen(data) >= sizeof(dest)) {
        fputs("ERROR: input exceeds destination capacity\n", stderr);
        exit(1);
    }
    strcpy(dest, data);
    printf("%s\n", data);
}
