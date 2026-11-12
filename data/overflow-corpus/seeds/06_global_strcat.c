#include <stdio.h>
#include <string.h>

void log_event(const char *event) {
    static char static_log[128];
    strcat(static_log, event);
    strcat(static_log, " | ");
    printf("Log: %s\n", static_log);
}

int main(int argc, char **argv) {
    if (argc > 1) {
        log_event(argv[1]);
        log_event(argv[1]);
    }
    return 0;
}
