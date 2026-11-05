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
 *       jobwrap-gate5 probe m4-gate5b -- <repo-root> <work-dir>
 *       jobwrap-gate5 routea <job-id>          # added per Lead record 72 (path 4)
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
 *   The `routea` mode follows the same isolation, but every value comes from
 *   the root-owned /usr/local/etc/binrepair/routea.conf rather than from the
 *   caller. Its exit codes are 2 (bad argument), 3 (unknown job), 4 (candidate
 *   hash mismatch); the worker's own exit code is propagated verbatim.
 *
 *   Both modes write an isolation attestation from inside the sandbox
 *   (<work-dir>/attestation.json) so the conformance window can check real
 *   uid/gid/CapEff/NoNewPrivs/netns/route values instead of taking them on
 *   trust. A missing attestation is `inconclusive`, never a pass.
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
#include <time.h>
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

/*
 * die_rc — same as die() but with a documented exit code.
 *
 * The routea mode has three documented non-generic codes (JOBWRAP_ROUTEA.md):
 *   3 = unknown job (valid id, no config line)
 *   4 = candidate hash mismatch
 * Everything else stays on 1 so "the wrapper refused for an unlisted reason" is
 * still distinguishable from "the wrapper refused for a documented reason".
 */
static void die_rc(int rc, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    fputs("jobwrap-gate5: ", stderr);
    vfprintf(stderr, fmt, ap);
    fputc('\n', stderr);
    va_end(ap);
    _exit(rc);
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
/* routea mode — Route A fixed-argv executor (T6.2 host driver target) */
/*                                                                     */
/* Added per Lead record 72 (path 4: build a successor with a new fixed */
/* -argv mode rather than rebuilding the lost jobwrap_v3.c).           */
/*                                                                     */
/* Contract (workers/route_a/JOBWRAP_ROUTEA.md):                       */
/*   jobwrap-gate5 routea <job-id>            # exactly this form      */
/*   config: /usr/local/etc/binrepair/routea.conf (root-owned 0600)    */
/*     <job-id> TAB <job-dir> TAB <worker.py> TAB <work-dir> TAB       */
/*     <python> TAB <candidate-sha256>                                 */
/*   exit: 2 bad argument, 3 unknown job, 4 candidate hash mismatch    */
/*                                                                     */
/* The wrapper never takes a path, a binary name, or an argv array from */
/* the caller. Every value comes from the root-owned config, and each  */
/* is re-validated here before it can reach execv.                     */
/* ------------------------------------------------------------------ */

#define ROUTEA_CONF "/usr/local/etc/binrepair/routea.conf"
#define JOBS_ROOT "/var/lib/binrepair/jobs/"
#define FIXED_WORKER "/opt/binrepair/workers/route_a/worker.py"
#define FIXED_PYTHON "/opt/angr-venv/bin/python"
#define EVIDENCE_ROOT "/var/lib/binrepair/evidence"

#define RC_BAD_ARG 2
#define RC_UNKNOWN_JOB 3
#define RC_HASH_MISMATCH 4

struct routea_job {
    char job_dir[PATH_MAX];
    char worker[PATH_MAX];
    char work_dir[PATH_MAX];
    char python[PATH_MAX];
    char cand_sha[65];
};

/* `[A-Za-z0-9._-]{1,64}` — a job id is a token, never a path. */
static int valid_job_id(const char *s) {
    size_t n = strlen(s);
    if (n < 1 || n > 64) return 0;
    for (size_t i = 0; i < n; i++) {
        char c = s[i];
        int ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
                 || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-';
        if (!ok) return 0;
    }
    return 1;
}

static int is_lower_hex64(const char *s) {
    size_t n = strlen(s);
    if (n != 64) return 0;
    for (size_t i = 0; i < n; i++) {
        char c = s[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return 0;
    }
    return 1;
}

static int starts_with(const char *s, const char *prefix) {
    return strncmp(s, prefix, strlen(prefix)) == 0;
}

/*
 * Trim trailing CR/LF/space in place. The config is root-written, but a stray
 * CR (edited on Windows) must not become part of a hash or a path.
 */
static void trim(char *s) {
    size_t n = strlen(s);
    while (n > 0) {
        char c = s[n - 1];
        if (c == '\n' || c == '\r' || c == ' ' || c == '\t') s[--n] = '\0';
        else break;
    }
}

/*
 * Look one job id up in the root-owned config.
 * Returns 0 = found, 1 = unknown job, -1 = config unusable.
 * A config line that fails validation is a hard error, never skipped: a
 * half-valid config must not silently degrade into "job not found".
 */
static int lookup_routea_job(const char *job_id, struct routea_job *out) {
    struct stat st;
    if (stat(ROUTEA_CONF, &st) != 0)
        die_rc(1, "config %s unreadable: %s", ROUTEA_CONF, strerror(errno));
    if (!S_ISREG(st.st_mode))
        die_rc(1, "config %s is not a regular file", ROUTEA_CONF);
    if (st.st_uid != 0)
        die_rc(1, "config %s is not root-owned (uid=%ld)", ROUTEA_CONF, (long)st.st_uid);
    if (st.st_mode & (S_IWGRP | S_IWOTH))
        die_rc(1, "config %s is group/other-writable (mode=%o)",
               ROUTEA_CONF, (unsigned)(st.st_mode & 07777));

    FILE *f = fopen(ROUTEA_CONF, "r");
    if (!f) die_rc(1, "cannot open config %s: %s", ROUTEA_CONF, strerror(errno));

    char line[4096];
    int found = 0;
    while (fgets(line, sizeof line, f)) {
        trim(line);
        if (line[0] == '\0' || line[0] == '#') continue;

        /* Count tabs first: splitting in place destroys the separators, so a
         * 7-field line would otherwise look like a valid 6-field line. */
        int tabs = 0;
        for (const char *p = line; *p; p++)
            if (*p == '\t') tabs++;
        if (tabs != 5)
            die_rc(1, "config %s: a line has %d tab-separated fields, want 6",
                   ROUTEA_CONF, tabs + 1);

        char *field[6] = {0};
        int nf = 0;
        char *cursor = line;
        while (nf < 6) {
            field[nf++] = cursor;
            char *tab = strchr(cursor, '\t');
            if (!tab) break;
            *tab = '\0';
            cursor = tab + 1;
        }
        if (nf != 6)
            die_rc(1, "config %s: could not split line for %s", ROUTEA_CONF, job_id);
        for (int i = 0; i < 6; i++)
            if (field[i][0] == '\0')
                die_rc(1, "config %s: empty field in line for %s", ROUTEA_CONF, field[0]);

        if (strcmp(field[0], job_id) != 0) continue;

        /* --- re-validate every value (never trust the file blindly) --- */
        if (!starts_with(field[1], JOBS_ROOT))
            die_rc(1, "config %s: job-dir %s is not under %s",
                   ROUTEA_CONF, field[1], JOBS_ROOT);
        if (strcmp(field[2], FIXED_WORKER) != 0)
            die_rc(1, "config %s: worker %s is not the fixed %s",
                   ROUTEA_CONF, field[2], FIXED_WORKER);
        if (!starts_with(field[3], field[1]))
            die_rc(1, "config %s: work-dir %s is not inside job-dir %s",
                   ROUTEA_CONF, field[3], field[1]);
        if (strcmp(field[4], FIXED_PYTHON) != 0)
            die_rc(1, "config %s: python %s is not the fixed %s",
                   ROUTEA_CONF, field[4], FIXED_PYTHON);
        if (!is_lower_hex64(field[5]))
            die_rc(1, "config %s: candidate sha256 for %s is not 64 lowercase hex",
                   ROUTEA_CONF, job_id);

        snprintf(out->job_dir, sizeof out->job_dir, "%s", field[1]);
        snprintf(out->worker, sizeof out->worker, "%s", field[2]);
        snprintf(out->work_dir, sizeof out->work_dir, "%s", field[3]);
        snprintf(out->python, sizeof out->python, "%s", field[4]);
        snprintf(out->cand_sha, sizeof out->cand_sha, "%s", field[5]);
        found = 1;
        break;
    }
    fclose(f);
    return found ? 0 : 1;
}

/* Read CapEff from /proc/self/status. Returns 0 when unreadable. */
static unsigned long long read_cap_eff(void) {
    FILE *f = fopen("/proc/self/status", "r");
    if (!f) return 0ULL;
    char line[256];
    unsigned long long v = 0ULL;
    while (fgets(line, sizeof line, f)) {
        if (strncmp(line, "CapEff:", 7) == 0) {
            if (sscanf(line + 7, "%llx", &v) != 1) v = 0ULL;
            break;
        }
    }
    fclose(f);
    return v;
}

/*
 * Format the isolation attestation from the CURRENT process state.
 *
 * Every field is measured, not assumed: uid/gid from getuid/getgid, CapEff from
 * /proc/self/status, NoNewPrivs from prctl, netns from /proc/self/ns/net, and
 * the default route from /proc/net/route.
 *
 * Callers decide where the bytes go. The routea mode pipes them to the root
 * supervisor because the job directory is not writable by uid 1003 (measured
 * 2026-11-05: /var/lib/binrepair is 0700, so the sandbox cannot create a file
 * there). Measuring here and writing there keeps the evidence truthful: the
 * values come from inside the sandbox, the file is root-owned.
 */
static int format_attestation(char *out, size_t n) {
    char netns[128] = "";
    ssize_t k = readlink("/proc/self/ns/net", netns, sizeof netns - 1);
    if (k > 0) netns[k] = '\0';

    /* A default route exists iff a route line has destination 00000000. */
    char route[128] = "";
    FILE *rf = fopen("/proc/net/route", "r");
    if (rf) {
        char rline[512];
        int first = 1;
        while (fgets(rline, sizeof rline, rf)) {
            if (first) { first = 0; continue; } /* header */
            char iface[64], dest[32];
            if (sscanf(rline, "%63s %31s", iface, dest) == 2
                && strcmp(dest, "00000000") == 0) {
                snprintf(route, sizeof route, "default via %s", iface);
                break;
            }
        }
        fclose(rf);
    }

    unsigned long long cap = read_cap_eff();
    int nnp = prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0);
    if (nnp < 0) nnp = 0;

    char capbuf[32];
    if (cap == 0ULL) snprintf(capbuf, sizeof capbuf, "0");
    else snprintf(capbuf, sizeof capbuf, "%llx", cap);

    int r = snprintf(out, n,
                     "{\"uid\":%ld,\"gid\":%ld,\"cap_eff\":\"%s\","
                     "\"no_new_privs\":%d,\"netns\":\"%s\","
                     "\"default_route\":\"%s\",\"rlimit_cpu\":300}",
                     (long)getuid(), (long)getgid(), capbuf, nnp, netns, route);
    return (r > 0 && (size_t)r < n) ? 0 : -1;
}

/*
 * Write the attestation next to the work directory (probe mode).
 *
 * Used when the caller-supplied work-dir is writable by the dropped uid, which
 * is how the conformance runner sets it up. A failure is silent on purpose: a
 * missing attestation must read as `inconclusive` downstream, never as a pass.
 */
static void write_attestation(const char *dir) {
    char path[PATH_MAX];
    if (snprintf(path, sizeof path, "%s/attestation.json", dir) >= (int)sizeof path)
        return;
    char body[512];
    if (format_attestation(body, sizeof body) != 0) return;
    FILE *out = fopen(path, "w");
    if (!out) return;
    fprintf(out, "%s\n", body);
    fclose(out);
}

/* ISO-8601 UTC timestamp, second resolution. Either output may be NULL when the
 * caller only needs one form (avoids a set-but-unused variable under -Werror). */
static void utc_now(char *out, char *compact) {
    time_t t = time(NULL);
    struct tm tmv;
    gmtime_r(&t, &tmv);
    if (out) strftime(out, 32, "%Y-%m-%dT%H:%M:%SZ", &tmv);
    if (compact) strftime(compact, 32, "%Y%m%dT%H%M%SZ", &tmv);
}

/*
 * Write the wrapper's own evidence record (root-owned, before returning).
 *
 * Two identities are recorded, deliberately separated:
 *   "supervisor"         — this process, which stays root to write the file;
 *   "sandbox_attestation"— measured by the child from inside the sandbox.
 * Recording only the supervisor's uid would read as "the worker ran as root",
 * which is false; recording only the child's would hide who wrote the file.
 */
static void write_routea_evidence(const char *job_id, const struct routea_job *job,
                                  int argc, char **argv, const char *worker_sha,
                                  const char *config_sha, const char *started,
                                  const char *finished, int exit_code,
                                  const char *sandbox_attestation) {
    char compact[32];
    utc_now(NULL, compact);

    char dir[PATH_MAX];
    if (snprintf(dir, sizeof dir, "%s/%s-%s", EVIDENCE_ROOT, compact, job_id)
        >= (int)sizeof dir)
        return;
    if (mkdir(dir, 0700) != 0 && errno != EEXIST) {
        /* The evidence root may not exist yet on a fresh guest. Create it once
         * and retry; if it still fails, the run continues without evidence and
         * the absence must be treated as a missing artefact downstream. */
        if (errno == ENOENT) {
            mkdir(EVIDENCE_ROOT, 0700);
            if (mkdir(dir, 0700) != 0) return;
        } else {
            return;
        }
    }

    char path[PATH_MAX];
    if (snprintf(path, sizeof path, "%s/jobwrap-routea.json", dir) >= (int)sizeof path)
        return;

    FILE *f = fopen(path, "w");
    if (!f) return;

    char netns[128] = "";
    ssize_t n = readlink("/proc/self/ns/net", netns, sizeof netns - 1);
    if (n > 0) netns[n] = '\0';

    fprintf(f, "{\n  \"job_id\": \"%s\",\n", job_id);
    fprintf(f, "  \"argv\": [");
    for (int i = 0; i < argc; i++)
        fprintf(f, "%s\"%s\"", i ? ", " : "", argv[i]);
    fprintf(f, "],\n");
    fprintf(f, "  \"supervisor\": {\"uid\": %ld, \"gid\": %ld, \"netns\": \"%s\"},\n",
            (long)getuid(), (long)getgid(), netns);
    fprintf(f, "  \"sandbox_attestation\": %s,\n",
            (sandbox_attestation && sandbox_attestation[0]) ? sandbox_attestation : "null");
    fprintf(f, "  \"candidate_sha256\": \"%s\",\n", job->cand_sha);
    fprintf(f, "  \"worker_sha256\": \"%s\",\n", worker_sha);
    fprintf(f, "  \"config_sha256\": \"%s\",\n", config_sha);
    fprintf(f, "  \"exit_code\": %d,\n", exit_code);
    fprintf(f, "  \"started_at\": \"%s\",\n  \"finished_at\": \"%s\"\n}\n",
            started, finished);
    fclose(f);
}

/*
 * routea <job-id>
 *
 * Runs the Route A worker under the same isolation as the probe modes. The
 * supervisor (root) forks, the child isolates and execs, the supervisor waits
 * and then writes the evidence record with the real exit code.
 */
static void run_routea(const char *job_id, int argc, char **argv) {
    /* Order matters for the documented exit codes: a malformed id is a bad
     * argument (2) before any privilege or config check can turn it into 1. */
    if (!valid_job_id(job_id))
        die_rc(RC_BAD_ARG, "bad job id %s (want [A-Za-z0-9._-]{1,64})", job_id);

    if (geteuid() != 0)
        die("must run as root (euid=%ld); jobwrap-gate5 refuses non-root",
            (long)geteuid());

    struct routea_job job;
    memset(&job, 0, sizeof job);
    if (lookup_routea_job(job_id, &job) != 0)
        die_rc(RC_UNKNOWN_JOB, "unknown job: %s", job_id);

    /* Candidate must exist and match the configured hash. */
    char cand[PATH_MAX];
    if (snprintf(cand, sizeof cand, "%s/route_a/candidate.elf", job.work_dir)
        >= (int)sizeof cand)
        die("work-dir too long");
    char actual[65];
    if (sha256_hex_of_file(cand, actual) != 0)
        die_rc(RC_HASH_MISMATCH, "candidate unreadable: %s: %s", cand, strerror(errno));
    if (strcmp(actual, job.cand_sha) != 0)
        die_rc(RC_HASH_MISMATCH, "candidate hash mismatch: got %s, expected %s",
               actual, job.cand_sha);

    /* Worker blob must be readable and hashable; the hash goes into evidence. */
    char worker_sha[65];
    if (sha256_hex_of_file(job.worker, worker_sha) != 0)
        die("cannot hash worker %s: %s", job.worker, strerror(errno));
    char config_sha[65];
    if (sha256_hex_of_file(ROUTEA_CONF, config_sha) != 0)
        die("cannot hash config: %s", strerror(errno));

    char started[32];
    utc_now(started, NULL);

    /* Pipe for the child's measured attestation. The job directory is not
     * writable by uid 1003, so the child measures and the root supervisor
     * writes; the values still come from inside the sandbox. */
    int apipe[2];
    if (pipe(apipe) != 0) die("pipe: %s", strerror(errno));

    pid_t pid = fork();
    if (pid < 0) die("fork: %s", strerror(errno));

    if (pid == 0) {
        /* --- child: chdir, isolate, attest, exec ---
         *
         * The chdir happens BEFORE isolation on purpose: the seccomp allow-list
         * is deliberately tight and does not include chdir, so doing it after
         * the filter is installed returns EPERM (measured 2026-11-05).
         * Resolving the working directory as root first also means the worker
         * never needs to walk a path after privileges are dropped. */
        close(apipe[0]);

        if (chdir(job.work_dir) != 0)
            die("chdir(%s): %s", job.work_dir, strerror(errno));

        enter_isolation();

        char body[512];
        if (format_attestation(body, sizeof body) == 0) {
            ssize_t w = write(apipe[1], body, strlen(body));
            (void)w; /* a short write just means absent evidence downstream */
        }
        close(apipe[1]);

        /* Fixed argv: absolute python + absolute worker + fixed arguments.
         * The candidate is read from <work-dir>/route_a/ (the path whose hash
         * was just verified) and written to a separate out-dir so the worker's
         * copy is not a self-copy. */
        char *child_argv[] = {
            (char *)FIXED_PYTHON,
            job.worker,
            "--job-dir", job.job_dir,
            "--original", "original.elf",
            "--contract", "contract.json",
            "--tests-dir", "tests",
            "--out", "route_a-run",
            "--candidate", "route_a/candidate.elf",
            "--expected-candidate", job.cand_sha,
            NULL,
        };
        execv(FIXED_PYTHON, child_argv);
        die("execv(%s): %s", FIXED_PYTHON, strerror(errno));
    }

    /* --- supervisor: collect the attestation, wait, record --- */
    close(apipe[1]);

    char attest[512];
    size_t got = 0;
    ssize_t nread;
    while (got < sizeof attest - 1
           && (nread = read(apipe[0], attest + got, sizeof attest - 1 - got)) > 0)
        got += (size_t)nread;
    attest[got] = '\0';
    close(apipe[0]);

    int status = 0;
    if (waitpid(pid, &status, 0) < 0) die("waitpid: %s", strerror(errno));

    int exit_code = 1;
    if (WIFEXITED(status)) exit_code = WEXITSTATUS(status);
    else if (WIFSIGNALED(status)) exit_code = 128 + WTERMSIG(status);

    /* Persist the sandbox's own attestation, root-owned, next to the work dir. */
    if (got > 0) {
        char apath[PATH_MAX];
        if (snprintf(apath, sizeof apath, "%s/attestation.json", job.work_dir)
            < (int)sizeof apath) {
            FILE *af = fopen(apath, "w");
            if (af) {
                fprintf(af, "%s\n", attest);
                fclose(af);
            }
        }
    }

    char finished[32];
    utc_now(finished, NULL);
    write_routea_evidence(job_id, &job, argc, argv, worker_sha, config_sha,
                          started, finished, exit_code, attest);

    /* A worker failure is never a pass: propagate the child's code verbatim. */
    _exit(exit_code);
}

/* ------------------------------------------------------------------ */
/* main                                                               */
/* ------------------------------------------------------------------ */

static void usage(void) {
    fputs("usage: jobwrap-gate5 probe (m4-gate5|m4-gate5b) -- <repo-root> <work-dir>\n"
          "       jobwrap-gate5 routea <job-id>\n", stderr);
    _exit(2);
}

int main(int argc, char **argv) {
    if (argc < 2) usage();

    /* --- routea: exactly one argument, the job id --- */
    if (strcmp(argv[1], "routea") == 0) {
        if (argc != 3) usage();          /* bad argument -> 2 */
        run_routea(argv[2], argc, argv); /* does not return */
        return 127;
    }

    /* --- probe: exactly 6 tokens after program name --- */
    if (strcmp(argv[1], "probe") != 0) usage();
    if (argc != 6) usage();
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

    /* Attest what isolation actually produced, from inside it. Best-effort:
     * a missing file reads as `inconclusive` downstream, never as a pass. */
    write_attestation(work_dir);

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
