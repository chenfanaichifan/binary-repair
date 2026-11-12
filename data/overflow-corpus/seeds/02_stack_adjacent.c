#include <stdio.h>
#include <string.h>

void check_permission(char *username) {
    int is_admin = 0;
    char name[32];
    strcpy(name, username);
    if (is_admin != 0) {
        printf("Access Granted to Admin!\n");
    } else {
        printf("Access Denied.\n");
    }
}

int main(int argc, char **argv) {
    if (argc > 1) check_permission(argv[1]);
    return 0;
}
