/*
 * Reconstructed from main() at 0x401256 in the committed original.elf.
 *
 * Upstream: the evaluation harness that packaged the Juliet test case. Its
 * source was not shipped with the binary; this file is derived from the
 * disassembly, which is unambiguous at -O0:
 *
 *   401269  cmp  DWORD PTR [rbp-0x4],0x2      ; argc
 *   40126d  je   401296                        ; argc == 2 -> sink
 *   40126f  ...  rdx = argv[0]                 ; first fprintf argument
 *   40127d  esi = 0x402004                     ; "usage: %s <input>\n"
 *   40128a  call fprintf
 *   40128f  eax = 2                            ; exit status for bad usage
 *   401296  ...  rdi = argv[1]
 *   4012a4  call badSink
 *   4012a9  eax = 0
 *
 * The harness never calls goodG2BSink, which is why the good path is dead code
 * in this binary.
 */
#include <stdio.h>

#include "std_testcase.h"

void CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(char * data);

int main(int argc, char * argv[])
{
    if (argc != 2)
    {
        fprintf(stderr, "usage: %s <input>\n", argv[0]);
        return 2;
    }

    CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink(argv[1]);
    return 0;
}
