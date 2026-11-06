/*
 * Fixture harness for:
 *   CWE416_Use_After_Free__malloc_free_char_01
 *
 * This file is evaluator-side build infrastructure. It is NOT part of the
 * repair input and must not be shipped to the repair provider.
 *
 * The Juliet case file is compiled unmodified. Its exported entry point is
 * called directly:
 *
 *   bad()  mallocs 100 bytes, fills them with 'A', frees the block, then reads
 *          it through printLine(). The use-after-free is unconditional -- there
 *          is no input that avoids it -- which is what makes this fixture
 *          deterministic: every run takes the same path to the same defect.
 *
 * Only bad() is called. The case file's own main() (compiled only under
 * INCLUDEMAIN) additionally runs good() and seeds srand() from the wall clock;
 * neither belongs in a fixture.
 */

void CWE416_Use_After_Free__malloc_free_char_01_bad(void);

int main(void)
{
    CWE416_Use_After_Free__malloc_free_char_01_bad();
    return 0;
}
