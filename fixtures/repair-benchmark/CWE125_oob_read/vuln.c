#include <stdio.h>
#include <stdlib.h>
void cwe125_bad(const char *src){char dst[16]="0123456789abcdef";int idx=atoi(src);printf("%c\n",dst[idx]);}
int main(int argc,char **argv){if(argc!=2){fprintf(stderr,"usage: %s <index>\n",argv[0]);return 2;}cwe125_bad(argv[1]);return 0;}
