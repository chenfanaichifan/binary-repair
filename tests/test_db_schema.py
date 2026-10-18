from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from db.migrate import applied_versions, apply_migrations, connect

H = "a" * 64
NOW = "2026-10-18T00:00:00+00:00"


def add_job(conn: sqlite3.Connection, job_id: str = "job-1") -> None:
    conn.execute(
        "INSERT INTO jobs(id, original_sha256, classification, created_at, phase)"
        " VALUES (?, ?, 'public', ?, 'awaiting_review')",
        (job_id, H, NOW),
    )


def add_contract(
    conn: sqlite3.Connection,
    contract_id: str = "contract-1",
    job_id: str = "job-1",
    revision: int = 1,
    body_json: str = "{}",
    approved: bool = True,
) -> None:
    conn.execute(
        "INSERT INTO contracts(id, job_id, revision, body_json, sha256, approved_at, reviewer_label)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            contract_id,
            job_id,
            revision,
            body_json,
            H,
            NOW if approved else None,
            "reviewer" if approved else None,
        ),
    )


def add_run(
    conn: sqlite3.Connection,
    run_id: str = "run-1",
    job_id: str = "job-1",
    contract_id: str = "contract-1",
    key: str = "key-1",
) -> None:
    conn.execute(
        "INSERT INTO runs(id, job_id, contract_id, manifest_sha256, idempotency_key,"
        " phase, started_at) VALUES (?, ?, ?, ?, ?, 'queued', ?)",
        (run_id, job_id, contract_id, H, key, NOW),
    )


def add_attempt(
    conn: sqlite3.Connection,
    attempt_id: str = "attempt-1",
    run_id: str = "run-1",
    route: str = "route_b",
    sequence: int = 1,
) -> None:
    conn.execute(
        "INSERT INTO attempts(id, run_id, route, sequence, phase)"
        " VALUES (?, ?, ?, ?, 'queued')",
        (attempt_id, run_id, route, sequence),
    )


def add_artifact(conn: sqlite3.Connection, artifact_id: str = "artifact-1") -> None:
    conn.execute(
        "INSERT INTO artifacts(id, job_id, attempt_id, relative_path, sha256,"
        " size_bytes, media_type, role, created_at)"
        " VALUES (?, 'job-1', 'attempt-1', ?, ?, 10, 'application/octet-stream',"
        " 'candidate', ?)",
        (artifact_id, f"jobs/job-1/{artifact_id}.bin", H, NOW),
    )


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = connect(tmp_path / "test.db")
    apply_migrations(c)
    add_job(c)
    add_contract(c)
    add_run(c)
    add_attempt(c)
    add_artifact(c)
    c.commit()
    yield c
    c.close()


def test_migrations_are_idempotent(tmp_path: Path) -> None:
    c = connect(tmp_path / "fresh.db")
    assert apply_migrations(c) == [1]
    assert apply_migrations(c) == []
    assert applied_versions(c) == {1}
    c.close()


def test_failed_migration_rolls_back(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_bad.sql").write_text(
        "CREATE TABLE should_not_exist (id TEXT);\n"
        "INSERT INTO missing_table VALUES (1);\n",
        encoding="utf-8",
    )

    c = connect(tmp_path / "bad.db")
    with pytest.raises(sqlite3.Error):
        apply_migrations(c, migrations)

    remaining = c.execute(
        "SELECT count(*) FROM sqlite_master WHERE name = 'should_not_exist'"
    ).fetchone()[0]
    assert remaining == 0
    assert applied_versions(c) == set()
    c.close()


def test_foreign_key_is_enforced(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO attempts(id, run_id, route, sequence, phase)"
            " VALUES ('attempt-x', 'missing-run', 'B', 1, 'queued')"
        )
    conn.rollback()


def test_run_cannot_use_another_jobs_contract(conn: sqlite3.Connection) -> None:
    add_job(conn, "job-2")
    add_contract(conn, "contract-2", job_id="job-2")
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO runs(id, job_id, contract_id, manifest_sha256, idempotency_key,"
            " phase, started_at) VALUES ('run-x', 'job-1', 'contract-2', ?, 'key-x',"
            " 'queued', ?)",
            (H, NOW),
        )
    conn.rollback()


def test_idempotency_key_is_unique(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_run(conn, run_id="run-2", key="key-1")
    conn.rollback()


def test_route_and_outcome_vocabulary(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_attempt(conn, attempt_id="attempt-c", route="C", sequence=2)
    conn.rollback()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE runs SET outcome = 'ok' WHERE id = 'run-1'")
    conn.rollback()

    conn.execute("UPDATE runs SET outcome = 'success_within_scope' WHERE id = 'run-1'")
    conn.commit()


def test_attempt_is_unique_per_route_and_sequence(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_attempt(conn, attempt_id="attempt-2", route="route_b", sequence=1)
    conn.rollback()

    add_attempt(conn, attempt_id="attempt-2", route="route_b", sequence=2)
    conn.commit()


def test_pass_obligation_requires_evidence(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO obligations(id, attempt_id, kind, required, result)"
            " VALUES ('ob-1', 'attempt-1', 'security', 1, 'pass')"
        )
    conn.rollback()

    conn.execute(
        "INSERT INTO obligations(id, attempt_id, kind, required, result, evidence_artifact_id)"
        " VALUES ('ob-2', 'attempt-1', 'security', 1, 'pass', 'artifact-1')"
    )
    conn.execute(
        "INSERT INTO obligations(id, attempt_id, kind, required, result)"
        " VALUES ('ob-3', 'attempt-1', 'security', 0, 'not_run')"
    )
    conn.commit()


def test_contract_approval_is_atomic(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO contracts(id, job_id, revision, body_json, sha256, approved_at)"
            " VALUES ('contract-x', 'job-1', 2, '{}', ?, ?)",
            (H, NOW),
        )
    conn.rollback()


def test_json_columns_must_be_valid_json(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_contract(conn, "contract-json", revision=2, body_json="not json")
    conn.rollback()


def test_model_call_costs_are_non_negative_and_nullable(conn: sqlite3.Connection) -> None:
    def insert(call_id: str, cost: float | None, status: str = "accepted_for_validation") -> None:
        conn.execute(
            "INSERT INTO model_calls(id, attempt_id, request_id, model, prompt_sha256,"
            " status, estimated_cost_usd, created_at)"
            " VALUES (?, 'attempt-1', ?, 'deepseek-flash', ?, ?, ?, ?)",
            (call_id, f"req-{call_id}", H, status, cost, NOW),
        )

    insert("call-1", 0.5)
    insert("call-2", None, status="provider_timeout")
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        insert("call-3", -0.01)
    conn.rollback()

    row = conn.execute(
        "SELECT * FROM job_ai_usage WHERE job_id = 'job-1'"
    ).fetchone()
    assert row["call_count"] == 2
    assert row["unknown_cost_calls"] == 1
    assert row["known_cost_usd"] == pytest.approx(0.5)
    assert row["accepted_candidates"] == 1
