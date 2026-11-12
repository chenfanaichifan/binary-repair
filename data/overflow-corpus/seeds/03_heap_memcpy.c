#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void process_data(const char *data, int len) {
    char *heap_buf = (char *)malloc(128);
    if (!heap_buf) return;
    memcpy(heap_buf, data, len);
    printf("Data processed.\n");
    free(heap_buf);
}

int main(int argc, char **argv) {
    if (argc > 1) process_data(argv[1], strlen(argv[1]));
    return 0;
}
