"""Static assertions over jobwrap_gate5.c (routea mode).

These are source-level checks, not a compile and not a run. They exist because
the host must never compile a binary (AGENTS.md §3): the only thing the host can
honestly verify about the C wrapper is that the required properties are present
in the text. Compilation and execution happen in the guest.

What each assertion buys: a regression in the security shape (a stray `system()`,
a missing exit code, an isolation step skipped) fails here before anyone builds.
What it does NOT buy: any claim that the binary behaves correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "route-a" / "jobwrap-gate5" / "jobwrap_gate5.c"
SAMPLE = SOURCE.parent / "routea.conf.sample"


@pytest.fixture(scope="module")
def src() -> str:
    return SOURCE.read_text(encoding="utf-8")


# ---- no shell, no arbitrary exec -----------------------------------------


@pytest.mark.parametrize("forbidden", ["system(", "popen(", "execvp(", "execlp(", "pclose("])
def test_no_shell_escapes(src, forbidden):
    assert forbidden not in src, f"{forbidden} would allow a shell/PATH escape"


def test_execv_uses_absolute_paths_only(src):
    """Every execv target is a compile-time absolute path, never argv."""
    for line in src.splitlines():
        if "execv(" in line and not line.strip().startswith("*"):
            assert "FIXED_PYTHON" in line or "PYTHON3_PATH" in line or "execv(FIXED" in line


# ---- documented exit codes ------------------------------------------------


@pytest.mark.parametrize(
    "macro,value", [("RC_BAD_ARG", 2), ("RC_UNKNOWN_JOB", 3), ("RC_HASH_MISMATCH", 4)]
)
def test_exit_codes_defined(src, macro, value):
    assert f"#define {macro} {value}" in src
    assert f"{macro}" in src.split(f"#define {macro} {value}", 1)[1], "defined but unused"


# ---- fixed paths from the spec -------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        "/usr/local/etc/binrepair/routea.conf",
        "/var/lib/binrepair/jobs/",
        "/opt/binrepair/workers/route_a/worker.py",
        "/opt/angr-venv/bin/python",
        "/var/lib/binrepair/evidence",
    ],
)
def test_spec_paths_present(src, token):
    assert token in src


# ---- validation order and coverage ---------------------------------------


def test_job_id_regex_rejects_separators(src):
    """The id validator must reject anything outside [A-Za-z0-9._-]."""
    block = src.split("static int valid_job_id", 1)[1].split("static int is_lower_hex64", 1)[0]
    assert "'/'" not in block, "a slash must not be accepted in a job id"
    for allowed in ("'A'", "'a'", "'0'", "'.'", "'_'", "'-'"):
        assert allowed in block


def test_config_permissions_checked(src):
    block = src.split("static int lookup_routea_job", 1)[1].split("static unsigned long long", 1)[0]
    assert "st_uid != 0" in block, "config must be root-owned"
    assert "S_IWGRP" in block and "S_IWOTH" in block, "config must not be group/other-writable"
    assert "S_ISREG" in block


def test_field_count_is_checked_before_splitting(src):
    """A 7-field line must not silently pass as 6 fields."""
    block = src.split("static int lookup_routea_job", 1)[1].split("static unsigned long long", 1)[0]
    assert "tabs != 5" in block
    assert block.index("tabs != 5") < block.index("while (nf < 6)")


def test_work_dir_must_be_inside_job_dir(src):
    assert "is not inside job-dir" in src


def test_candidate_hash_mismatch_uses_rc4(src):
    assert "RC_HASH_MISMATCH" in src
    assert "candidate hash mismatch" in src


# ---- isolation reused, not re-implemented --------------------------------


def test_routea_reuses_enter_isolation(src):
    block = src.split("static void run_routea", 1)[1]
    assert "enter_isolation();" in block


def test_worker_exit_code_propagated(src):
    block = src.split("static void run_routea", 1)[1]
    assert "waitpid" in block
    assert "WEXITSTATUS" in block
    assert "_exit(exit_code)" in block


def test_child_argv_is_fixed(src):
    """The worker argv is a static list; nothing is taken from the caller."""
    block = src.split("static void run_routea", 1)[1]
    assert '"--expected-candidate"' in block
    assert "job.cand_sha" in block


def test_child_chdirs_to_work_dir_before_exec(src):
    """The worker takes relative paths, so cwd must be the work-dir."""
    block = src.split("static void run_routea", 1)[1]
    assert "chdir(job.work_dir)" in block


def test_chdir_happens_before_the_seccomp_filter(src):
    """The seccomp allow-list excludes chdir, so chdir must precede isolation.

    Doing it after enter_isolation() returns EPERM (measured in the guest on
    2026-11-05); this assertion keeps that ordering from regressing.
    """
    block = src.split("static void run_routea", 1)[1]
    assert block.index("chdir(job.work_dir)") < block.index("enter_isolation();")


def test_candidate_and_out_do_not_collide(src):
    """Reading route_a/candidate.elf while writing route_a would be a self-copy."""
    block = src.split("static void run_routea", 1)[1]
    assert '"route_a/candidate.elf"' in block
    out = block.split('"--out",', 1)[1].split(",", 1)[0].strip().strip('"')
    assert out and out != "route_a", f"--out {out!r} would collide with the input dir"


# ---- attestation ---------------------------------------------------------


@pytest.mark.parametrize("mode_marker", ["enter_isolation();\n\n    /* Attest", ])
def test_probe_mode_attests(src, mode_marker):
    assert "write_attestation(work_dir);" in src


def test_routea_mode_attests_from_inside_the_sandbox(src):
    """routea measures in the child and pipes it out for the root to write.

    The job dir is not writable by uid 1003 (/var/lib/binrepair is 0700), so the
    file must be written by the supervisor; the values still come from inside.
    """
    block = src.split("static void run_routea", 1)[1]
    assert "format_attestation(body, sizeof body)" in block
    assert "write(apipe[1], body, strlen(body))" in block
    # the measurement must happen after isolation, not before
    assert block.index("enter_isolation();") < block.index("format_attestation(body")


def test_attestation_measures_not_assumes(src):
    """Every attested value is read from the kernel, not hardcoded."""
    fmt = src.split("static int format_attestation", 1)[1].split(
        "/*\n * Write the attestation next to the work directory", 1)[0]
    cap = src.split("static unsigned long long read_cap_eff", 1)[1].split(
        "/*\n * Format the isolation attestation", 1)[0]
    assert "read_cap_eff()" in fmt, "format_attestation must call the reader"
    assert "/proc/self/status" in cap, "CapEff must be read, not assumed"
    assert "/proc/self/ns/net" in fmt, "netns must be read"
    assert "/proc/net/route" in fmt, "egress state must be read"
    assert "PR_GET_NO_NEW_PRIVS" in fmt


# ---- dispatch and usage --------------------------------------------------


def test_usage_documents_routea(src):
    block = src.split("static void usage", 1)[1]
    assert "routea <job-id>" in block


def test_main_dispatches_routea_with_exact_arity(src):
    block = src.split("int main(int argc, char **argv)", 1)[1]
    assert 'strcmp(argv[1], "routea")' in block
    assert "argc != 3" in block


def test_probe_still_requires_six_tokens(src):
    block = src.split("int main(int argc, char **argv)", 1)[1]
    assert "argc != 6" in block


# ---- sample config -------------------------------------------------------


def test_sample_has_six_tab_separated_fields():
    line = next(l for l in SAMPLE.read_text(encoding="utf-8").splitlines()
                if l and not l.startswith("#"))
    fields = line.split("\t")
    assert len(fields) == 6, f"sample line has {len(fields)} fields"
    assert line.count("\t") == 5
    assert all(f.strip() for f in fields)


def test_sample_paths_match_the_spec_constants():
    line = next(l for l in SAMPLE.read_text(encoding="utf-8").splitlines()
                if l and not l.startswith("#"))
    fields = line.split("\t")
    assert fields[1].startswith("/var/lib/binrepair/jobs/")
    assert fields[2] == "/opt/binrepair/workers/route_a/worker.py"
    assert fields[3].startswith(fields[1])
    assert fields[4] == "/opt/angr-venv/bin/python"
    assert len(fields[5]) == 64 and all(c in "0123456789abcdef" for c in fields[5])
