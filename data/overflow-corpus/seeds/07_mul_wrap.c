#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void read_data(uint32_t count) {
    uint32_t size = 4;
    uint32_t total_bytes = count * size;
    char *buf = (char *)malloc(total_bytes);
    if (!buf) return;
    for (uint32_t i = 0; i < count; i++) {
        buf[i * size] = 'A';
    }
    free(buf);
}

int main(int argc, char **argv) {
    if (argc > 1) read_data(strtoul(argv[1], NULL, 0));
    return 0;
}
