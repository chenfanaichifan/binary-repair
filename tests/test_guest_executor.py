"""Host-safe tests for workers/executor (T6.2).

The guest executor itself is guest-only. These tests exercise its pure
verification/derivation helpers and never run a binary.
"""

from __future__ import annotations

from workers.executor import self_test as st


def test_account_guard() -> None:
    st.test_account_guard()


def test_package_verification() -> None:
    st.test_package_verification()


def test_tamper_rejected() -> None:
    st.test_tamper_rejected()


def test_unlisted_file_rejected() -> None:
    st.test_unlisted_file_rejected()


def test_traversal_rejected() -> None:
    st.test_traversal_rejected()


def test_symlink_rejected() -> None:
    st.test_symlink_rejected()


def test_route_b_gate_derivation() -> None:
    st.test_route_b_gates()


def test_route_a_gate_derivation() -> None:
    st.test_route_a_gates()


def test_sums_sorted_and_complete() -> None:
    st.test_sums_are_sorted_and_complete()
