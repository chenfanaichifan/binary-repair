/* Minimal CGC POV replay harness: connect pov<->challenge with two pipes.
 *
 * Usage: pov_runner <challenge> <pov> [timeout_seconds]
 *
 * Exit codes: 0 = both processes exited normally; 2 = usage/pipe error;
 * 3 = timeout (both killed); 4 = challenge died by signal; 5 = pov died by
 * signal.  The stdout line is machine-readable:
 *   cb_exit=<n> cb_signal=<n> pov_exit=<n> pov_signal=<n> timed_out=<0|1>
 */
#define _GNU_SOURCE
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static pid_t cb_pid = -1, pov_pid = -1;

static const char *qemu_path(void) {
    const char *q = getenv("POV_QEMU");
    return (q && *q) ? q : NULL;
}

static void exec_target(const char *path) {
    const char *q = qemu_path();
    if (q) {
        execl(q, q, path, (char *)NULL);
    } else {
        execl(path, path, (char *)NULL);
    }
}

static void kill_both(void) {
    if (pov_pid > 0) kill(pov_pid, SIGKILL);
    if (cb_pid > 0) kill(cb_pid, SIGKILL);
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <challenge> <pov> [timeout_seconds]\n", argv[0]);
        return 2;
    }
    int timeout = argc > 3 ? atoi(argv[3]) : 15;
    if (timeout <= 0) timeout = 15;

    int to_cb[2], from_cb[2];
    if (pipe(to_cb) != 0 || pipe(from_cb) != 0) {
        perror("pipe");
        return 2;
    }

    cb_pid = fork();
    if (cb_pid == 0) {
        dup2(to_cb[0], STDIN_FILENO);
        dup2(from_cb[1], STDOUT_FILENO);
        close(to_cb[0]); close(to_cb[1]);
        close(from_cb[0]); close(from_cb[1]);
        exec_target(argv[1]);
        perror("exec challenge");
        _exit(127);
    }
    if (cb_pid < 0) { perror("fork challenge"); return 2; }

    pov_pid = fork();
    if (pov_pid == 0) {
        dup2(from_cb[0], STDIN_FILENO);
        dup2(to_cb[1], STDOUT_FILENO);
        close(to_cb[0]); close(to_cb[1]);
        close(from_cb[0]); close(from_cb[1]);
        exec_target(argv[2]);
        perror("exec pov");
        _exit(127);
    }
    if (pov_pid < 0) { perror("fork pov"); kill(cb_pid, SIGKILL); return 2; }

    close(to_cb[0]); close(to_cb[1]);
    close(from_cb[0]); close(from_cb[1]);

    int cb_status = 0, pov_status = 0, timed_out = 0;
    int cb_done = 0, pov_done = 0;
    for (int i = 0; i < timeout * 20; i++) {
        if (!cb_done) {
            pid_t r = waitpid(cb_pid, &cb_status, WNOHANG);
            if (r == cb_pid) cb_done = 1;
        }
        if (!pov_done) {
            pid_t r = waitpid(pov_pid, &pov_status, WNOHANG);
            if (r == pov_pid) pov_done = 1;
        }
        if (cb_done && pov_done) break;
        usleep(50000);
    }
    if (!cb_done || !pov_done) {
        timed_out = 1;
        kill_both();
        if (!cb_done) waitpid(cb_pid, &cb_status, 0);
        if (!pov_done) waitpid(pov_pid, &pov_status, 0);
    }

    int cb_sig = WIFSIGNALED(cb_status) ? WTERMSIG(cb_status) : 0;
    int pov_sig = WIFSIGNALED(pov_status) ? WTERMSIG(pov_status) : 0;
    int cb_exit = WIFEXITED(cb_status) ? WEXITSTATUS(cb_status) : -1;
    int pov_exit = WIFEXITED(pov_status) ? WEXITSTATUS(pov_status) : -1;

    printf("cb_exit=%d cb_signal=%d pov_exit=%d pov_signal=%d timed_out=%d\n",
           cb_exit, cb_sig, pov_exit, pov_sig, timed_out);
    fflush(stdout);

    if (timed_out) return 3;
    if (cb_sig) return 4;
    if (pov_sig) return 5;
    return 0;
}
