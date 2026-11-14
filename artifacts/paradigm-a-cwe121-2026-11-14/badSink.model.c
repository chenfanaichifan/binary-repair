void CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(char *data)
{
    char dest[50];
    int i;
    int len = 0;

    while (data[len] != '\0') {
        len++;
    }

    if (len >= 50) {
        br_fail();
        return;
    }

    for (i = 0; i < len; i++) {
        dest[i] = data[i];
    }
    dest[len] = '\0';

    printLine(data);
    return;
}
