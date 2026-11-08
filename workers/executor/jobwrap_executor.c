/*
 * jobwrap_executor.c - fixed-argv executor wrapper for T6.2.
 *
 * GUEST ONLY. Build inside the disposable guest; the host must not compile it.
 * This is a NEW binary, installed as /usr/local/sbin/jobwrap-executor. It does
 * NOT replace /usr/local/sbin/jobwrap: Gate 3/4 evidence is bound to that old
 * binary (sha256 b232d60b...), and this file is not a reconstruction of it.
 *
 * Invocation (exactly this shape, no shell, no caller-supplied argv array):
 *
 *     jobwrap-executor executor <repo-root> <package> <out>
 *
 * <repo-root> must resolve to the fixed /opt/binrepair/executor-repo tree.
 * <package> and <out> must be under /var/lib/binrepair/jobs/. The package tree
 * is root-owned and not group/other-writable; the wrapper rejects symlinks and
 * writable entries before it drops privileges. <out> must not already exist;
 * the wrapper creates it as runner:runner 0750.
 *
 * Isolation, in order: root-only, no-egress netns + mount/uts ns, private /,
 * fresh /proc, seccomp denylist, NoNewPrivs=1, setgroups(0), setgid(1003),
 * setuid(1003), rlimits, cleared environment. It then writes a root-owned
 * attestation to /run/binrepair/executor/attest-<pid>.json and execs:
 *
 *     /opt/angr-venv/bin/python \
 *       /opt/binrepair/executor-repo/workers/executor/run_job.py \
 *       --package <package> --out <out> --guest-ack \
 *       --repo-root /opt/binrepair/executor-repo
 *
 * The attestation is created by root before the drop and written after the
 * drop, so its uid/cap_eff/NoNewPrivs/seccomp/netns fields are measured from
 * inside the sandbox. run_job.py refuses a non-plan run unless that file is
 * root-owned, in the fixed directory, for its own pid, and reports the expected
 * isolation. It is evidence, not a substitute for the wrapper: the wrapper is
 * what enforces the isolation.
 */

#define _GNU_SOURCE

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <limits.h>
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
#include <unistd.h>

#define TARGET_UID 1003
#define TARGET_GID 1003

#define REPO_ROOT "/opt/binrepair/executor-repo"
#define RUN_JOB REPO_ROOT "/workers/executor/run_job.py"
#define PYTHON "/opt/angr-venv/bin/python"
#define JOBS_ROOT "/var/lib/binrepair/jobs/"
#define ATTEST_DIR "/run/binrepair/executor"
#define ATTEST_PREFIX ATTEST_DIR "/attest-"
#define JOBWRAP_PATH "/usr/local/sbin/jobwrap-executor"

static const char *g_repo;
static const char *g_package;
static const char *g_out;
static char g_host_netns[128];

static void die(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    fputs("jobwrap-executor: ", stderr);
    vfprintf(stderr, fmt, ap);
    fputc('\n', stderr);
    va_end(ap);
    _exit(2);
}

static void die_errno(const char *what, const char *path) {
    die("%s %s: %s", what, path, strerror(errno));
}

/* A path is under a root prefix and has no "." or ".." component. */
static int safe_under(const char *path, const char *root) {
    size_t rn = strlen(root);
    if (strncmp(path, root, rn) != 0) return 0;
    if (path[rn] == '\0') return 0;

    char buf[PATH_MAX];
    if (snprintf(buf, sizeof buf, "%s", path) >= (int)sizeof buf) return 0;
    char *save = NULL;
    for (char *tok = strtok_r(buf, "/", &save); tok; tok = strtok_r(NULL, "/", &save)) {
        if (strcmp(tok, ".") == 0 || strcmp(tok, "..") == 0) return 0;
    }
    return 1;
}

static int valid_token(const char *s) {
    size_t n = strlen(s);
    if (n < 1 || n > 128) return 0;
    for (size_t i = 0; i < n; i++) {
        char c = s[i];
        int ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
                 || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-';
        if (!ok) return 0;
    }
    return 1;
}

