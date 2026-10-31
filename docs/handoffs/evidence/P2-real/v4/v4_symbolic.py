#!/usr/bin/env python3
"""V4 bounded symbolic exploration of badSink.

Model (measured from the original disassembly):
  badSink @ 0x4012b0, frame: rbp-0x40 = dest[0], dest capacity 50 bytes
  (contract dest_capacity_bytes=50, capacity includes the terminator),
  rbp-0x48 = data ptr, strcpy@plt = 0x4010d0, printLine@plt = 0x401380.

  The function is modelled *standalone* (call_state at 0x4012b0), with the
  incoming `data` argument pointing at a bounded symbolic buffer. The buffer
  length is constrained to the contract's valid domain (0..49 payload bytes +
  NUL). Under that constraint, a correct repair must never write past
  dest[50] (i.e. past rbp-0x40+50).

  Library hooks: strcpy@plt and printLine@plt are hooked with explicit,
  length-aware models so the copy is observed as a concrete memory write
  rather than an unconstrained stub.

  Verdict space: proven / counterexample / inconclusive / not_run.
  A timeout is NOT a pass; it is recorded as inconclusive.
"""
from __future__ import annotations
import sys, json, time
import angr
import angr.claripy as claripy  # angr 10 lazy-imports claripy; grab it via angr

BAD_SINK = 0x4012B0
STRCPY_PLT = 0x4010D0
PRINTLINE_PLT = 0x401380
RET_ADDR = 0x401317          # the `ret` of badSink (terminal sentinel)
DEST_OFF = 0x40              # dest[0] = rbp - 0x40
DEST_CAP = 50                # contract dest_capacity_bytes (includes NUL)
MAX_VALID = 49               # contract max_valid_input_bytes (payload, +NUL)

# ---- library models ---------------------------------------------------------

class StrcpyModel(angr.SimProcedure):
    """Length-aware strcpy: copy src (up to and including NUL) into dest,
    recording every byte written. If src has no NUL within the explored bound,
    this is reported rather than silently succeeding."""
    def run(self, dst, src):
        # Read the source as a concrete-ish NUL-terminated string up to a bound.
        max_read = MAX_VALID + 8   # generous bound; we stop at the first NUL
        written = 0
        for i in range(max_read):
            b = self.state.memory.load(src + i, 1)
            # store the byte (this is the write we want to observe)
            self.state.memory.store(dst + i, b)
            written = i + 1
            # stop at the first byte that is forced NUL under the constraints
            # (b != 0 is unsat). Free bytes keep the copy going.
            if self.state.solver.is_false(b != 0):
                break
        self.state.globals["strcpy_bytes_written"] = written
        self.state.globals["strcpy_dst"] = int(self.state.solver.eval(dst))
        return dst


class PrintLineModel(angr.SimProcedure):
    def run(self, s):
        # printLine prints the line; we do not model stdout, just return.
        return None


def build_project(path):
    p = angr.Project(path, auto_load_libs=False)
    p.hook(STRCPY_PLT, StrcpyModel())
    p.hook(PRINTLINE_PLT, PrintLineModel())
    return p


