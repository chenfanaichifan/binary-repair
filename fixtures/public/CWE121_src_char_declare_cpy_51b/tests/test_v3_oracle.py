"""Tests for the V3 assertion layer.

These tests execute **no binary**. They exercise the pure comparison logic with
synthetic observations, so they can run on the host and in CI, which the project
requires: the sample and any candidate run only inside the disposable guest.

Run from this directory:

    python -m unittest test_v3_oracle -v
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import v3_oracle as oracle  # noqa: E402

HERE = Path(__file__).resolve().parent
VALID = HERE / "valid.json"
INVALID = HERE / "invalid.json"
DEST_CAPACITY = 50
MAX_VALID_LEN = 49


def expected_observation(case: dict) -> oracle.Observation:
    """The observation a conforming candidate must produce for this case."""
    expected = case["expected"]
    return oracle.Observation(
        return_code=expected["return_code"],
        stdout=expected["stdout"].encode("utf-8"),
        stderr=expected["stderr"].encode("utf-8"),
    )


def all_observations(*manifests: dict) -> dict[str, oracle.Observation]:
    observations: dict[str, oracle.Observation] = {}
    for manifest in manifests:
        for case in manifest["tests"]:
            observations[case["id"]] = expected_observation(case)
    return observations


class ManifestLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.valid = oracle.load_manifest(VALID)
        cls.invalid = oracle.load_manifest(INVALID)

    def test_real_manifests_load(self) -> None:
        self.assertEqual(self.valid["schema_version"], oracle.SCHEMA_VERSION)
        self.assertEqual(len(self.valid["tests"]), 4)
        self.assertEqual(len(self.invalid["tests"]), 2)
        self.assertEqual(
            self.valid["original_sha256"], self.invalid["original_sha256"]
        )

    def test_manifest_pair_matches_contract(self) -> None:
        oracle.check_manifest_pair(
            self.valid,
            self.invalid,
            dest_capacity=DEST_CAPACITY,
            max_valid_len=MAX_VALID_LEN,
        )

    def test_wrong_schema_version_is_rejected(self) -> None:
        payload = copy.deepcopy(self.valid)
        payload["schema_version"] = 2
        with self.assertRaises(oracle.ManifestError):
            oracle.validate_manifest(payload, name="bad.json")

    def test_duplicate_case_id_is_rejected(self) -> None:
        payload = copy.deepcopy(self.valid)
        payload["tests"][1]["id"] = payload["tests"][0]["id"]
        with self.assertRaises(oracle.ManifestError):
            oracle.validate_manifest(payload, name="dup.json")

    def test_non_integer_return_code_is_rejected(self) -> None:
        payload = copy.deepcopy(self.valid)
        payload["tests"][0]["expected"]["return_code"] = "0"
        with self.assertRaises(oracle.ManifestError):
            oracle.validate_manifest(payload, name="rc.json")

    def test_missing_expected_field_is_rejected(self) -> None:
        payload = copy.deepcopy(self.valid)
        del payload["tests"][0]["expected"]["stderr"]
        with self.assertRaises(oracle.ManifestError):
            oracle.validate_manifest(payload)


class ContractBoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.valid = oracle.load_manifest(VALID)
        cls.invalid = oracle.load_manifest(INVALID)

    def test_valid_case_over_capacity_is_rejected(self) -> None:
        payload = copy.deepcopy(self.valid)
        payload["tests"][3]["argv"][1] = "A" * (MAX_VALID_LEN + 1)
        with self.assertRaises(oracle.ManifestError):
            oracle.validate_contract_bounds(
                payload, dest_capacity=DEST_CAPACITY, max_valid_len=MAX_VALID_LEN
            )

    def test_invalid_case_within_capacity_is_rejected(self) -> None:
        payload = copy.deepcopy(self.invalid)
        payload["tests"][0]["argv"][1] = "A" * MAX_VALID_LEN
        with self.assertRaises(oracle.ManifestError):
            oracle.validate_contract_bounds(
                payload, dest_capacity=DEST_CAPACITY, max_valid_len=MAX_VALID_LEN
            )

    def test_capacity_disagreeing_with_max_valid_len_is_rejected(self) -> None:
        with self.assertRaises(oracle.ManifestError):
            oracle.validate_contract_bounds(
                self.valid, dest_capacity=DEST_CAPACITY, max_valid_len=DEST_CAPACITY
            )

    def test_kind_in_the_wrong_manifest_is_rejected(self) -> None:
        swapped = copy.deepcopy(self.invalid)
        swapped["tests"][0]["kind"] = "valid"
        with self.assertRaises(oracle.ManifestError):
            oracle.check_manifest_pair(self.valid, swapped)

    def test_pair_with_different_case_id_is_rejected(self) -> None:
        other = copy.deepcopy(self.invalid)
        other["case_id"] = "some-other-case"
        with self.assertRaises(oracle.ManifestError):
            oracle.check_manifest_pair(self.valid, other)

    def test_length_is_counted_in_bytes_not_characters(self) -> None:
        case = {"argv": ["./original", "é"], "kind": "valid"}
        self.assertEqual(oracle.input_length(case), 2)


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.valid = oracle.load_manifest(VALID)
        cls.invalid = oracle.load_manifest(INVALID)
        cls.both = (cls.valid, cls.invalid)

    def evaluate_all(
        self, observations: dict[str, oracle.Observation]
    ) -> oracle.SuiteResult:
        suites = [oracle.evaluate(manifest, observations) for manifest in self.both]
        cases = tuple(case for suite in suites for case in suite.cases)
        result = oracle.PASSED
        if any(suite.result == oracle.FAILED for suite in suites):
            result = oracle.FAILED
        elif any(suite.result == oracle.NOT_RUN for suite in suites):
            result = oracle.NOT_RUN
        return oracle.SuiteResult(
            gate=oracle.GATE,
            result=result,
            cases=cases,
            passed=sum(suite.passed for suite in suites),
            failed=sum(suite.failed for suite in suites),
            not_run=sum(suite.not_run for suite in suites),
        )

    def test_conforming_candidate_passes_six_of_six(self) -> None:
        suite = self.evaluate_all(all_observations(*self.both))
        self.assertEqual(suite.result, oracle.PASSED)
        self.assertEqual((suite.passed, suite.failed, suite.not_run), (6, 0, 0))

    def test_wrong_return_code_fails(self) -> None:
        observations = all_observations(*self.both)
        observations["invalid-first"] = oracle.Observation(
            return_code=0, stdout=b"", stderr=b""
        )
        suite = self.evaluate_all(observations)
        self.assertEqual(suite.result, oracle.FAILED)
        failed_ids = [c.case_id for c in suite.cases if c.result == oracle.FAILED]
        self.assertEqual(failed_ids, ["invalid-first"])

    def test_missing_trailing_newline_in_stderr_fails(self) -> None:
        observations = all_observations(*self.both)
        observations["invalid-longer"] = oracle.Observation(
            return_code=1,
            stdout=b"",
            stderr=b"ERROR: input exceeds destination capacity",
        )
        suite = self.evaluate_all(observations)
        self.assertEqual(suite.result, oracle.FAILED)
        case = next(c for c in suite.cases if c.case_id == "invalid-longer")
        self.assertIn("stderr", " ".join(case.mismatches))

    def test_extra_stdout_on_the_invalid_path_fails(self) -> None:
        observations = all_observations(*self.both)
        observations["invalid-first"] = oracle.Observation(
            return_code=1,
            stdout=b"\n",
            stderr=b"ERROR: input exceeds destination capacity\n",
        )
        self.assertEqual(self.evaluate_all(observations).result, oracle.FAILED)

    def test_missing_observation_is_not_run_never_passed(self) -> None:
        observations = all_observations(*self.both)
        del observations["valid-typical"]
        suite = self.evaluate_all(observations)
        self.assertEqual(suite.result, oracle.NOT_RUN)
        self.assertEqual((suite.passed, suite.failed, suite.not_run), (5, 0, 1))
        self.assertNotEqual(suite.obligation()["result"], oracle.PASSED)

    def test_no_observations_is_not_run(self) -> None:
        suite = self.evaluate_all({})
        self.assertEqual(suite.result, oracle.NOT_RUN)
        self.assertEqual(suite.passed, 0)

    def test_failure_outranks_missing_evidence(self) -> None:
        observations = all_observations(*self.both)
        del observations["valid-typical"]
        observations["invalid-first"] = oracle.Observation(
            return_code=0, stdout=b"A" * 50 + b"\n", stderr=b""
        )
        suite = self.evaluate_all(observations)
        self.assertEqual(suite.result, oracle.FAILED)
        self.assertEqual((suite.failed, suite.not_run), (1, 1))

    def test_vulnerable_original_scores_four_of_six(self) -> None:
        """The original binary is measured evidence for V0, not a passing V3."""
        observations = all_observations(*self.both)
        observations["invalid-first"] = oracle.Observation(
            return_code=0, stdout=b"A" * 50 + b"\n", stderr=b""
        )
        observations["invalid-longer"] = oracle.Observation(
            return_code=-11, stdout=b"", stderr=b""
        )
        suite = self.evaluate_all(observations)
        self.assertEqual(suite.result, oracle.FAILED)
        self.assertEqual((suite.passed, suite.failed), (4, 2))
        self.assertEqual(suite.obligation()["result"], oracle.FAILED)

    def test_extra_observation_ids_are_ignored(self) -> None:
        observations = all_observations(*self.both)
        observations["not-in-the-manifest"] = oracle.Observation(return_code=7)
        self.assertEqual(self.evaluate_all(observations).result, oracle.PASSED)

    def test_unexpected_output_file_fails(self) -> None:
        observations = all_observations(*self.both)
        observations["valid-empty"] = oracle.Observation(
            return_code=0,
            stdout=b"\n",
            stderr=b"",
            output_files={"core": b"x"},
        )
        self.assertEqual(self.evaluate_all(observations).result, oracle.FAILED)

    def test_obligation_shape_matches_acceptance_contract(self) -> None:
        suite = self.evaluate_all(all_observations(*self.both))
        obligation = suite.obligation()
        self.assertEqual(set(obligation), {"kind", "required", "result", "detail"})
        self.assertEqual(obligation["kind"], "behaviour")
        self.assertTrue(obligation["required"])
        self.assertEqual(obligation["result"], oracle.PASSED)


class FileEvaluationTests(unittest.TestCase):
    def test_evaluate_files_uses_both_manifests(self) -> None:
        valid = oracle.load_manifest(VALID)
        invalid = oracle.load_manifest(INVALID)
        suite = oracle.evaluate_files(
            [VALID, INVALID], all_observations(valid, invalid)
        )
        self.assertEqual(suite.result, oracle.PASSED)
        self.assertEqual(suite.passed, 6)


if __name__ == "__main__":
    unittest.main()
