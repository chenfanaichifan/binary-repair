#include <stdio.h>
#include <stdlib.h>
void cwe125_bad(const char *src){char dst[16]="0123456789abcdef";int idx=atoi(src);if(idx<0||idx>=16)return;printf("%c\n",dst[idx]);}
