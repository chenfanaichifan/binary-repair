/*
 * Reconstructed from the committed original.elf. This is NOT a byte-for-byte
 * copy of the upstream file, and it is not presented as one.
 *
 * Evidence used (all inside original.elf):
 *   - DW_AT_producer: "GNU C17 13.3.0 ... -g -O0 -fno-stack-protector -fno-pie"
 *   - .debug_line_str: the upstream path
 *       juliet-v1.3/C/testcases/CWE121_Stack_Based_Buffer_Overflow/s09/
 *       CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b.c
 *   - symbol table: badSink at 0x4012b0, goodG2BSink at 0x401318
 *   - disassembly of badSink: char dest[50] zero-initialised (50 bytes),
 *     strcpy(dest, data) at 0x401304, then printLine(data) - note it prints
 *     `data`, not `dest`.
 *
 * Upstream artifact: NIST SARD / Juliet Test Suite v1.3 (public domain).
 * Comments and whitespace may differ from upstream; the repair contract and
 * build.json only depend on the observable behaviour, which the disassembly
 * fixes exactly.
 */
#include "std_testcase.h"

#ifndef OMITBAD

void CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(char * data)
{
    {
        char dest[50] = "";
        /* POTENTIAL FLAW: Possible buffer overflow if data is larger than dest */
        strcpy(dest, data);
        printLine(data);
    }
}

#endif /* OMITBAD */

#ifndef OMITGOOD

void CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_goodG2BSink(char * data)
{
    {
        char dest[50] = "";
        /* FIX: data already came from the good source and is length-checked */
        strcpy(dest, data);
        printLine(data);
    }
}

#endif /* OMITGOOD */
