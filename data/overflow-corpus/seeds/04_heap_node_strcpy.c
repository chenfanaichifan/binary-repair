#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct Node {
    char data[16];
    struct Node *next;
} Node;

void add_node(const char *content) {
    Node *new_node = (Node *)malloc(sizeof(Node));
    strcpy(new_node->data, content);
    new_node->next = NULL;
    printf("Node added.\n");
}

int main(int argc, char **argv) {
    if (argc > 1) add_node(argv[1]);
    return 0;
}
