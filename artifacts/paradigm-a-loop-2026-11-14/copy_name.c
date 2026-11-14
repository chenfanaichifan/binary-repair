
uint copy_name(long param_1,long param_2,uint param_3)

{
  uint local_c;
  
  for (local_c = 0; local_c < param_3; local_c = local_c + 1) {
    *(undefined1 *)(param_1 + (ulong)local_c) = *(undefined1 *)(param_2 + (ulong)local_c);
  }
  *(undefined1 *)(param_1 + (ulong)local_c) = 0;
  return local_c;
}

