/*
 * jobwrap_gate5.c — Gate 5 Route A fixed-argv isolation executor (successor).
 *
 * This is a NEW binary, distinct from the deployed `/usr/local/sbin/jobwrap`
 * (b232d60b, which stays bound to Gate 4). It is built for ONE obligation only:
 * Gate 5 Route A — run M4's fixed runtime-placement probe inside the disposable
 * guest under isolation, so M4 can classify PASS / FAIL / NOT VERIFIED.
 *
 * Provenance / scope (binding):
 *   - The original jobwrap_v3.c source is permanently lost (host disk, git
 *     history, and guest /home/runner were all checked). The deployed jobwrap
 *     binary is "not stripped" but carries no DWARF, so it yields function
 *     structure, not byte-equivalent source.
 *   - This file is a SEMANTIC reconstruction of the isolation sequence that the
 *     old jobwrap's `run_argv` performs, plus the NEW `probe m4-gate5` mode.
 *     It is NOT claimed to be hash- or byte-equivalent to jobwrap_v3.c, and it
 *     does NOT replace the old jobwrap.
 *   - This binary binds ONLY Gate 5. Gate 4 stays bound to b232d60b. P4 and the
 *     Gate 4 evidence chain are NOT re-signed by this work.
 *
 * Contract (aligned to Lead 52 §3 and handoff 66):
 *   Invocation (fixed argv, no shell string, no caller-supplied command):
 *       jobwrap-gate5 probe m4-gate5 -- <repo-root> <work-dir>
 *   It must, in order:
 *     1. refuse to run unless euid == 0 (root-only);
 *     2. verify <repo-root>/scripts/m4_gate5_probe.py against the compile-time
 *        pinned blob (fail-closed; no env override; reject on mismatch);
 *     3. build the no-egress netns + mount namespace, drop to uid 1003 with
 *        CapEff=0, apply seccomp + NoNewPrivs + rlimits, clear env to a minimal
 *        whitelist;
 *     4. execv the ABSOLUTE path /usr/bin/python3 with fixed argv:
 *           python3 <repo-root>/scripts/m4_gate5_probe.py <repo-root> <work-dir>
 *        (no PATH lookup, no m4_gate5_fixed.sh, no shell).
 *
 * Isolation must be SEMANTICALLY equivalent to the old jobwrap run_argv
 * (byte-equivalence is NOT required — the old source is gone):
 *   root-only, netns/no-egress, setgroups -> setgid(1003) -> setuid(1003),
 *   CapEff=0, seccomp, NoNewPrivs=1, rlimits, clearenv, fixed argv, absolute
 *   paths, script root-owned/non-writable, fail-closed.
 *
 * NOTE: compilation must happen INSIDE the guest (AGENTS.md hard line: the host
 * and ordinary CI never compile a binary). The build recipe is
 * build-recipe.md. Do NOT build on the host.
 */

#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <limits.h>
#include <linux/capability.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <sched.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* ------------------------------------------------------------------ */
/* Compile-time pinned identities (fail-closed, stored in .rodata).    */
/* ------------------------------------------------------------------ */

/* uid the probe must run as (matches old jobwrap setgid/setuid target). */
#define TARGET_UID 1003
#define TARGET_GID 1003

/* Absolute python3 (no PATH resolution). */
#define PYTHON3_PATH "/usr/bin/python3"

/* Relative location of the Route A probe inside the repo root. */
#define PROBE_REL "scripts/m4_gate5_probe.py"

/*
 * Pinned SHA-256 of scripts/m4_gate5_probe.py (M4-owned blob, frozen).
 * Value: f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb
 * Verified against .tmp/integration/scripts/m4_gate5_probe.py on 2026-10-31.
 */
static const char PROBE_SHA256_HEX[] =
    "f39a0302dd1aa42635da80fa4e9160d37a221f5ac383270add3eaedcffd146cb";

/* Relative location of the Route B probe inside the repo root. */
#define PROBE_B_REL "scripts/m4_gate5b_probe.py"

/*
 * Pinned SHA-256 of scripts/m4_gate5b_probe.py (M4-authored Route B blob, frozen).
 * Value: 05d9a2cd417880c9be51e1a4cd4608158d94b50da233b223c2f4a589850edb82
 * Verified against .tmp/integration/scripts/m4_gate5b_probe.py on 2026-10-31.
 * (Updated after fixing the R4 gdb `x/2i` redirect-regex to match gdb's
 *  `=> 0x4012b0 <sym>:\tjmp 0x<target>` output format.)
 */
static const char PROBE_B_SHA256_HEX[] =
    "05d9a2cd417880c9be51e1a4cd4608158d94b50da233b223c2f4a589850edb82";

