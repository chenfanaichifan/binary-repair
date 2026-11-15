#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void cwe190_bad(const char *src){int n=atoi(src);char *p=malloc((size_t)(n+1));if(p==NULL)exit(1);memcpy(p,src,(size_t)n);p[n]='\0';puts(p);free(p);}
int main(int argc,char **argv){if(argc!=2){fprintf(stderr,"usage: %s <len>\n",argv[0]);return 2;}cwe190_bad(argv[1]);return 0;}
