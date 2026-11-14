/* Additional hard cases: heap, multi-call, sprintf and non-constant copy.
 * The target functions intentionally call through different layers so the
 * template analyzer cannot recover a stack call-site capacity. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void helper_copy(char *dst, const char *src)
{
    strcpy(dst, src);
}

void heap_bad(char *src)
{
    char *dst = (char *)malloc(16);
    if (dst == NULL) exit(1);
    strcpy(dst, src);
    puts(dst);
    free(dst);
}

void multicall_bad(char *src)
{
    char dst[16];
    helper_copy(dst, src);
    puts(dst);
}

void sprintf_bad(char *src)
{
    char dst[16];
    sprintf(dst, "%s", src);
    puts(dst);
}

void nonconst_bad(char *src)
{
    char dst[16];
    memcpy(dst, src, strlen(src) + 1);
    puts(dst);
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: %s <case> <input>\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "heap") == 0) heap_bad(argv[2]);
    else if (strcmp(argv[1], "multicall") == 0) multicall_bad(argv[2]);
    else if (strcmp(argv[1], "sprintf") == 0) sprintf_bad(argv[2]);
    else if (strcmp(argv[1], "nonconst") == 0) nonconst_bad(argv[2]);
    else return 2;
    return 0;
}
