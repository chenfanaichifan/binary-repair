#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void append_data(char *base, size_t base_len, const char *input, size_t input_len) {
    if (base_len + input_len > 1024) {
        printf("Data too large!\n");
        return;
    }
    memcpy(base + base_len, input, input_len);
}

int main() {
    char buffer[1024] = {0};
    size_t base_len = 1024;
    char input[32] = "evil_data";
    append_data(buffer, base_len, input, (size_t)-1);
    return 0;
}
