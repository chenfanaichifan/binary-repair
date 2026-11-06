import hashlib
import json
import os
import tempfile
from pathlib import Path

os.environ["BINARYREPAIR_DATA_DIR"] = str(Path(tempfile.mkdtemp()) / "var")

from fastapi.testclient import TestClient  # noqa: E402

from app.controller_api import app  # noqa: E402
from app.db.connection import connect  # noqa: E402
from tests.test_evidence_endpoint import (  # noqa: E402
    MIXED_RESULTS,
    _route_attempt,
    _seed_finished_run,
)

client = TestClient(app, base_url="http://127.0.0.1")
job_id, run = _seed_finished_run(client, MIXED_RESULTS, key="m4-gate-summary")
attempt = _route_attempt(run, "route_b")
data_dir = Path(os.environ["BINARYREPAIR_DATA_DIR"])

relative = f"jobs/{job_id}/evidence/{attempt['id']}/manifest-repaired.json"
target = data_dir / relative
target.parent.mkdir(parents=True, exist_ok=True)
manifest = {
    "cases": [
        {"id": "valid-no-input", "kind": "valid", "ok": True},
    ]
}
raw = json.dumps(manifest).encode("utf-8")
target.write_bytes(raw)

connection = connect(data_dir)
try:
    with connection:
        connection.execute(
            "INSERT INTO artifacts (id, job_id, attempt_id, relative_path, sha256, "
            "size_bytes, media_type, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'application/json', 'v3_manifest', "
            "'2026-11-06T00:00:00+00:00')",
            (
                "art-v3-probe",
                job_id,
                attempt["id"],
                relative,
                hashlib.sha256(raw).hexdigest(),
                len(raw),
            ),
        )
        connection.execute(
            "UPDATE obligations SET result = 'passed', evidence_artifact_id = ?, "
            "detail = 'input_mode=none valid 1/1 invalid not_applicable' "
            "WHERE attempt_id = ? AND kind = 'behaviour'",
            ("art-v3-probe", attempt["id"]),
        )
finally:
    connection.close()

response = client.get(f"/api/attempts/{attempt['id']}/evidence")
print("status:", response.status_code)
payload = response.json()
print("top-level gates type:", type(payload.get("gates")).__name__)
print(
    "gate sequence:",
    [row["gate"] for row in payload.get("gates", [])],
)
print("V3 row:")
print(json.dumps(next(row for row in payload["gates"] if row["gate"] == "V3"), indent=2))
print("v3 summary:")
print(json.dumps(payload["v3"], indent=2))
print(
    "criteria:",
    {
        "gates_is_array": isinstance(payload.get("gates"), list),
        "v3_row_gate_is_V3": any(
            row.get("gate") == "V3" for row in payload.get("gates", [])
        ),
        "invalid_total_zero": payload["v3"]["invalid"]["total"] == 0,
        "invalid_passed_zero": payload["v3"]["invalid"]["passed"] == 0,
        "invalid_applicable_false": payload["v3"]["invalid_applicable"] is False,
    },
)
