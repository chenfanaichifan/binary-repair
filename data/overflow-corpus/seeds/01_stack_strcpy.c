#include <stdio.h>
#include <string.h>

void vulnerable_copy(char *input) {
    char buffer[64];
    strcpy(buffer, input);
    printf("Copied: %s\n", buffer);
}

int main(int argc, char **argv) {
    if (argc > 1) vulnerable_copy(argv[1]);
    return 0;
}
