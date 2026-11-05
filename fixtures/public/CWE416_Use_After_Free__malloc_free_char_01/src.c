/*
 * CWE-416 use after free on a heap block of char, synthetic team sample.
 *
 * NOT imported from an upstream corpus.  PROVENANCE.md says what it is and
 * why: the Juliet mirror the Lead pinned (01e353d) does not resolve, and the
 * host that authored this has no guest compiler, so original.elf is produced
 * later by M3/VMer from build.sh.
 *
 * Scope is deliberately one defect.  duplicate() clamps the copy so the
 * sample cannot also overflow (CWE-121 stays the baseline's job), and the
 * only hazard is badSink reading the buffer after it was freed.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define DEST_CAPACITY 50

/* Copy at most DEST_CAPACITY-1 bytes and terminate.  Clamping keeps
 * out-of-bounds writes out of this sample's defect surface. */
static char *duplicate(const char *data)
{
    size_t n = strlen(data);
    char *buffer;

    if (n >= DEST_CAPACITY) {
        n = DEST_CAPACITY - 1;
    }
    buffer = (char *)malloc(DEST_CAPACITY);
    if (buffer == NULL) {
        return NULL;
    }
    memcpy(buffer, data, n);
    buffer[n] = '\0';
    return buffer;
}

static void printLine(const char *text)
{
    if (text == NULL) {
        return;
    }
    fputs(text, stdout);
    fputc('\n', stdout);
}

/* Defect: the block is released, then read.
 *
 * The read is made observable without a sanitizer by taking a same-size block
 * from the allocator immediately after the free.  glibc serves that request
 * from the tcache LIFO for this size class, so the bytes the stale pointer
 * sees are the sentinel ones and not the original text.  PROVENANCE.md records
 * that this is an observation technique, not a language guarantee; M4 should
 * still run ASan/valgrind where available and let that report win. */
void badSink(char *data)
{
    char *buffer = duplicate(data);
    char *reuse;

    if (buffer == NULL) {
        fputs("ERROR: allocation failed\n", stderr);
        exit(1);
    }
    free(buffer);

    reuse = (char *)malloc(DEST_CAPACITY);
    if (reuse != NULL) {
        memset(reuse, 'X', DEST_CAPACITY - 1);
        reuse[DEST_CAPACITY - 1] = '\0';
    }

    printLine(buffer);   /* read of freed memory */

    free(reuse);
}

/* The correct order: read, then release. */
void goodSink(char *data)
{
    char *buffer = duplicate(data);

    if (buffer == NULL) {
        fputs("ERROR: allocation failed\n", stderr);
        exit(1);
    }
    printLine(buffer);
    free(buffer);
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s <input> [--uaf]\n", argv[0]);
        return 2;
    }
    if (argc > 2 && strcmp(argv[2], "--uaf") == 0) {
        badSink(argv[1]);
    } else {
        goodSink(argv[1]);
    }
    return 0;
}
