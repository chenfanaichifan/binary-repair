#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
void cwe190_bad(const char *src){int n=atoi(src);if(n<0||n>=INT_MAX)return;char *p=malloc((size_t)n+1);if(p==NULL)exit(1);memcpy(p,src,(size_t)n);p[n]='\0';puts(p);free(p);}