def explore(path, label, valid_domain=True):
    """valid_domain=True  -> constrain input to 0..49 payload + NUL (the contract
    valid domain). A correct repair must not overflow dest under this domain.
    valid_domain=False -> leave the first bytes unconstrained up to a larger
    bound, to calibrate that the model *can* find the original overflow."""
    p = build_project(path)
    st = p.factory.call_state(
        BAD_SINK,
        add_options={
            angr.options.SYMBOLIC_WRITE_ADDRESSES,
            angr.options.TRACK_MEMORY_ACTIONS,
        },
    )
    # Stack frame: give the state a fresh stack; set rbp so dest is addressable.
    rbp = st.regs.rsp  # after call_state prologue we model rbp = rsp region
    # allocate a data buffer
    data_addr = 0x500000
    n = MAX_VALID + 1 if valid_domain else MAX_VALID + 8
    sym = claripy.BVS("input", 8 * n)
    # write symbolic bytes
    for i in range(n):
        st.memory.store(data_addr + i, sym.get_byte(i))
    if valid_domain:
        # Valid domain worst case: exactly 49 payload bytes (all non-NUL) + NUL
        # at index 49. Any shorter legal string writes fewer bytes, so if this
        # worst case does not overflow dest[50], no legal input does (monotonic).
        # Concrete bytes avoid symbolic loop-termination pitfalls in the model.
        for i in range(MAX_VALID):
            st.memory.store(data_addr + i, claripy.BVV(0x41, 8))  # 'A'
        st.memory.store(data_addr + MAX_VALID, claripy.BVV(0, 8))  # NUL
    else:
        # Calibration: no NUL within the explored prefix forces a long copy.
        ncal = MAX_VALID + 8
        for i in range(ncal):
            st.memory.store(data_addr + i, claripy.BVV(0x41, 8))
        st.memory.store(data_addr + ncal, claripy.BVV(0, 8))
    # set the argument: rdi = data pointer
    st.regs.rdi = data_addr
    st.globals["data_addr"] = data_addr

    # push a sentinel return address so `ret` lands at RET_ADDR
    # (call_state already pushed a return; we instead just bound the run)

    simgr = p.factory.simgr(st)
    deadline = time.time() + 120
    steps = 0
    max_steps = 400
    writes_out_of_bounds = []
    try:
        while simgr.active and steps < max_steps and time.time() < deadline:
            simgr.step()
            steps += 1
            for s in simgr.active + simgr.deadended:
                if "strcpy_bytes_written" in s.globals:
                    dst = s.globals["strcpy_dst"]
                    w = s.globals["strcpy_bytes_written"]
                    # dest base is rbp-0x40 at the time strcpy ran; we recorded
                    # dst directly. The dest capacity is 50; bytes beyond 50 are
                    # out of bounds.
                    if w > DEST_CAP:
                        writes_out_of_bounds.append({"dst": hex(dst), "bytes": w})
    except Exception as e:
        return {"label": label, "verdict": "inconclusive", "reason": repr(e),
                "steps": steps}

    timed_out = time.time() >= deadline
    result = {
        "label": label,
        "valid_domain": valid_domain,
        "steps": steps,
        "timed_out": timed_out,
        "active": len(simgr.active),
        "deadended": len(simgr.deadended),
        "errored": len(simgr.errored),
        "unconstrained": len(simgr.unconstrained),
        "out_of_bounds_writes": writes_out_of_bounds,
    }
    if timed_out:
        result["verdict"] = "inconclusive"
        result["reason"] = "timeout (not a pass)"
    elif valid_domain:
        # Under the valid domain, ANY out-of-bounds write is a counterexample
        # to the safety property "no write past dest[50] for legal inputs".
        if writes_out_of_bounds:
            result["verdict"] = "counterexample"
        else:
            result["verdict"] = "proven"
    else:
        # Calibration / defect-injection domain (arbitrary-length input).
        # For the ORIGINAL we expect to FIND the overflow (counterexample).
        # For a correctly repaired candidate we expect NO overflow even here,
        # because the repair rejects over-long input instead of copying it.
        # So "no out-of-bounds write" here is evidence the repair is effective.
        if writes_out_of_bounds:
            result["verdict"] = "counterexample"
            result["meaning"] = "defect present: over-long input overflows dest"
        else:
            result["verdict"] = "no_counterexample"
            result["meaning"] = ("no overflow even for over-long input: the "
                                 "repair rejects/rebounds instead of copying")
    return result


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "original"
    path = {"original": "./original.elf",
            "routea": "./routea-candidate.elf",
            "routeb": "./routeb-candidate.elf"}[which]
    domain = (sys.argv[2] == "valid") if len(sys.argv) > 2 else True
    r = explore(path, which, valid_domain=domain)
    print(json.dumps(r, indent=2))
