
int puts(char *s)

{
  uchar *puVar1;
  int iVar2;
  bool bVar3;
  
                    /* Unresolved local var: int __need_unlock@[???]
                       Unresolved local var: int r@[???] */
  if (__stdout_FILE.lock < 0) {
    bVar3 = true;
  }
  else {
    iVar2 = __lockfile(&__stdout_FILE);
    bVar3 = iVar2 == 0;
  }
  iVar2 = fputs(s,&__stdout_FILE);
  if (iVar2 < 0) {
    iVar2 = -1;
  }
  else if ((__stdout_FILE.lbf == 10) || (__stdout_FILE.wpos == __stdout_FILE.wend)) {
    iVar2 = __overflow(&__stdout_FILE,10);
    iVar2 = iVar2 >> 0x1f;
  }
  else {
    puVar1 = __stdout_FILE.wpos + 1;
    *__stdout_FILE.wpos = '\n';
    __stdout_FILE.wpos = puVar1;
    iVar2 = 0;
  }
  if (!bVar3) {
    __unlockfile(&__stdout_FILE);
  }
  return iVar2;
}

