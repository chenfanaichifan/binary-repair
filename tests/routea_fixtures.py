"""Deterministic Route A/B evidence fixtures for the P0 trust-boundary tests.

These builders create *synthetic* bundles for tests only. They never execute a
binary: the candidate bytes may be the frozen fixture bytes or a byte-edited
copy used to trigger a host-recomputed check. The guest produced the real
evidence in the P1 window; here we exercise the host validator deterministically.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput"
ORIGINAL_ELF = FIXTURE / "original.elf"
CONTRACT = json.loads((FIXTURE / "contract.json").read_text(encoding="utf-8"))
VALID_JSON = (FIXTURE / "tests" / "valid.json").read_bytes()
TARGET_ENTRY = CONTRACT["target_entry"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def change_entry(candidate: bytes, delta: int = 1) -> bytes:
    """Return a copy with e_entry changed, so V2 entry_unchanged must fail."""

    patched = bytearray(candidate)
    entry = int.from_bytes(patched[24:32], "little")
    patched[24:32] = (entry + delta).to_bytes(8, "little")
    return bytes(patched)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_json(path: Path, payload: object) -> None:
    _write(path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _canonical_hash(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_bytes(canonical.encode("utf-8"))


def _contract_text() -> str:
    from app.domain.contracts import canonical_contract_json

    return canonical_contract_json(CONTRACT)


def _manifest_set_sha256() -> str:
    valid = json.loads(VALID_JSON.decode("utf-8"))
    payload = {
        "schema_version": 1,
        "case_id": valid["case_id"],
        "original_sha256": valid["original_sha256"],
        "manifests": [{"name": "valid.json", "sha256": sha256_bytes(VALID_JSON)}],
    }
    return _canonical_hash(payload)


def v4_marker(
    *,
    candidate_sha256: str,
    original_sha256: str,
    contract_sha256: str,
    verified_by: str | None = "m4",
) -> dict:
    """A complete typed V4 marker (schema from app.domain.v4)."""

    return {
        "schema_version": 1,
        "gate": "V4",
        "kind": "symbolic",
        "scope": "model",
        "state": "passed",
        "ran": True,
        "candidate_sha256": candidate_sha256,
        "original_sha256": original_sha256,
        "tool_versions": {"angr": "10.0.4.post1", "z3": "5.1.0"},
        "preconditions": ["synthetic fixture: candidate bytes are the test subject"],
        "property_kind": "pointer-flow",
        "memory_predicates": ["no pointer passed to free() is later read"],
        "forbidden_ranges": [{"start": 0, "end": 64, "reason": "synthetic range"}],
        "hooks": ["malloc", "memset", "free", "printLine", "exit"],
        "exploration_accounting": {
            "initial": 2, "deadended": 2, "errored": 0, "unconstrained": 0,
            "deferred": 0, "active": 0, "pruned": 0,
            "complete": True, "unexplored": [],
        },
        "solver_accounting": {
            "engine": "z3", "version": "5.1.0", "queries": 2,
            "sat": 1, "unsat": 1, "unknown": 0, "eval": 0,
            "timeouts": 0, "steps": 20, "max_steps": 80, "complete": True,
        },
        "calibration": {
            "suite": "synthetic", "cases": 2, "passed": 1, "failed": 1,
            "known_good": True, "known_bad": True, "known_bad_rejected": True,
            "complete": True,
        },
        "replay": {
            "command": "synthetic replay",
            "runs": 2,
            "identical": True,
            "evidence_sha256": original_sha256,
            "verified_by": verified_by,
        },
        "claimed_scope": "model",
        "not_claimed": ["one binary-level proof is not claimed"],
        "source": {"contract_sha256": contract_sha256, "target_entry": TARGET_ENTRY},
    }


def v5_replay(
    *,
    candidate_sha256: str,
    original_sha256: str,
    independent_replay: bool = True,
    sha256: list[str] | None = None,
) -> dict:
    values = sha256 if sha256 is not None else [candidate_sha256, candidate_sha256]
    return {
        "schema_version": 1,
        "gate": "V5",
        "kind": "reproducibility",
        "state": "measured",
        "independent_replay": independent_replay,
        "candidate_sha256": candidate_sha256,
        "original_sha256": original_sha256,
        "patch_tool_sha256": "a" * 64,
        "runs": 2,
        "sha256": values,
        "byte_identical": True,
        "matches_candidate": True,
        "replayed_by": "fresh-context-agent-test",
        "method": "two independent patch replays",
    }


def build_route_a_bundle(
    bundle: Path,
    *,
    candidate_bytes: bytes | None = None,
    original_bytes: bytes | None = None,
    audit_pass: bool = True,
    v3_ok: bool = True,
    include: set[str] | None = None,
    claims: dict[str, str] | None = None,
    v4_verified_by: str | None = "m4",
    v5_independent_replay: bool = True,
    v5_sha256: list[str] | None = None,
) -> dict[str, str]:
    """Create a canonical Route A bundle.

    Every present gate is internally consistent; callers assert the host's
    recomputation. ``include`` removes gates to exercise missing-evidence paths.
    """

    include = include if include is not None else {"V0", "V1", "V2", "V3", "V4", "V5"}
    original = original_bytes or ORIGINAL_ELF.read_bytes()
    candidate = candidate_bytes or original
    original_sha = sha256_bytes(original)
    candidate_sha = sha256_bytes(candidate)
    from app.domain.contracts import contract_sha256

    contract_sha = contract_sha256(CONTRACT)

    _write(bundle / "route_a" / "candidate.elf", candidate)
    _write(bundle / "original.elf", original)
    _write(bundle / "contract.json", _contract_text().encode("utf-8"))
    _write(bundle / "tests" / "valid.json", VALID_JSON)

    status = {
        "schema_version": 1,
        "route": "A",
        "job_id": "synthetic-p0",
        "phase": "finished",
        "original_sha256": original_sha,
        "contract_sha256": contract_sha,
        "manifest_set_sha256": _manifest_set_sha256(),
        "candidate": {
            "relative_path": "route_a/candidate.elf",
            "sha256": candidate_sha,
            "size_bytes": len(candidate),
        },
        "artifacts": [],
        "evidence": [],
        "tool_versions": {"python": "3.12.3"},
        "manual_interventions": [],
        "warnings": [],
    }
    if "V0" in include:
        _write_json(bundle / "route_a" / "status.json", status)

    if "V1" in include:
        _write_json(bundle / "route_a" / "audit.json", {"pass": audit_pass})
        _write_json(
            bundle / "route_a" / "edit-manifest.json",
            {"route": "route_a", "original_sha256": original_sha,
             "candidate_sha256": candidate_sha},
        )
        _write(bundle / "route_a" / "readelf-audit.txt",
               (f"ELF header of {candidate_sha}\n" + "program headers\n").encode("utf-8"))
        _write_json(bundle / "evidence" / "v1" / "lief.json", {"candidate": {"hash": candidate_sha}})

    if "V2" in include:
        # A claim file is present on purpose: the host must ignore it and
        # recompute the five checks itself.
        _write_json(
            bundle / "evidence" / "v2" / "interface.json",
            {"status": "pass", "details": {"claim": "producer said pass"}, "missing": []},
        )

    if "V3" in include:
        case = {
            "id": "valid-no-input",
            "ok": v3_ok,
            "exit_code": 0 if v3_ok else 1,
            "stdout_bytes": 100,
            "stdout_sha256": "0" * 64,
            "stderr_bytes": 0,
            "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }
        _write_json(
            bundle / "evidence" / "v3" / "manifest-repaired.json",
            {
                "schema_version": 1,
                "route": "route_a",
                "input_mode": "none",
                "candidate_sha256": candidate_sha,
                "candidate_size": len(candidate),
                "repaired_pass": v3_ok,
                "passed": 1 if v3_ok else 0,
                "total": 1,
                "cases": [case],
            },
        )

    if "V4" in include:
        _write_json(
            bundle / "v4-symbolic.json",
            v4_marker(
                candidate_sha256=candidate_sha,
                original_sha256=original_sha,
                contract_sha256=contract_sha,
                verified_by=v4_verified_by,
            ),
        )

    if "V5" in include:
        _write_json(
            bundle / "evidence" / "v5" / "replay.json",
            v5_replay(
                candidate_sha256=candidate_sha,
                original_sha256=original_sha,
                independent_replay=v5_independent_replay,
                sha256=v5_sha256,
            ),
        )

    if claims is not None:
        _write_json(
            bundle / "bundle.json",
            {
                "schema_version": 1,
                "candidate_sha256": candidate_sha,
                "route": "route_a",
                "gates": {gate: {"status": claims.get(gate, "passed")} for gate in
                          ("V0", "V1", "V2", "V3", "V4", "V5")},
                "identity": {"candidate_sha256": candidate_sha, "original_sha256": original_sha},
            },
        )

    return {
        "candidate_sha256": candidate_sha,
        "original_sha256": original_sha,
        "contract_sha256": contract_sha,
    }


def build_route_b_bundle(
    bundle: Path,
    *,
    candidate_bytes: bytes | None = None,
    original_bytes: bytes | None = None,
    audit_pass: bool = True,
) -> dict[str, str]:
    """Create a legitimate Route B static bundle for combination tests."""

    original = original_bytes or ORIGINAL_ELF.read_bytes()
    candidate = candidate_bytes or original
    original_sha = sha256_bytes(original)
    candidate_sha = sha256_bytes(candidate)
    _write(bundle / "candidate.elf", candidate)
    # Route B's adapter runs the interface check against bundle/original.elf.
    _write(bundle / "original.elf", original)
    _write_json(
        bundle / "edit-manifest.json",
        {"route": "route_b", "original_sha256": original_sha,
         "candidate_sha256": candidate_sha, "function": TARGET_ENTRY},
    )
    _write_json(bundle / "audit.json", {"pass": audit_pass})
    _write_json(
        bundle / "manifest-repaired.json",
        {"repaired_pass": True, "passed": 1, "total": 1, "input_mode": "none", "cases": []},
    )
    _write_json(bundle / "reproducibility.json", {"state": "measured", "pass": True})
    _write_json(
        bundle / "v2-interface.json",
        {"target_symbol": TARGET_ENTRY, "status": "pass"},
    )
    _write_json(
        bundle / "v4-symbolic.json",
        v4_marker(
            candidate_sha256=candidate_sha,
            original_sha256=original_sha,
            contract_sha256=__import__("app.domain.contracts", fromlist=["contract_sha256"]).contract_sha256(CONTRACT),
        ),
    )
    return {
        "candidate_sha256": candidate_sha,
        "original_sha256": original_sha,
    }