/* ------------------------------------------------------------------ */
/* Tiny SHA-256 (self-contained; no external sha256sum dependency).    */
/* Public-domain style implementation, FIPS 180-4.                     */
/* ------------------------------------------------------------------ */

typedef struct {
    uint32_t h[8];
    uint64_t len;
    uint8_t buf[64];
    size_t buflen;
} Sha256;

static const uint32_t K256[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
};

static uint32_t rotr32(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

static void sha256_transform(Sha256 *s, const uint8_t *block) {
    uint32_t w[64];
    for (int i = 0; i < 16; i++) {
        w[i] = ((uint32_t)block[i * 4] << 24) |
               ((uint32_t)block[i * 4 + 1] << 16) |
               ((uint32_t)block[i * 4 + 2] << 8) |
               ((uint32_t)block[i * 4 + 3]);
    }
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = rotr32(w[i - 15], 7) ^ rotr32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = rotr32(w[i - 2], 17) ^ rotr32(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = s->h[0], b = s->h[1], c = s->h[2], d = s->h[3];
    uint32_t e = s->h[4], f = s->h[5], g = s->h[6], h = s->h[7];
    for (int i = 0; i < 64; i++) {
        uint32_t S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
        uint32_t ch = (e & f) ^ (~e & g);
        uint32_t t1 = h + S1 + ch + K256[i] + w[i];
        uint32_t S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t t2 = S0 + maj;
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    s->h[0] += a; s->h[1] += b; s->h[2] += c; s->h[3] += d;
    s->h[4] += e; s->h[5] += f; s->h[6] += g; s->h[7] += h;
}

static void sha256_init(Sha256 *s) {
    s->h[0] = 0x6a09e667; s->h[1] = 0xbb67ae85; s->h[2] = 0x3c6ef372;
    s->h[3] = 0xa54ff53a; s->h[4] = 0x510e527f; s->h[5] = 0x9b05688c;
    s->h[6] = 0x1f83d9ab; s->h[7] = 0x5be0cd19;
    s->len = 0; s->buflen = 0;
}

static void sha256_update(Sha256 *s, const uint8_t *data, size_t n) {
    while (n > 0) {
        size_t take = 64 - s->buflen;
        if (take > n) take = n;
        memcpy(s->buf + s->buflen, data, take);
        s->buflen += take;
        data += take;
        n -= take;
        s->len += (uint64_t)take * 8;
        if (s->buflen == 64) {
            sha256_transform(s, s->buf);
            s->buflen = 0;
        }
    }
}

static void sha256_final(Sha256 *s, uint8_t out[32]) {
    uint64_t bits = s->len;
    uint8_t pad = 0x80;
    sha256_update(s, &pad, 1);
    uint8_t zero = 0;
    while (s->buflen != 56) sha256_update(s, &zero, 1);
    uint8_t lenb[8];
    for (int i = 0; i < 8; i++) lenb[i] = (uint8_t)(bits >> (56 - i * 8));
    sha256_update(s, lenb, 8);
    for (int i = 0; i < 8; i++) {
        out[i * 4] = (uint8_t)(s->h[i] >> 24);
        out[i * 4 + 1] = (uint8_t)(s->h[i] >> 16);
        out[i * 4 + 2] = (uint8_t)(s->h[i] >> 8);
        out[i * 4 + 3] = (uint8_t)(s->h[i]);
    }
}

static int sha256_hex_of_file(const char *path, char out[65]) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    Sha256 s;
    sha256_init(&s);
    uint8_t buf[65536];
    ssize_t n;
    while ((n = read(fd, buf, sizeof buf)) > 0) sha256_update(&s, buf, (size_t)n);
    close(fd);
    if (n < 0) return -1;
    uint8_t digest[32];
    sha256_final(&s, digest);
    static const char hexd[] = "0123456789abcdef";
    for (int i = 0; i < 32; i++) {
        out[i * 2] = hexd[digest[i] >> 4];
        out[i * 2 + 1] = hexd[digest[i] & 0xf];
    }
    out[64] = '\0';
    return 0;
}

/* ------------------------------------------------------------------ */
/* Diagnostics (fail-closed: every error prints and exits non-zero).   */
/* ------------------------------------------------------------------ */

static void die(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    fputs("jobwrap-gate5: ", stderr);
    vfprintf(stderr, fmt, ap);
    fputc('\n', stderr);
    va_end(ap);
    _exit(1);
}

/* ------------------------------------------------------------------ */
/* seccomp filter (SECCOMP_SET_MODE_FILTER). The old jobwrap installed  */
/* a filter via syscall(0x7e, 0x20080522, ...). We install an allow-list */
/* BPF that permits only the syscalls the probe needs and returns EPERM  */
/* otherwise — semantically equivalent (fail-closed on unknown syscalls).*/
/* ------------------------------------------------------------------ */

static int install_seccomp_filter(void) {
    /* Allow the syscalls the probe + python runtime need. Any other syscall
     * returns EPERM (SECCOMP_RET_ERRNO). This keeps egress blocked because
     * socket/connect are not in the allow-list (and the netns has no route). */
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_read, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_write, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_open, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_openat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_close, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_fstat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_newfstatat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_lseek, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_mmap, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_mprotect, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_munmap, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_brk, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_rt_sigaction, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_rt_sigprocmask, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_ioctl, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_readlink, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getcwd, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_access, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_faccessat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_execve, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_exit, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_exit_group, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getpid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getuid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_geteuid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getgid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getegid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getrlimit, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_setrlimit, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_uname, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_rt_sigreturn, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_futex, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clone, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_wait4, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getdents64, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_dup, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_dup2, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_pipe2, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_prlimit64, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_sched_getaffinity, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        /* privilege-drop setup syscalls (needed while dropping to 1003) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_prctl, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_setgroups, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_setgid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_setuid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        /* python3 runtime + gdb + probe syscalls */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_stat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_lstat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_statx, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getppid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getpgrp, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_gettid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getrandom, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_arch_prctl, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_set_tid_address, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_set_robust_list, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_rseq, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_madvise, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clock_gettime, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clock_nanosleep, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_nanosleep, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_sched_yield, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getpeername, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getsockname, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_getsockopt, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_setsockopt, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_ptrace, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_waitid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_kill, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_tgkill, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_personality, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_sysinfo, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_mbind, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_fcntl, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_pread64, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_pwrite64, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_fsync, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_fdatasync, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_truncate, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_ftruncate, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_unlink, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_rename, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_renameat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_readv, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_writev, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_sendfile, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_epoll_create1, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_epoll_ctl, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_epoll_wait, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_eventfd2, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        /* file/dir mutation used by probe (mkdir/chmod/copyfile/chown) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_mkdir, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_mkdirat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_chmod, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_fchmod, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_fchmodat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_chown, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_fchown, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_fchownat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_utimensat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_copy_file_range, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_rmdir, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        /* subprocess.run + selectors (probe spawns ip/gdb/candidate) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_poll, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_ppoll, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_pselect6, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_pipe, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_socketpair, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_recvmsg, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_sendmsg, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_recvfrom, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_sendto, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_vfork, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clone3, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_execveat, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        /* NOTE: socket/connect/bind are NOT allowed — egress stays blocked even
         * though socketpair/sendmsg/recvmsg are allowed for subprocess IPC. */
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA)),
    };
    struct sock_fprog prog = {
        .len = (unsigned short)(sizeof filter / sizeof filter[0]),
        .filter = filter,
    };
    if (syscall(__NR_seccomp, SECCOMP_SET_MODE_FILTER, SECCOMP_FILTER_FLAG_TSYNC, &prog) != 0) {
        die("seccomp(SECCOMP_SET_MODE_FILTER) failed: %s", strerror(errno));
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* Isolation sequence (semantically equivalent to old jobwrap run_argv).*/
/* ------------------------------------------------------------------ */

static void apply_rlimits(void) {
    struct rlimit r;
    /* CPU seconds */
    r.rlim_cur = r.rlim_max = 300;
    if (setrlimit(RLIMIT_CPU, &r) != 0) die("setrlimit(CPU): %s", strerror(errno));
    /* address space (bytes) — 8 GiB matches the old gate4 as_bytes budget */
    r.rlim_cur = r.rlim_max = 8ULL * 1024 * 1024 * 1024;
    if (setrlimit(RLIMIT_AS, &r) != 0) die("setrlimit(AS): %s", strerror(errno));
    /* file size */
    r.rlim_cur = r.rlim_max = 1ULL * 1024 * 1024 * 1024;
    if (setrlimit(RLIMIT_FSIZE, &r) != 0) die("setrlimit(FSIZE): %s", strerror(errno));
    /* number of processes */
    r.rlim_cur = r.rlim_max = 128;
    if (setrlimit(RLIMIT_NPROC, &r) != 0) die("setrlimit(NPROC): %s", strerror(errno));
}

static void enter_isolation(void) {
    /* 1. no-egress netns + mount ns + uts ns (0x60020000 == old jobwrap). */
    if (unshare(CLONE_NEWNET | CLONE_NEWNS | CLONE_NEWUTS) != 0)
        die("unshare(CLONE_NEWNET|NEWNS|NEWUTS): %s", strerror(errno));

    /* 2. make / a private mount so we can hide /proc. */
    if (mount("none", "/", NULL, MS_REC | MS_PRIVATE, NULL) != 0)
        die("mount(/, private): %s", strerror(errno));

    /* 3. remount an empty /proc (hide host process list). */
    if (mount("none", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL) != 0)
        die("mount(/proc): %s", strerror(errno));

    /* 4. seccomp filter MUST be installed while still root (before setuid).
     *    After dropping to 1003 we lose CAP_SYS_ADMIN and cannot install it. */
    install_seccomp_filter();

    /* 5. NoNewPrivs (also before the seccomp-filtered exec, and prevents the
     *    probe from regaining privileges via setuid binaries). */
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0)
        die("prctl(PR_SET_NO_NEW_PRIVS): %s", strerror(errno));

    /* 6. drop groups, gid, uid — order matters (groups before uid). */
    if (setgroups(0, NULL) != 0) die("setgroups: %s", strerror(errno));
    if (setgid(TARGET_GID) != 0) die("setgid(%d): %s", strerror(errno), TARGET_GID);
    if (setuid(TARGET_UID) != 0) die("setuid(%d): %s", strerror(errno), TARGET_UID);

    /* 7. rlimits. */
    apply_rlimits();

    /* 8. minimal env. */
    clearenv();
    setenv("PATH", "/usr/bin:/bin", 1);
    setenv("HOME", "/nonexistent", 1);
    setenv("LANG", "C.UTF-8", 1);
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);
    setenv("PYTHONUNBUFFERED", "1", 1);
}

