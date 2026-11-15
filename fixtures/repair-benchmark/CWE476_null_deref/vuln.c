#include <stdio.h>
#include <stdlib.h>
void cwe476_bad(const char *src){char *p=NULL;if(atoi(src)==0)*p='x';puts("ok");}
int main(int argc,char **argv){if(argc!=2){fprintf(stderr,"usage: %s <flag>\n",argv[0]);return 2;}cwe476_bad(argv[1]);return 0;}
