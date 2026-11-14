/* LD_PRELOAD errno probe for dynamic ELF PoC runs.
 * Writes the process's current errno at normal exit to $BR_ERRNO_PATH.
 * This is intentionally process-exit errno, not an arbitrary function-return
 * capture; the caller must label it accordingly.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static const char *errno_path;
static int written;

static void dump_errno(void)
{
    if (written || !errno_path) {
        return;
    }
    written = 1;
    char buf[64];
    int n = snprintf(buf, sizeof(buf), "BR_ERRNO=%d\n", errno);
    int fd = open(errno_path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd >= 0) {
        if (n > 0) {
            (void)write(fd, buf, (size_t)n);
        }
        (void)close(fd);
    }
}

__attribute__((constructor)) static void init_errno_dumper(void)
{
    errno_path = getenv("BR_ERRNO_PATH");
    if (errno_path) {
        (void)atexit(dump_errno);
    }
}

__attribute__((destructor)) static void fini_errno_dumper(void)
{
    dump_errno();
}
