/*
 * Fixture harness for:
 *   CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b
 *
 * This file is evaluator-side build infrastructure. It is NOT part of the
 * repair input and must not be shipped to the repair provider.
 *
 * The Juliet case file is compiled unmodified. Its exported sink is called
 * directly with argv[1], so the input string is the caller-provided buffer
 * (no copy, no truncation, no validation) and the overflow happens inside
 * the Juliet sink's own stack frame.
 */

#include <stdio.h>

void CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(char *data);

int main(int argc, char **argv)
{
    if (argc != 2)
    {
        fprintf(stderr, "usage: %s <input>\n", argv[0]);
        return 2;
    }

    CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(argv[1]);
    return 0;
}
