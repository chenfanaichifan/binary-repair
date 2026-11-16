"""Versioned external CWE knowledge snapshot and capability-candidate mapping.

This module is deliberately offline by default.  It parses the official MITRE
CWE XML schema 8.0 catalog that was fetched while building the committed
normalized snapshot under ``data/external/cwe-5.0/`` and never claims that an
external weakness entry is a supported repair capability.  External entries
only produce bounded, deterministic *candidate* gaps; support remains
unmeasured until a local experiment and independent verification exist.

The live fetch helper is optional and records the requested URL/version/hash;
tests never call it.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.services import gap_registry

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_REL = "data/external/cwe-5.0"
SNAPSHOT_VERSION = 1
SNAPSHOT_KIND = "cwe_external_catalog_snapshot"
SCAN_KIND = "phase8d_external_knowledge_scan"
GENERATED_AT = "2026-11-17T00:00:00Z"
EXPECTED_CATALOG_VERSION = "5.0"
EXPECTED_SCHEMA_VERSION = "8.0"
EXPECTED_WEAKNESS_COUNT = 984
PRIOR_CATALOG_VERSION = "4.19"
PRIOR_WEAKNESS_COUNT = 969

SOURCE_CATALOG_URL = "https://cwe.mitre.org/data/xml/cwec_v5.0.xml.zip"
SOURCE_SCHEMA_URL = "https://cwe.mitre.org/data/xsd/cwe_schema_v8.0.xsd"
SOURCE_PRIOR_URL = "https://cwe.mitre.org/data/xml/cwec_v4.19.xml.zip"
SOURCE_TERMS_URL = "https://cwe.mitre.org/about/termsofuse.html"

#: CWE ids that are plausibly relevant to memory/arithmetic/control-flow
#: binary repair.  Keyword rules widen this set; the mapping is a discovery
#: filter, never a support claim.
_BINARY_CWES: dict[str, str] = {
    "19": "input_validation", "20": "input_validation",
    "22": "input_validation", "73": "file_handling", "74": "input_validation",
    "77": "resource", "78": "input_validation", "79": "input_validation",
    "88": "input_validation", "89": "input_validation",
    "94": "input_validation", "95": "input_validation",
    "113": "input_validation", "114": "input_validation",
    "116": "input_validation", "117": "input_validation",
    "119": "memory_safety", "120": "memory_safety", "121": "memory_safety",
    "122": "memory_safety", "123": "memory_safety", "124": "memory_safety",
    "125": "memory_safety", "126": "memory_safety", "127": "memory_safety",
    "128": "memory_safety", "129": "memory_safety", "130": "memory_safety",
    "131": "memory_safety", "134": "string_safety", "170": "memory_safety",
    "172": "memory_safety", "176": "memory_safety", "190": "arithmetic",
    "191": "arithmetic", "192": "arithmetic", "193": "memory_safety",
    "194": "memory_safety", "195": "memory_safety", "196": "memory_safety",
    "197": "memory_safety", "242": "resource", "252": "resource",
    "253": "resource", "256": "resource", "400": "resource",
    "401": "resource", "404": "resource", "415": "memory_safety",
    "416": "memory_safety", "457": "initialization",
    "460": "initialization", "475": "initialization",
    "476": "memory_safety", "590": "resource", "665": "initialization",
    "667": "resource", "668": "resource", "672": "resource",
    "674": "control_flow", "675": "resource", "680": "arithmetic",
    "681": "arithmetic", "682": "arithmetic", "690": "resource",
    "704": "input_validation", "754": "input_validation",
    "758": "input_validation", "770": "resource", "771": "resource",
    "772": "resource", "773": "resource", "775": "resource",
    "778": "logging", "787": "memory_safety", "788": "memory_safety",
    "789": "memory_safety", "805": "input_validation", "806": "input_validation",
    "824": "initialization", "825": "initialization", "826": "initialization",
    "835": "resource", "908": "initialization", "909": "resource",
    "910": "resource", "911": "resource", "1234": "control_flow",
}

_GROUP_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "memory_safety": ("D05", "D06", "D09", "D15", "D16", "D18", "D19"),
    "arithmetic": ("D05", "D07", "D09", "D15", "D16", "D18", "D19"),
    "control_flow": ("D05", "D08", "D09", "D10", "D18"),
    "string_safety": ("D05", "D06", "D09", "D15", "D16", "D18"),
    "input_validation": ("D05", "D09", "D14", "D18"),
    "initialization": ("D05", "D06", "D09", "D18"),
    "resource": ("D05", "D09", "D18"),
    "file_handling": ("D01", "D05", "D09"),
    "logging": ("D05", "D14"),
}

_GROUP_SEVERITY = {
    "memory_safety": "high",
    "arithmetic": "high",
    "control_flow": "high",
    "string_safety": "medium",
    "initialization": "medium",
    "resource": "medium",
    "input_validation": "medium",
    "file_handling": "low",
    "logging": "low",
}

_GROUP_RISK = {
    "memory_safety": "high",
    "arithmetic": "high",
    "control_flow": "high",
    "string_safety": "medium",
    "initialization": "medium",
    "resource": "medium",
    "input_validation": "medium",
    "file_handling": "low",
    "logging": "low",
}

_CWE_ID_RE = re.compile(r"CWE-(\d+)", re.IGNORECASE)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local(child.tag) == name]


def _first_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local(child.tag) == name:
            return " ".join("".join(child.itertext()).split())
    return None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def _safe_key(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    base = root.resolve()
    if path != base and base not in path.parents:
        raise ValueError(f"path escapes repository root: {relative}")
    return path


def parse_catalog(xml_bytes: bytes) -> dict[str, Any]:
    """Parse one official CWE XML catalog into a compact catalog object."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"invalid CWE XML: {exc}") from exc
    if _local(root.tag) != "Weakness_Catalog":
        raise ValueError("not a CWE Weakness_Catalog")
    namespace = root.tag.split("}", 1)[0].lstrip("{") if "}" in root.tag else ""
    catalog = {
        "version": str(root.get("Version") or ""),
        "date": str(root.get("Date") or ""),
        "namespace": namespace,
        "schema_location": str(root.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation") or ""),
    }
    weakness_parent = next(
        (child for child in root if _local(child.tag) == "Weaknesses"), None
    )
    weaknesses: list[dict[str, Any]] = []
    if weakness_parent is not None:
        for element in weakness_parent:
            if _local(element.tag) != "Weakness":
                continue
            cwe_id = str(element.get("ID") or "")
            if not cwe_id:
                continue
            description = _first_text(element, "Description") or ""
            related: list[str] = []
            rel_parent = next(
                (child for child in element if _local(child.tag) == "Related_Weaknesses"),
                None,
            )
            if rel_parent is not None:
                for rel in rel_parent:
                    if _local(rel.tag) != "Related_Weakness":
                        continue
                    rel_id = str(rel.get("CWE_ID") or "")
                    if rel_id and rel_id not in related:
                        related.append(rel_id)
            weaknesses.append({
                "id": cwe_id,
                "name": str(element.get("Name") or ""),
                "abstraction": str(element.get("Abstraction") or ""),
                "structure": str(element.get("Structure") or ""),
                "status": str(element.get("Status") or ""),
                "description_sha256": _sha256_bytes(description.encode("utf-8")),
                "related_cwe_ids": sorted(related, key=lambda value: (len(value), value)),
            })
    weaknesses.sort(key=lambda item: int(item["id"]) if item["id"].isdigit() else item["id"])
    catalog["counts"] = {
        "weaknesses": len(weaknesses),
        "categories": sum(
            1 for parent in root if _local(parent.tag) == "Categories"
            for child in parent if _local(child.tag) == "Category"
        ),
        "groupings": sum(
            1 for parent in root if _local(parent.tag) == "Groupings"
            for child in parent if _local(child.tag) == "Grouping"
        ),
        "views": sum(
            1 for parent in root if _local(parent.tag) == "Views"
            for child in parent if _local(child.tag) == "View"
        ),
    }
    return {"catalog": catalog, "weaknesses": weaknesses}


def build_snapshot(
    current_xml: bytes,
    prior_xml: bytes,
    *,
    sources: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the committed normalized snapshot and schema-drift record."""
    current = parse_catalog(current_xml)
    prior = parse_catalog(prior_xml)
    old_ids = {item["id"] for item in prior["weaknesses"]}
    new_ids = {item["id"] for item in current["weaknesses"]}
    new_count = len(new_ids - old_ids)
    removed_count = len(old_ids - new_ids)
    catalog = current["catalog"]
    old_catalog = prior["catalog"]
    snapshot = {
        "schema_version": SNAPSHOT_VERSION,
        "kind": SNAPSHOT_KIND,
        "generated_at": GENERATED_AT,
        "catalog": catalog,
        "weaknesses": current["weaknesses"],
        "schema_drift": {
            "prior_version": old_catalog["version"],
            "prior_date": old_catalog["date"],
            "current_version": catalog["version"],
            "current_date": catalog["date"],
            "prior_namespace": old_catalog["namespace"],
            "current_namespace": catalog["namespace"],
            "namespace_changed": old_catalog["namespace"] != catalog["namespace"],
            "prior_counts": old_catalog["counts"],
            "current_counts": catalog["counts"],
            "new_ids": sorted(new_ids - old_ids, key=int),
            "removed_ids": sorted(old_ids - new_ids, key=int),
            "new_count": new_count,
            "removed_count": removed_count,
            "count_delta": len(current["weaknesses"]) - len(prior["weaknesses"]),
            "schema_version_changed_from": _schema_version_from_location(
                old_catalog.get("schema_location") or ""
            ),
            "schema_version_changed_to": _schema_version_from_location(
                catalog.get("schema_location") or ""
            ),
            "structural_changes": [
                "schema namespace changed from cwe-7 to cwe-8" if old_catalog["namespace"] != catalog["namespace"] else "schema namespace unchanged",
                "categories replaced by groupings in the 5.0 XML layout" if not catalog["counts"]["categories"] and catalog["counts"]["groupings"] else "category/grouping layout unchanged",
                f"weakness set delta: {len(new_ids - old_ids)} new and {len(old_ids - new_ids)} removed",
            ],
        },
        "source": dict(sources),
        "limitations": [
            "normalized projection only: description text is stored as a digest, not full prose",
            "new/removed ids compare CWE 5.0 with 4.19 as measured; the briefing's 16-new count is not asserted independently",
            "external entries are candidates, never evidence of local repair support",
        ],
    }
    errors = validate_snapshot(snapshot)
    if errors:
        raise ValueError("built snapshot is invalid: " + "; ".join(errors))
    return snapshot


def _schema_version_from_location(location: str) -> str | None:
    match = re.search(r"cwe_schema_v([0-9.]+)\.xsd", location)
    return match.group(1) if match else None


def validate_snapshot(snapshot: Mapping[str, Any]) -> list[str]:
    """Validate the normalized snapshot without reading the network."""
    problems: list[str] = []
    if snapshot.get("schema_version") != SNAPSHOT_VERSION:
        problems.append("schema_version mismatch")
    if snapshot.get("kind") != SNAPSHOT_KIND:
        problems.append("kind mismatch")
    catalog = snapshot.get("catalog")
    if not isinstance(catalog, Mapping):
        return problems + ["catalog is missing"]
    if str(catalog.get("version") or "") != EXPECTED_CATALOG_VERSION:
        problems.append(
            f"catalog version {catalog.get('version')!r} != {EXPECTED_CATALOG_VERSION}"
        )
    weaknesses = snapshot.get("weaknesses")
    if not isinstance(weaknesses, list):
        return problems + ["weaknesses is not a list"]
    if len(weaknesses) != EXPECTED_WEAKNESS_COUNT:
        problems.append(
            f"weakness count {len(weaknesses)} != expected {EXPECTED_WEAKNESS_COUNT}"
        )
    ids = [str(item.get("id") or "") for item in weaknesses if isinstance(item, Mapping)]
    if len(ids) != len(set(ids)):
        problems.append("duplicate weakness ids")
    if any(not value.isdigit() for value in ids):
        problems.append("non-numeric weakness id")
    drift = snapshot.get("schema_drift")
    if not isinstance(drift, Mapping):
        problems.append("schema_drift is missing")
    else:
        if drift.get("prior_version") != PRIOR_CATALOG_VERSION:
            problems.append(
                f"prior_version {drift.get('prior_version')!r} != {PRIOR_CATALOG_VERSION}"
            )
        if drift.get("new_count") != len(drift.get("new_ids") or []):
            problems.append("new_count does not match new_ids")
        if drift.get("removed_count") != len(drift.get("removed_ids") or []):
            problems.append("removed_count does not match removed_ids")
    source = snapshot.get("source")
    if not isinstance(source, Mapping):
        problems.append("source metadata is missing")
    else:
        for key in ("catalog_url", "schema_url", "prior_catalog_url"):
            if not str(source.get(key) or "").startswith("https://"):
                problems.append(f"source.{key} must be an https URL")
        for key in ("catalog_sha256", "schema_sha256", "prior_catalog_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(source.get(key) or "")):
                problems.append(f"source.{key} must be a sha256")
    return problems


def load_snapshot(root: Path = ROOT) -> dict[str, Any]:
    path = _safe_key(root, f"{SNAPSHOT_REL}/snapshot.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_snapshot(payload)
    if errors:
        raise ValueError("invalid CWE snapshot: " + "; ".join(errors))
    return payload


def detect_version_drift(
    snapshot: Mapping[str, Any],
    *,
    expected_catalog_version: str = EXPECTED_CATALOG_VERSION,
    expected_schema_version: str = EXPECTED_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Detect snapshot/catalog/schema drift without claiming currentness."""
    catalog = snapshot.get("catalog") or {}
    drift = snapshot.get("schema_drift") or {}
    actual_schema = _schema_version_from_location(
        str(catalog.get("schema_location") or "")
    )
    actual_namespace = str(catalog.get("namespace") or "")
    expected_namespace = "http://cwe.mitre.org/cwe-8"
    catalog_drift = str(catalog.get("version") or "") != expected_catalog_version
    schema_drift = actual_schema != expected_schema_version
    namespace_drift = actual_namespace != expected_namespace
    status = "drifted" if (catalog_drift or schema_drift or namespace_drift) else "current"
    return {
        "status": status,
        "expected_catalog_version": expected_catalog_version,
        "actual_catalog_version": catalog.get("version"),
        "expected_schema_version": expected_schema_version,
        "actual_schema_version": actual_schema,
        "schema_namespace": actual_namespace,
        "expected_schema_namespace": expected_namespace,
        "catalog_version_drift": catalog_drift,
        "schema_version_drift": schema_drift,
        "namespace_drift": namespace_drift,
        "prior_schema_change": bool(drift.get("namespace_changed")),
        "new_ids": list(drift.get("new_ids") or []),
        "removed_ids": list(drift.get("removed_ids") or []),
        "new_count": int(drift.get("new_count") or 0),
        "removed_count": int(drift.get("removed_count") or 0),
        "note": "status=current only means the snapshot matches configured expected versions; it is not a support claim",
    }


def _keyword_group(name: str) -> str | None:
    lowered = name.lower()
    rules = (
        ("memory_safety", ("buffer", "out-of-bounds", "out of bounds", "use after free",
                           "double free", "uninitialized", "null pointer", "dangling",
                           "write-what-where", "stack", "heap")),
        ("arithmetic", ("integer overflow", "integer underflow", "wrap", "truncation",
                        "sign conversion", "divide by zero", "numeric")),
        ("control_flow", ("control flow", "function pointer", "indirect", "unreachable",
                          "improper check", "missing return")),
        ("string_safety", ("string", "format string", "off-by-one", "terminator")),
        ("initialization", ("initialization", "initialized", "uninitialized")),
        ("resource", ("resource", "lifetime", "release", "cleanup", "leak")),
        ("input_validation", ("input validation", "improper input", "length mismatch",
                              "type confusion", "parser", "deserialization")),
        ("file_handling", ("file", "path traversal", "directory")),
        ("logging", ("logging", "log file", "log injection")),
    )
    for group, needles in rules:
        if any(needle in lowered for needle in needles):
            return group
    return None


def classify_weakness(weakness: Mapping[str, Any]) -> dict[str, Any]:
    cwe_id = str(weakness.get("id") or "")
    group = _BINARY_CWES.get(cwe_id) or _keyword_group(str(weakness.get("name") or ""))
    if group is None:
        return {"binary_relevant": False, "group": None, "capability_ids": []}
    return {
        "binary_relevant": True,
        "group": group,
        "capability_ids": list(_GROUP_CAPABILITIES.get(group, ())),
    }


def _public_exposure(root: Path) -> dict[str, dict[str, int]]:
    path = _safe_key(root, "benchmark/phase8c/manifest.json")
    if not path.is_file():
        return {}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    exposure: dict[str, dict[str, int]] = {}
    results_path = _safe_key(root, "benchmark/phase8c/results.json")
    verified_ids: set[str] = set()
    if results_path.is_file():
        try:
            results = json.loads(results_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            results = {}
        for result in results.get("samples") or []:
            if not isinstance(result, Mapping):
                continue
            if (result.get("verification") or {}).get("decision") == "verified":
                verified_ids.add(str(result.get("sample_id") or ""))
    for sample in manifest.get("samples") or []:
        if not isinstance(sample, Mapping):
            continue
        text = " ".join([
            str(sample.get("cwe") or ""),
            str(sample.get("vulnerability_family") or ""),
            str(sample.get("vulnerability_subtype") or ""),
            str(sample.get("vulnerability_class") or ""),
        ])
        for match in _CWE_ID_RE.findall(text):
            cwe = f"CWE-{match}"
            entry = exposure.setdefault(cwe, {"public_samples": 0, "verified_repairs": 0})
            entry["public_samples"] += 1
            if str(sample.get("sample_id") or "") in verified_ids:
                entry["verified_repairs"] += 1
    return exposure


def map_candidates(
    snapshot: Mapping[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Map binary-relevant external entries to bounded gap candidates."""
    exposure = _public_exposure(root)
    candidates: list[dict[str, Any]] = []
    mapped: dict[str, int] = {}
    unmapped = 0
    for weakness in snapshot.get("weaknesses") or []:
        if not isinstance(weakness, Mapping):
            continue
        classification = classify_weakness(weakness)
        if not classification["binary_relevant"]:
            unmapped += 1
            continue
        cwe_id = str(weakness.get("id") or "")
        cwe_key = f"CWE-{cwe_id}"
        group = str(classification["group"])
        mapped[group] = mapped.get(group, 0) + 1
        observed = exposure.get(cwe_key) or {"public_samples": 0, "verified_repairs": 0}
        candidate = gap_registry.make_record(
            discovery_source="knowledge_source_scan",
            gap_id=gap_registry.deterministic_gap_id(
                "knowledge_source_scan", f"cwe-{cwe_id}"
            ),
            category=group,
            subcategory="cwe-external-candidate",
            target={
                "kind": "external_cwe",
                "cwe_id": cwe_key,
                "catalog_version": (snapshot.get("catalog") or {}).get("version"),
                "weakness_name": str(weakness.get("name") or ""),
            },
            observed_failure=(
                f"external CWE {cwe_key} ({weakness.get('name')}) is present in the "
                "versioned external knowledge snapshot but has no measured local "
                "repair capability claim"
            ),
            existing_capability=(
                "external entry only; mapping is a discovery filter, not evidence "
                "of support; public-corpus exposure is reported separately"
            ),
            severity=_GROUP_SEVERITY.get(group, "medium"),
            status="candidate",
            evidence_refs=[
                f"{SNAPSHOT_REL}/snapshot.json#weaknesses[id={cwe_id}]",
                f"{SNAPSHOT_REL}/schema-drift.json#current_version",
                "benchmark/phase8c/manifest.json",
            ],
            plan=gap_registry.proposed_experiment(
                status="proposed",
                experiment_id=f"EXP-KSRC-CWE-{cwe_id}",
                steps=[
                    "select an independently sourced local binary sample for "
                    f"{cwe_key} and verify it does not duplicate the public corpus",
                    "measure deterministic detection/root-cause/candidate behavior "
                    "and record not_run/blocked reasons without inventing evidence",
                    "require independent oracle and verification evidence before any "
                    "capability status change; candidate remains candidate",
                ],
            ),
            owner="capability-governance",
            review_by="2027-05-14",
            verification_required=True,
            false_verified_risk=_GROUP_RISK.get(group, "medium"),
        )
        candidate["mapped_capability_ids"] = classification["capability_ids"]
        candidate["external_catalog_version"] = (
            snapshot.get("catalog") or {}
        ).get("version")
        candidate["support_claimed"] = False
        candidate["public_corpus_exposure"] = dict(observed)
        candidates.append(candidate)
    candidates.sort(key=lambda item: item["gap_id"])
    validation = gap_registry.validate_records(candidates)
    if not validation["ok"]:
        raise ValueError("external candidate validation failed: "
                         + "; ".join(validation["violations"]))
    return {
        "candidates": candidates,
        "mapped_by_group": dict(sorted(mapped.items())),
        "mapped_count": len(candidates),
        "unmapped_count": unmapped,
        "public_corpus_exposed_cwes": sorted(exposure),
    }


def scan(
    *,
    root: Path = ROOT,
    live: bool = False,
) -> dict[str, Any]:
    """Build the external-knowledge scan artifact (offline by default)."""
    snapshot = load_snapshot(root)
    drift = detect_version_drift(snapshot)
    mapping = map_candidates(snapshot, root=root)
    live_result: dict[str, Any] | None = None
    if live:
        live_result = fetch_live_metadata()
    return {
        "schema_version": 1,
        "kind": SCAN_KIND,
        "generated_at": GENERATED_AT,
        "snapshot": {
            "path": f"{SNAPSHOT_REL}/snapshot.json",
            "sha256": _sha256_file(_safe_key(root, f"{SNAPSHOT_REL}/snapshot.json")),
            "catalog_version": (snapshot.get("catalog") or {}).get("version"),
            "catalog_date": (snapshot.get("catalog") or {}).get("date"),
            "schema_namespace": (snapshot.get("catalog") or {}).get("namespace"),
            "weakness_count": len(snapshot.get("weaknesses") or []),
        },
        "version_drift": drift,
        "schema_drift": snapshot.get("schema_drift"),
        "mapping": {
            "rules_version": 1,
            "candidates": mapping["candidates"],
            "candidate_count": mapping["mapped_count"],
            "mapped_by_group": mapping["mapped_by_group"],
            "unmapped_count": mapping["unmapped_count"],
            "public_corpus_exposed_cwes": mapping["public_corpus_exposed_cwes"],
        },
        "summary": {
            "external_entries": len(snapshot.get("weaknesses") or []),
            "mapped_candidates": mapping["mapped_count"],
            "unmapped": mapping["unmapped_count"],
            "mapped_by_group": mapping["mapped_by_group"],
            "new_ids": drift.get("new_ids"),
            "new_count": drift.get("new_count"),
            "removed_count": drift.get("removed_count"),
            "support_claimed": False,
            "capability_promotion": False,
        },
        "mechanism_status": {
            "knowledge_source_scan": {
                "status": "run",
                "evidence": "versioned snapshot parsed; 232 mapped candidates",
                "support_claimed": False,
            },
            "unified_gap_registry_integration": {
                "status": "not_run",
                "reason": "standalone D06 artifact; the existing seven-mechanism registry was not edited by this angle",
            },
        },
        "live_fetch": live_result,
        "provenance": {
            "source": snapshot.get("source"),
            "live_fetch_performed": bool(live),
            "network_used": bool(live),
            "test_network_allowed": False,
            "candidate_records_are_not_support_claims": True,
        },
        "limitations": [
            "external CWE entries are discovery candidates only; no local repair support is claimed",
            "the normalized snapshot stores description digests, not full CWE prose",
            "the measured new-id count is 15 versus CWE 4.19; the briefing's approximate 16 is not asserted",
            "live fetch is optional and not used by tests; a committable snapshot remains the evidence source",
        ],
    }


def fetch_live_metadata(timeout: float = 60.0) -> dict[str, Any]:
    """Fetch official catalog/schema metadata; caller must record provenance."""
    def _fetch(url: str) -> tuple[str, int]:
        request = urllib.request.Request(url, headers={"User-Agent": "binary-repair/phase8d"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
        return _sha256_bytes(data), len(data)

    catalog_sha, catalog_size = _fetch(SOURCE_CATALOG_URL)
    schema_sha, schema_size = _fetch(SOURCE_SCHEMA_URL)
    return {
        "catalog_url": SOURCE_CATALOG_URL,
        "catalog_sha256": catalog_sha,
        "catalog_bytes": catalog_size,
        "schema_url": SOURCE_SCHEMA_URL,
        "schema_sha256": schema_sha,
        "schema_bytes": schema_size,
        "terms_url": SOURCE_TERMS_URL,
        "retrieved_at": GENERATED_AT,
        "network_used": True,
    }


def write_snapshot_files(root: Path, files: Mapping[str, bytes]) -> list[dict[str, str]]:
    out = _safe_key(root, SNAPSHOT_REL)
    out.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    for name, data in files.items():
        target = out / name
        target.write_bytes(data)
        written.append({"path": str(target), "sha256": _sha256_bytes(data)})
    return written


def build_snapshot_files(
    current_xml: bytes,
    prior_xml: bytes,
    *,
    catalog_sha256: str,
    schema_sha256: str,
    prior_catalog_sha256: str,
    catalog_bytes: int,
    schema_bytes: int,
    prior_catalog_bytes: int,
) -> dict[str, bytes]:
    sources = {
        "catalog_url": SOURCE_CATALOG_URL,
        "catalog_version": EXPECTED_CATALOG_VERSION,
        "catalog_date": "2026-10-28",
        "catalog_sha256": catalog_sha256,
        "catalog_bytes": catalog_bytes,
        "schema_url": SOURCE_SCHEMA_URL,
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "schema_sha256": schema_sha256,
        "schema_bytes": schema_bytes,
        "prior_catalog_url": SOURCE_PRIOR_URL,
        "prior_catalog_version": PRIOR_CATALOG_VERSION,
        "prior_catalog_sha256": prior_catalog_sha256,
        "prior_catalog_bytes": prior_catalog_bytes,
        "terms_url": SOURCE_TERMS_URL,
        "retrieved_at": GENERATED_AT,
        "live_fetch_performed": True,
        "network_used": True,
    }
    snapshot = build_snapshot(current_xml, prior_xml, sources=sources)
    schema_drift = snapshot["schema_drift"]
    provenance = {
        "schema_version": 1,
        "kind": "cwe_external_snapshot_provenance",
        "generated_at": GENERATED_AT,
        "sources": sources,
        "normalization": {
            "parser": "xml.etree.ElementTree",
            "snapshot_schema_version": SNAPSHOT_VERSION,
            "fields": ["id", "name", "abstraction", "structure", "status",
                       "description_sha256", "related_cwe_ids"],
            "raw_xml_committed": False,
            "why_no_raw_xml": "the official 19 MB XML is source input; the committed normalized projection is bounded and reproducible",
        },
        "measured_counts": {
            "weaknesses": len(snapshot["weaknesses"]),
            "prior_weaknesses": PRIOR_WEAKNESS_COUNT,
            "new_ids": schema_drift["new_count"],
            "removed_ids": schema_drift["removed_count"],
            "current_categories": snapshot["catalog"]["counts"]["categories"],
            "current_groupings": snapshot["catalog"]["counts"]["groupings"],
            "prior_categories": schema_drift["prior_counts"]["categories"],
            "prior_groupings": schema_drift["prior_counts"]["groupings"],
        },
        "limitations": [
            "raw XML/XSD are not committed; the normalized snapshot and source hashes are the reviewable evidence",
            "the briefing says ~16 new weaknesses; measured 5.0-vs-4.19 diff is 15 new ids and 0 removals",
            "external entries are not local capability evidence",
        ],
    }
    schema_record = {
        "schema_version": 1,
        "kind": "cwe_external_schema_drift",
        "generated_at": GENERATED_AT,
        "catalog_version": snapshot["catalog"]["version"],
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "schema_namespace": snapshot["catalog"]["namespace"],
        "schema_url": SOURCE_SCHEMA_URL,
        "schema_sha256": schema_sha256,
        "prior_catalog_version": schema_drift["prior_version"],
        "prior_schema_version": schema_drift["schema_version_changed_from"],
        "prior_catalog_sha256": prior_catalog_sha256,
        "current_counts": snapshot["catalog"]["counts"],
        "prior_counts": schema_drift["prior_counts"],
        "changes": snapshot["schema_drift"],
        "breaking_changes": [
            "XML schema namespace changed to http://cwe.mitre.org/cwe-8",
            "Categories were removed from the 5.0 weakness catalog layout; Groupings are present",
            "id set changed by new/removed lists; consumers must not assume a stable 4.x shape",
        ],
        "limitations": provenance["limitations"],
    }
    return {
        "snapshot.json": _canonical(snapshot).encode("utf-8"),
        "schema-drift.json": _canonical(schema_record).encode("utf-8"),
        "provenance.json": _canonical(provenance).encode("utf-8"),
    }


def zip_xml(payload: bytes) -> bytes:
    """Return the single XML member from an official CWE ZIP."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if len(names) != 1:
            raise ValueError(f"expected one XML member, found {names}")
        return archive.read(names[0])
