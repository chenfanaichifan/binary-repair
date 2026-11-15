from types import SimpleNamespace
from app.services.native_trace import NativeTrace, from_case_result, unavailable


def test_n1_trace_does_not_fabricate_registers():
    case = SimpleNamespace(case_id="c", exit_code=139, stdout="", stderr="signal 11",
                           syscall_errors=["EINVAL"])
    trace = from_case_result(case)
    assert trace.available and trace.signal == 11
    assert trace.registers == {} and trace.stack == []
    assert trace.to_dict()["schema_version"] == 1


def test_unavailable_is_explicit():
    trace = unavailable("c", "gdb not installed")
    assert trace.to_dict()["status"] == "not_run"
    assert trace.available is False
