
void multicall_bad(undefined8 param_1)

{
  long in_FS_OFFSET;
  char local_28 [24];
  long local_10;
  
  local_10 = *(long *)(in_FS_OFFSET + 0x28);
  helper_copy(local_28,param_1);
  puts(local_28);
  if (*(long *)(in_FS_OFFSET + 0x28) != local_10) {
                    /* WARNING: Subroutine does not return */
    __stack_chk_fail();
  }
  return;
}