static void check_owned(const char *path, int want_dir) {
    struct stat st;
    if (lstat(path, &st) != 0) die_errno("lstat", path);
    if (S_ISLNK(st.st_mode)) die("symlink not allowed: %s", path);
    if (want_dir && !S_ISDIR(st.st_mode)) die("not a directory: %s", path);
    if (!want_dir && !S_ISREG(st.st_mode)) die("not a regular file: %s", path);
    if (st.st_uid != 0) die("not root-owned (uid=%ld): %s", (long)st.st_uid, path);
    if (st.st_mode & (S_IWGRP | S_IWOTH))
        die("group/other-writable (mode=%o): %s", (unsigned)(st.st_mode & 07777), path);
}

static void check_tree(const char *path, int depth) {
    check_owned(path, 1);
    if (depth <= 0) die("tree too deep: %s", path);

    DIR *dir = opendir(path);
    if (!dir) die_errno("opendir", path);
    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL) {
        if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0) continue;
        char child[PATH_MAX];
        if (snprintf(child, sizeof child, "%s/%s", path, ent->d_name) >= (int)sizeof child)
            die("path too long under %s", path);
        if (ent->d_type == DT_DIR) {
            check_tree(child, depth - 1);
        } else if (ent->d_type == DT_LNK) {
            die("symlink not allowed: %s", child);
        } else if (ent->d_type == DT_UNKNOWN) {
            struct stat st;
            if (lstat(child, &st) != 0) die_errno("lstat", child);
            if (S_ISDIR(st.st_mode)) check_tree(child, depth - 1);
            else check_owned(child, 0);
        } else {
            check_owned(child, 0);
        }
    }
    closedir(dir);
}

static void validate_paths(const char *repo_arg, const char *package_arg, const char *out_arg,
                           char repo[PATH_MAX], char package[PATH_MAX], char out[PATH_MAX]) {
    if (repo_arg[0] != '/' || package_arg[0] != '/' || out_arg[0] != '/')
        die("repo-root, package and out must be absolute paths");

    if (realpath(repo_arg, repo) == NULL) die_errno("realpath", repo_arg);
    if (strcmp(repo, REPO_ROOT) != 0)
        die("repo-root must be exactly %s (got %s)", REPO_ROOT, repo);
    check_tree(REPO_ROOT, 6);
    check_owned(RUN_JOB, 0);

    if (realpath(package_arg, package) == NULL) die_errno("realpath", package_arg);
    if (!safe_under(package, JOBS_ROOT))
        die("package must be under %s (got %s)", JOBS_ROOT, package);
    check_tree(package, 5);

    char parent[PATH_MAX];
    if (snprintf(parent, sizeof parent, "%s", out_arg) >= (int)sizeof parent)
        die("out path too long");
    char *slash = strrchr(parent, '/');
    if (!slash || slash == parent) die("out must name a directory below %s", JOBS_ROOT);
    *slash = '\0';
    const char *base = slash + 1;
    if (!valid_token(base)) die("invalid out basename: %s", base);

    char parent_real[PATH_MAX];
    if (realpath(parent, parent_real) == NULL) die_errno("realpath", parent);
    if (!safe_under(parent_real, JOBS_ROOT))
        die("out parent must be under %s (got %s)", JOBS_ROOT, parent_real);
    check_owned(parent_real, 1);

    if (snprintf(out, PATH_MAX, "%s/%s", parent_real, base) >= PATH_MAX)
        die("out path too long");
    struct stat st;
    if (lstat(out, &st) == 0) die("out already exists: %s", out);
    if (errno != ENOENT) die_errno("lstat", out);
}

static int read_status_value(const char *key, char *out, size_t n) {
    FILE *f = fopen("/proc/self/status", "r");
    if (!f) return -1;
    char line[512];
    size_t kn = strlen(key);
    int found = -1;
    while (fgets(line, sizeof line, f)) {
        if (strncmp(line, key, kn) == 0 && line[kn] == ':') {
            char *p = line + kn + 1;
            while (*p == ' ' || *p == '\t') p++;
            size_t len = strcspn(p, "\r\n");
            if (len >= n) len = n - 1;
            memcpy(out, p, len);
            out[len] = '\0';
            found = 0;
            break;
        }
    }
    fclose(f);
    return found;
}

