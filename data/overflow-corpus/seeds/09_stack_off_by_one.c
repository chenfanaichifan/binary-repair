#include <stdio.h>
#include <string.h>

void copy_string(const char *src, int len) {
    char buffer[32];
    for (int i = 0; i <= len; i++) {
        buffer[i] = src[i];
        if (src[i] == '\0') break;
    }
}

int main(int argc, char **argv) {
    if (argc > 1) copy_string(argv[1], strlen(argv[1]));
    return 0;
}
