#include <stdio.h>
#include <stdlib.h>
void cwe476_bad(const char *src){char *p=NULL;if(atoi(src)==0&&p!=NULL)*p='x';puts("ok");}