static int format_attestation(char *out, size_t n) {
    char netns[128] = "";
    ssize_t k = readlink("/proc/self/ns/net", netns, sizeof netns - 1);
    if (k > 0) netns[k] = '\0';

    char route[128] = "";
    FILE *rf = fopen("/proc/net/route", "r");
    if (rf) {
        char line[512];
        int first = 1;
        while (fgets(line, sizeof line, rf)) {
            if (first) { first = 0; continue; }
            char iface[64], dest[32];
            if (sscanf(line, "%63s %31s", iface, dest) == 2
                && strcmp(dest, "00000000") == 0) {
                snprintf(route, sizeof route, "default via %s", iface);
                break;
            }
        }
        fclose(rf);
    }

    char cap[64] = "0";
    char nnp_s[32] = "0";
    char sec_s[32] = "0";
    if (read_status_value("CapEff", cap, sizeof cap) != 0) snprintf(cap, sizeof cap, "0");
    if (read_status_value("NoNewPrivs", nnp_s, sizeof nnp_s) != 0) snprintf(nnp_s, sizeof nnp_s, "0");
    if (read_status_value("Seccomp", sec_s, sizeof sec_s) != 0) snprintf(sec_s, sizeof sec_s, "0");

    long nnp = strtol(nnp_s, NULL, 10);
    long sec = strtol(sec_s, NULL, 10);

    int r = snprintf(out, n,
        "{\"schema_version\":1,\"jobwrap\":\"%s\",\"pid\":%ld,"
        "\"uid\":%ld,\"euid\":%ld,\"gid\":%ld,\"egid\":%ld,"
        "\"cap_eff\":\"%s\",\"no_new_privs\":%ld,\"seccomp\":%ld,"
        "\"netns\":\"%s\",\"host_netns\":\"%s\",\"default_route\":\"%s\","
        "\"repo\":\"%s\",\"package\":\"%s\",\"out\":\"%s\"}",
        JOBWRAP_PATH, (long)getpid(),
        (long)getuid(), (long)geteuid(), (long)getgid(), (long)getegid(),
        cap, nnp, sec, netns, g_host_netns, route, g_repo, g_package, g_out);
    return (r > 0 && (size_t)r < n) ? 0 : -1;
}

static int write_all(int fd, const char *buf, size_t len) {
    while (len > 0) {
        ssize_t w = write(fd, buf, len);
        if (w < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        buf += (size_t)w;
        len -= (size_t)w;
    }
    return 0;
}

static void apply_rlimits(void) {
    struct rlimit r;
    r.rlim_cur = r.rlim_max = 300;
    if (setrlimit(RLIMIT_CPU, &r) != 0) die("setrlimit(CPU): %s", strerror(errno));
    r.rlim_cur = r.rlim_max = 8ULL * 1024 * 1024 * 1024;
    if (setrlimit(RLIMIT_AS, &r) != 0) die("setrlimit(AS): %s", strerror(errno));
    r.rlim_cur = r.rlim_max = 1ULL * 1024 * 1024 * 1024;
    if (setrlimit(RLIMIT_FSIZE, &r) != 0) die("setrlimit(FSIZE): %s", strerror(errno));
    r.rlim_cur = r.rlim_max = 128;
    if (setrlimit(RLIMIT_NPROC, &r) != 0) die("setrlimit(NPROC): %s", strerror(errno));
}

static void install_seccomp_filter(void) {
    const uint32_t deny = SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA);
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),

        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_socket, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_connect, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_bind, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_listen, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_accept, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_accept4, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_sendto, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_recvfrom, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_sendmsg, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_recvmsg, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, deny),

        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };
    struct sock_fprog prog = {
        .len = (unsigned short)(sizeof filter / sizeof filter[0]),
        .filter = filter,
    };
    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog) != 0)
        die("prctl(PR_SET_SECCOMP): %s", strerror(errno));
}

