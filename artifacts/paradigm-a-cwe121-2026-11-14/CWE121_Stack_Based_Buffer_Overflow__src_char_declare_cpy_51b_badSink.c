
void CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(char *data)

{
  char *data_local;
  char dest [50];
  
  dest[0] = '\0';
  dest[1] = '\0';
  dest[2] = '\0';
  dest[3] = '\0';
  dest[4] = '\0';
  dest[5] = '\0';
  dest[6] = '\0';
  dest[7] = '\0';
  dest[8] = '\0';
  dest[9] = '\0';
  dest[10] = '\0';
  dest[0xb] = '\0';
  dest[0xc] = '\0';
  dest[0xd] = '\0';
  dest[0xe] = '\0';
  dest[0xf] = '\0';
  dest[0x10] = '\0';
  dest[0x11] = '\0';
  dest[0x12] = '\0';
  dest[0x13] = '\0';
  dest[0x14] = '\0';
  dest[0x15] = '\0';
  dest[0x16] = '\0';
  dest[0x17] = '\0';
  dest[0x18] = '\0';
  dest[0x19] = '\0';
  dest[0x1a] = '\0';
  dest[0x1b] = '\0';
  dest[0x1c] = '\0';
  dest[0x1d] = '\0';
  dest[0x1e] = '\0';
  dest[0x1f] = '\0';
  dest[0x20] = '\0';
  dest[0x21] = '\0';
  dest[0x22] = '\0';
  dest[0x23] = '\0';
  dest[0x24] = '\0';
  dest[0x25] = '\0';
  dest[0x26] = '\0';
  dest[0x27] = '\0';
  dest[0x28] = '\0';
  dest[0x29] = '\0';
  dest[0x2a] = '\0';
  dest[0x2b] = '\0';
  dest[0x2c] = '\0';
  dest[0x2d] = '\0';
  dest[0x2e] = '\0';
  dest[0x2f] = '\0';
  dest[0x30] = '\0';
  dest[0x31] = '\0';
  strcpy(dest,data);
  printLine(data);
  return;
}