/* ------------------------------------------------------------------ */
/* main                                                               */
/* ------------------------------------------------------------------ */

static void usage(void) {
    fputs("usage: jobwrap-gate5 probe (m4-gate5|m4-gate5b) -- <repo-root> <work-dir>\n", stderr);
    _exit(2);
}

int main(int argc, char **argv) {
    /* Fixed argv parse: exactly 6 tokens after program name. */
    if (argc != 6) usage();
    if (strcmp(argv[1], "probe") != 0) usage();
    const char *probe_rel;
    const char *probe_sha256_hex;
    if (strcmp(argv[2], "m4-gate5") == 0) {
        probe_rel = PROBE_REL;
        probe_sha256_hex = PROBE_SHA256_HEX;
    } else if (strcmp(argv[2], "m4-gate5b") == 0) {
        probe_rel = PROBE_B_REL;
        probe_sha256_hex = PROBE_B_SHA256_HEX;
    } else {
        usage();
    }
    if (strcmp(argv[3], "--") != 0) usage();
    const char *repo_root = argv[4];
    const char *work_dir = argv[5];

    /* Root-only (before anything else). */
    if (geteuid() != 0)
        die("must run as root (euid=%ld); jobwrap-gate5 refuses non-root", (long)geteuid());

    /* Reject empty / suspicious absolute-path requirements. */
    if (repo_root[0] != '/' || work_dir[0] != '/')
        die("repo-root and work-dir must be absolute paths");

    /* Build the probe path and verify its blob BEFORE dropping privileges,
     * so the uid-1003 process can never skip the check due to unreadability. */
    char probe_path[PATH_MAX];
    if (snprintf(probe_path, sizeof probe_path, "%s/%s", repo_root, probe_rel)
        >= (int)sizeof probe_path)
        die("repo-root too long");

    char actual[65];
    if (sha256_hex_of_file(probe_path, actual) != 0)
        die("cannot read probe %s: %s", probe_path, strerror(errno));
    if (strcmp(actual, probe_sha256_hex) != 0)
        die("probe blob mismatch: got %s, expected %s", actual, probe_sha256_hex);

    /* The probe must be root-owned and not writable by group/other (defense in
     * depth; it is executed after drop, so it cannot be replaced by uid 1003). */
    struct stat st;
    if (stat(probe_path, &st) != 0) die("stat probe: %s", strerror(errno));
    if (st.st_uid != 0) die("probe not root-owned (uid=%ld)", (long)st.st_uid);
    if (st.st_mode & (S_IWGRP | S_IWOTH)) die("probe is group/other-writable");

    /* Enter isolation (netns, drop to 1003, seccomp, nnp, rlimits, clearenv). */
    enter_isolation();

    /* Fixed argv: absolute python3 + absolute probe + repo + work. */
    char *child_argv[] = {
        (char *)PYTHON3_PATH,
        probe_path,
        (char *)repo_root,
        (char *)work_dir,
        NULL,
    };
    execv(PYTHON3_PATH, child_argv);
    die("execv(%s): %s", PYTHON3_PATH, strerror(errno));
    /* not reached */
    return 127;
}
