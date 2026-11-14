#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void printLine(const char *s);

/* Normalized Ghidra recovery: type/name edits only; no semantic changes. */
#include <string.h>

void CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(char *data)
{
    char dest[50];
    int i;

    for (i = 0; i < 50; i++) {
        dest[i] = '\0';
    }
    strcpy(dest, data);
    printLine(data);
    return;
}
