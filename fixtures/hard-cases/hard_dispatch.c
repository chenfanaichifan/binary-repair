/* Dispatcher for the synthetic hard-case benchmark.  The target functions are
 * implemented in hard_loops.S; this driver never determines the vulnerability. */
#include <stdio.h>
#include <string.h>

void vuln_loop16(const char *src);
void vuln_loop32(const char *src);
void vuln_loop_offbyone(const char *src);
void vuln_loop_reverse(const char *src);
void vuln_loop_newline(const char *src);

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: %s <case> <input>\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "loop16") == 0) vuln_loop16(argv[2]);
    else if (strcmp(argv[1], "loop32") == 0) vuln_loop32(argv[2]);
    else if (strcmp(argv[1], "offbyone") == 0) vuln_loop_offbyone(argv[2]);
    else if (strcmp(argv[1], "reverse") == 0) vuln_loop_reverse(argv[2]);
    else if (strcmp(argv[1], "newline") == 0) vuln_loop_newline(argv[2]);
    else return 2;
    return 0;
}
