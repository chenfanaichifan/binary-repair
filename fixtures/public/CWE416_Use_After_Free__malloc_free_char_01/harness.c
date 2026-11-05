/*
 * Evaluation harness.  It exists so the sink under test is reachable from a
 * fixed command line and so the defect path is selected explicitly rather
 * than depending on data values a caller might not reproduce.
 *
 *   ./original <input>          good path  (read, then free)
 *   ./original <input> --uaf    defect path (free, then read)
 *
 * The harness never decides pass/fail: tests/*.json states the expected
 * bytes and M4 compares them.
 */
#include <stdio.h>
#include <string.h>

void badSink(char *data);
void goodSink(char *data);

#define MAX_INPUT_BYTES 4096

int main(int argc, char *argv[])
{
    size_t length;

    if (argc < 2 || argc > 3) {
        fprintf(stderr, "usage: %s <input> [--uaf]\n", argv[0]);
        return 2;
    }
    length = strlen(argv[1]);
    if (length > MAX_INPUT_BYTES) {
        fprintf(stderr, "ERROR: input exceeds %d bytes\n", MAX_INPUT_BYTES);
        return 1;
    }
    if (argc == 3) {
        if (strcmp(argv[2], "--uaf") != 0) {
            fprintf(stderr, "usage: %s <input> [--uaf]\n", argv[0]);
            return 2;
        }
        badSink(argv[1]);
        return 0;
    }
    goodSink(argv[1]);
    return 0;
}
