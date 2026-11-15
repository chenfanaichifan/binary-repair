from app.services.repair.plan_evidence_links import build_evidence_links


def test_v2_links_and_hashes():
    plan = {
        "schema_version": 2,
        "security_invariants": ["copy_len < 16"],
        "verification": {"security_conditions": ["overflow_blocked"]},
        "evidence_refs": ["static.capacity", "poc.input"],
    }
    result = build_evidence_links(
        plan, assembly="ret\n",
        candidate={"gate": "pass", "candidate_sha256": "a" * 64},
    )
    assert result["plan_sha256"]
    assert result["assembly_sha256"]
    assert result["candidate_sha256"] == "a" * 64
    assert result["links"][0]["source"] == "provided"


def test_v1_has_no_fake_v2_links():
    result = build_evidence_links(
        {"schema_version": 1, "required_invariant": "x"},
        assembly=None, candidate=None,
    )
    assert result["links"] == []
