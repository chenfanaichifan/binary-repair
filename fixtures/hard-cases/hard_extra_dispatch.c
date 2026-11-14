#include <stdio.h>
#include <string.h>
void vuln_loop8(const char *src);
void vuln_loop64(const char *src);
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    if (!strcmp(argv[1], "loop8")) vuln_loop8(argv[2]);
    else if (!strcmp(argv[1], "loop64")) vuln_loop64(argv[2]);
    else return 2;
    return 0;
}
