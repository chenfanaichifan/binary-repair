#include <stdio.h>

void log_error(const char *msg) {
    char log_buf[128];
    snprintf(log_buf, sizeof(log_buf), "Error: %s\n", msg);
    printf(log_buf);
}

int main(int argc, char **argv) {
    if (argc > 1) log_error(argv[1]);
    return 0;
}
