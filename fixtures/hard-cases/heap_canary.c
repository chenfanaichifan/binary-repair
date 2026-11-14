/* Heap hard case with an observable canary: no native crash is required.
 * A 16-byte heap buffer is followed by a guard in one allocation.  Overflowing
 * the buffer corrupts the guard; the program prints HEAP GUARD CORRUPT and
 * exits 1.  A correct repair must reject/truncate the oversized input and keep
 * the guard intact. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct block {
    char data[16];
    unsigned long guard;
};

void heap_bad(char *src)
{
    struct block *b = (struct block *)malloc(sizeof(struct block));
    if (b == NULL) exit(2);
    b->guard = 0xDEADBEEFCAFEBABEUL;
    strcpy(b->data, src);
    if (b->guard != 0xDEADBEEFCAFEBABEUL) {
        fputs("HEAP GUARD CORRUPT\n", stderr);
        exit(1);
    }
    puts(b->data);
    free(b);
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    heap_bad(argv[1]);
    return 0;
}
