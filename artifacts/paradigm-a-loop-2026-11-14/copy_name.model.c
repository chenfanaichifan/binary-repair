int copy_name(char *dst, const char *src, unsigned int n)
{
    unsigned int i;
    if (n >= 16) {
        return -1;
    }
    for (i = 0; i < n; i++) {
        dst[i] = src[i];
    }
    dst[i] = '\0';
    return (int)i;
}
