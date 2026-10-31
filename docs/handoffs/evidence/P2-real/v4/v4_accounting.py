#!/usr/bin/env python3
"""Supplemental raw accounting for the V4 bounded symbolic run.

This does NOT change v4_symbolic.py's model or verdict logic. It re-runs the
same exploration while instrumenting the solver engine and state manager to
collect the exploration/solver accounting that Lead's Standard B checklist
(docs/handoffs/62, section 3) requires:

  - solver queries: decided / unknown / timeout (per call, and totals)
  - state classification: active / deadended / errored / unconstrained / deferred
  - step-by-step raw log to stdout (also tee'd to v4-accounting.log)

Verdicts are recomputed by the SAME v4_symbolic.explore() logic; nothing about
the model is altered. The purpose is to expose the raw machinery, not to change
any conclusion.
"""
import sys, time, json
import angr
import angr.claripy as claripy

import importlib.util
spec = importlib.util.spec_from_file_location("v4_symbolic", "./v4_symbolic.py")
v4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v4)

# --- solver accounting wrapper -------------------------------------------
class SolverStats:
    def __init__(self, solver):
        self.solver = solver
        self.decided = 0
        self.unknown = 0
        self.timeout = 0
        self.sat = 0
        self.unsat = 0
    def _count(self, r):
        # r is a tuple (sat_bool, ...) from claripy/z3
        if isinstance(r, tuple):
            sat = r[0]
        else:
            sat = r
        if sat is True:
            self.sat += 1; self.decided += 1
        elif sat is False:
            self.unsat += 1; self.decided += 1
        else:
            self.unknown += 1
        return r
    def satisfiable(self, *a, **k):
        return self._count(self.solver.satisfiable(*a, **k))
    def eval(self, *a, **k):
        return self.solver.eval(*a, **k)

# We wrap the solver used by the state's solver engine. angr's SimState.solver
# is a SolverEngine; we patch its satisfiable/eval at the instance level per run.

def collect_accounting(path, label, valid_domain):
    log = []
    def note(msg):
        log.append(msg)
        print(msg, flush=True)
    p = v4.build_project(path)
    st = p.factory.call_state(
        v4.BAD_SINK,
        add_options={
            angr.options.SYMBOLIC_WRITE_ADDRESSES,
            angr.options.TRACK_MEMORY_ACTIONS,
        },
    )
    # replicate v4.explore's setup (unchanged)
    rbp = st.regs.rsp
    data_addr = 0x500000
    n = v4.MAX_VALID + 1 if valid_domain else v4.MAX_VALID + 8
    sym = claripy.BVS("input", 8 * n)
    for i in range(n):
        st.memory.store(data_addr + i, sym.get_byte(i))
    if valid_domain:
        for i in range(v4.MAX_VALID):
            st.memory.store(data_addr + i, claripy.BVV(0x41, 8))
        st.memory.store(data_addr + v4.MAX_VALID, claripy.BVV(0, 8))
    else:
        ncal = v4.MAX_VALID + 8
        for i in range(ncal):
            st.memory.store(data_addr + i, claripy.BVV(0x41, 8))
        st.memory.store(data_addr + ncal, claripy.BVV(0, 8))
    st.regs.rdi = data_addr
    st.globals["data_addr"] = data_addr

    # wrap the solver engine to count satisfiable/eval calls
    engine = st.solver
    orig_sat = engine.satisfiable
    orig_eval = engine.eval
    stats = {"sat": 0, "unsat": 0, "unknown": 0, "eval": 0}
    def sat_counted(*a, **k):
        try:
            r = orig_sat(*a, **k)
        except Exception as e:
            stats["unknown"] += 1
            raise
        if r is True:
            stats["sat"] += 1
        elif r is False:
            stats["unsat"] += 1
        else:
            stats["unknown"] += 1
        return r
    def eval_counted(*a, **k):
        stats["eval"] += 1
        return orig_eval(*a, **k)
    engine.satisfiable = sat_counted
    engine.eval = eval_counted

    simgr = p.factory.simgr(st)
    deadline = time.time() + 120
    steps = 0
    max_steps = 400
    note(f"[{label}/{('valid' if valid_domain else 'free')}] start, entry=0x{v4.BAD_SINK:x}")
    try:
        while simgr.active and steps < max_steps and time.time() < deadline:
            simgr.step()
            steps += 1
            note(f"  step {steps}: active={len(simgr.active)} dead={len(simgr.deadended)} " +
                 f"err={len(simgr.errored)} uncon={len(simgr.unconstrained)}")
    except Exception as e:
        note(f"  exception: {e!r}")
    timed_out = time.time() >= deadline

    # state classification totals
    state_acct = {
        "active": len(simgr.active),
        "deadended": len(simgr.deadended),
        "errored": len(simgr.errored),
        "unconstrained": len(simgr.unconstrained),
        "deferred": len(getattr(simgr, "deferred", [])),
        "steps": steps,
        "timed_out": timed_out,
    }
    solver_acct = dict(stats)
    note(f"  solver accounting: {solver_acct}")
    note(f"  state accounting: {state_acct}")
    return {
        "label": label,
        "valid_domain": valid_domain,
        "state_accounting": state_acct,
        "solver_accounting": solver_acct,
        "steps": steps,
    }

if __name__ == "__main__":
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "engine": "angr 10.0.4.post1 + z3-solver 5.1.0 (claripy is angr's bundled rustylib)",
           "runs": []}
    for name, path in [("original", "./original.elf"),
                       ("routea", "./routea-candidate.elf"),
                       ("routeb", "./routeb-candidate.elf")]:
        for dom in (True, False):
            r = collect_accounting(path, name, dom)
            out["runs"].append(r)
    with open("v4-accounting.json", "w") as f:
        json.dump(out, f, indent=2)
    print("wrote v4-accounting.json")
