from scripts.fuzz_repair_benchmark import build_cases, mutate


def test_mutation_is_deterministic_and_bounded():
    a = build_cases({"poc": [{"argv": ["hi"]}]}, 5, 7)
    b = build_cases({"poc": [{"argv": ["hi"]}]}, 5, 7)
    assert a == b
    assert len(a) == 5
    assert all(row["argv"] for row in a)


def test_empty_base_is_safe():
    assert len(mutate([], __import__("random").Random(1), 2)) == 2
