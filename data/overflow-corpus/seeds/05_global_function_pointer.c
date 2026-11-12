#include <stdio.h>
#include <string.h>

char global_buf[64];
void (*callback_func)(void) = NULL;

void default_func() { printf("Default function executed.\n"); }

void set_data(const char *input) {
    strcpy(global_buf, input);
}

int main(int argc, char **argv) {
    callback_func = default_func;
    if (argc > 1) set_data(argv[1]);
    if (callback_func) callback_func();
    return 0;
}
