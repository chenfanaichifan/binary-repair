from app.services.errno_signature import compare, set_state


def test_errno_set_state():
    assert set_state(0) == "unset"
    assert set_state(22) == "set"
    assert set_state(None) == "unknown"


def test_errno_signature_is_conservative():
    assert compare(None, 0) == "not_run"
    assert compare(0, 0) == "matched"
    assert compare(22, 5) == "matched"  # both set; value may differ by libc path
    assert compare(0, 22) == "mismatch"
    assert compare(22, 0) == "mismatch"