static void enter_and_attest(int att_fd, const char *att_path) {
    /* Do this while still root: after setuid(1003) we are not the file owner
     * and fchmod would fail. The fd stays writable because write permission is
     * checked at open time. */
    if (fchmod(att_fd, 0444) != 0)
        die("could not chmod attestation: %s", strerror(errno));

    if (unshare(CLONE_NEWNET | CLONE_NEWNS | CLONE_NEWUTS) != 0)
        die("unshare(NEWNET|NEWNS|NEWUTS): %s", strerror(errno));
    if (mount("none", "/", NULL, MS_REC | MS_PRIVATE, NULL) != 0)
        die("mount(/, private): %s", strerror(errno));
    if (mount("none", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL) != 0)
        die("mount(/proc): %s", strerror(errno));

    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0)
        die("prctl(PR_SET_NO_NEW_PRIVS): %s", strerror(errno));
    install_seccomp_filter();

    if (setgroups(0, NULL) != 0) die("setgroups: %s", strerror(errno));
    if (setgid(TARGET_GID) != 0) die("setgid(%d): %s", TARGET_GID, strerror(errno));
    if (setuid(TARGET_UID) != 0) die("setuid(%d): %s", TARGET_UID, strerror(errno));

    apply_rlimits();
    clearenv();
    setenv("PATH", "/usr/bin:/bin", 1);
    setenv("HOME", "/nonexistent", 1);
    setenv("LANG", "C.UTF-8", 1);
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);
    setenv("PYTHONUNBUFFERED", "1", 1);
    setenv("BINARYREPAIR_JOBWRAP", att_path, 1);

    char body[2048];
    if (format_attestation(body, sizeof body) != 0)
        die("could not format attestation");
    if (write_all(att_fd, body, strlen(body)) != 0)
        die("could not write attestation: %s", strerror(errno));
    if (close(att_fd) != 0)
        die("could not close attestation: %s", strerror(errno));
}

static void open_attestation(char path[PATH_MAX], int *fd) {
    if (mkdir("/run/binrepair", 0755) != 0 && errno != EEXIST)
        die("mkdir /run/binrepair: %s", strerror(errno));
    if (mkdir(ATTEST_DIR, 0755) != 0 && errno != EEXIST)
        die("mkdir %s: %s", ATTEST_DIR, strerror(errno));
    check_owned(ATTEST_DIR, 1);

    if (snprintf(path, PATH_MAX, "%s%d.json", ATTEST_PREFIX, (int)getpid()) >= PATH_MAX)
        die("attestation path too long");
    if (unlink(path) != 0 && errno != ENOENT)
        die("unlink stale attestation %s: %s", path, strerror(errno));
    *fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    if (*fd < 0) die("open attestation %s: %s", path, strerror(errno));
    if (fchown(*fd, 0, 0) != 0)
        die("chown attestation %s: %s", path, strerror(errno));
}

static void usage(void) {
    fputs("usage: jobwrap-executor executor <repo-root> <package> <out>\n", stderr);
    _exit(2);
}

int main(int argc, char **argv) {
    if (argc != 5) usage();
    if (strcmp(argv[1], "executor") != 0) usage();
    if (geteuid() != 0)
        die("must run as root (euid=%ld); jobwrap-executor refuses non-root",
            (long)geteuid());

    ssize_t host_ns = readlink("/proc/self/ns/net", g_host_netns, sizeof g_host_netns - 1);
    if (host_ns <= 0) die("cannot read host netns: %s", strerror(errno));
    g_host_netns[host_ns] = '\0';

    char repo[PATH_MAX], package[PATH_MAX], out[PATH_MAX];
    validate_paths(argv[2], argv[3], argv[4], repo, package, out);
    g_repo = repo;
    g_package = package;
    g_out = out;

    char att_path[PATH_MAX];
    int att_fd = -1;
    open_attestation(att_path, &att_fd);

    if (mkdir(out, 0750) != 0) die("mkdir out %s: %s", out, strerror(errno));
    if (chown(out, TARGET_UID, TARGET_GID) != 0)
        die("chown out %s: %s", out, strerror(errno));
    if (chmod(out, 0750) != 0) die("chmod out %s: %s", out, strerror(errno));

    enter_and_attest(att_fd, att_path);

    char *child_argv[] = {
        (char *)PYTHON,
        (char *)RUN_JOB,
        "--package", package,
        "--out", out,
        "--guest-ack",
        "--repo-root", repo,
        NULL,
    };
    execv(PYTHON, child_argv);
    die("execv(%s): %s", PYTHON, strerror(errno));
    return 127;
}
