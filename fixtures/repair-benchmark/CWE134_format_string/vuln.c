#include <stdio.h>
void cwe134_bad(const char *src){printf(src,(char *)0x1);}
int main(int argc,char **argv){if(argc!=2){fprintf(stderr,"usage: %s <input>\n",argv[0]);return 2;}cwe134_bad(argv[1]);return 0;}
