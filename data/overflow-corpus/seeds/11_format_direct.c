#include <stdio.h>

void vulnerable_printf(char *user_input) {
    printf(user_input);
    printf("\n");
}

int main(int argc, char **argv) {
    if (argc > 1) vulnerable_printf(argv[1]);
    return 0;
}
