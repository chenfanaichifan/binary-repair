#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void process_heap_string(const char *input) {
    size_t len = strlen(input);
    char *buf = (char *)malloc(len);
    if (!buf) return;
    memcpy(buf, input, len);
    buf[len] = '\0';
    printf("%s\n", buf);
    free(buf);
}

int main(int argc, char **argv) {
    if (argc > 1) process_heap_string(argv[1]);
    return 0;
}
