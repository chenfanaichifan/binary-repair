/*
 * Evaluation harness for the verbatim SARD case.
 *
 * The upstream file defines badSink/goodSink plus its own main() under
 * `#ifdef INCLUDEMAIN`.  We do not define that macro, so this file supplies the
 * entry point and the upstream sinks stay untouched.
 *
 *   ./original.elf <ignored>          good path (allocate, read)
 *   ./original.elf <ignored> --uaf    defect path (free, then read)
 *
 * The first argument is accepted for command-line stability and is not read by
 * the sinks; the upstream case derives its buffer itself.
 */
#include <stdio.h>
#include <string.h>

void CWE416_Use_After_Free__malloc_free_char_01_bad(void);
void CWE416_Use_After_Free__malloc_free_char_01_good(void);

int main(int argc, char *argv[])
{
    if (argc < 2 || argc > 3) {
        fprintf(stderr, "usage: %s <ignored> [--uaf]\n", argv[0]);
        return 2;
    }
    if (argc == 3) {
        if (strcmp(argv[2], "--uaf") != 0) {
            fprintf(stderr, "usage: %s <ignored> [--uaf]\n", argv[0]);
            return 2;
        }
        CWE416_Use_After_Free__malloc_free_char_01_bad();
        return 0;
    }
    CWE416_Use_After_Free__malloc_free_char_01_good();
    return 0;
}
