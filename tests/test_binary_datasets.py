"""Dataset adapters: pair inventory, metadata-only fallback, no execution."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import SESSION_TOKEN, app
from app.services.binary_datasets import inventory_bin_pool, inventory_cvebinarysheet

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200


def _elf(path: Path, body: bytes = b"hello") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x7fELF" + body)


def test_binpool_pairs_vulnerable_and_patch(tmp_path):
    _elf(tmp_path / "CVE-2020-0001" / "vulnerable" / "opt0" / "bins" / "libx" / "a")
    _elf(tmp_path / "CVE-2020-0001" / "patch" / "opt0" / "bins" / "libx" / "a")
    _elf(tmp_path / "CVE-2020-0001" / "vulnerable" / "opt3" / "bins" / "libx" / "a")
    payload = inventory_bin_pool(tmp_path)
    assert payload["available"] is True
    assert payload["counts"]["binaries"] == 3
    assert payload["counts"]["cves"] == 1
    assert payload["counts"]["paired"] == 1
    assert payload["counts"]["optimizations"] == ["opt0", "opt3"]


def test_cvebinarysheet_metadata_only(tmp_path):
    (tmp_path / "cve-map").mkdir()
    (tmp_path / "cve-map" / "CVE-2021-0001.json").write_text(
        '{"vendor/lib": [{"cve_name":"CVE-2021-0001","function_names":["f"],'
        '"affected_version":["1.0"],"patch_url":"https://example.invalid/p"}]}',
        encoding="utf-8",
    )
    payload = inventory_cvebinarysheet(tmp_path)
    assert payload["available"] is True
    assert payload["counts"]["cves"] == 1
    assert payload["metadata"][0]["cve"] == "CVE-2021-0001"
    assert "Metadata only" in payload["limitations"][0]


def test_missing_roots_are_unknown_not_zero(tmp_path):
    payload = inventory_bin_pool(tmp_path / "nope")
    assert payload["available"] is False
    assert payload["reason"] == "root_not_found"
    assert payload["records"] == []


def test_status_endpoint_is_read_only():
    response = client.get("/api/datasets")
    assert response.status_code == 200
    payload = response.json()
    assert "datasets" in payload
    assert payload["datasets"]["binpool"] in (
        {"available": False, "reason": "not_configured", "hint": "set BINARYREPAIR_BINPOOL_ROOT"},
        payload["datasets"]["binpool"],
    )
