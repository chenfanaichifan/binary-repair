#!/usr/bin/env python3
"""V4 producer for the CWE416 no-input fixture.

Property (the violation):
    There exists an execution of the target function on which the pointer passed
    to `free()` is later passed to `printLine()`, i.e. a freed block is read.

For a binary where the defect is absent, the harness must find **no** such
execution; for the unrepaired original it must find one. The second is the
negative control: without it a "no violation" result is vacuous.

Input domain: the contract says `input_mode: none` — the entry takes no
arguments, reads no stdin and opens no file. The only nondeterminism left is the
address `malloc()` returns, so the harness makes that symbolic and quantifies
over it. Nothing else is assumed.

Hooks are enumerated (`HOOKS`) and justified; none of them assumes the repaired
operation is safe. `printLine` is hooked *to observe its argument*, not to
approve it — the violation is decided by comparing that argument with the
pointers recorded at `free()`.

Every number in the output comes from this run. The file is written only through
`write_v4_evidence`, which re-checks the checklist and refuses to write otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import angr

# angr 10 lazy-imports claripy; it is reachable through the angr package.
claripy = angr.claripy

sys.path.insert(0, str(Path(__file__).resolve().parent))

from v4_evidence import (  # noqa: E402
    Replay,
    SolverAccounting,
    StateAccounting,
    V4Case,
    V4Evidence,
    write_v4_evidence,
)

MAX_STEPS = 64
QUERY_TIMEOUT_MS = 5000

HOOKS = [
    {
        "symbol": "malloc",
        "why": "makes the one remaining nondeterminism explicit: the returned address is a fresh "
               "symbolic 64-bit value, aligned and non-null. Modelling it concretely would remove "
               "the only reason this analysis quantifies over anything.",
    },
    {
        "symbol": "memset",
        "why": "recorded as a no-op. The property is about which pointer reaches printLine(), not "
               "about block contents, so writing 99 bytes at a symbolic address adds nothing but "
               "state-explosion risk.",
    },
    {
        "symbol": "free",
        "why": "records the pointer argument instead of modelling the allocator. Recording is what "
               "the property needs; a model of tcache would add assumptions without adding reach.",
    },
    {
        "symbol": "printLine",
        "why": "hooked to observe the argument. It never returns a verdict by itself; the comparison "
               "with the freed pointers happens in the harness, and the state is terminated after "
               "the observation. Hooking it also keeps its strlen() loop out of the exploration.",
    },
    {
        "symbol": "exit",
        "why": "the malloc-null guard calls exit(). Without a hook the path would jump to an "
               "unconstrained address and be counted as an unexplored state, which would make "
               "complete=True a lie.",
    },
]


class CountingSolver:
    """Counts the queries the harness itself issues.

    angr's internal queries (branch resolution, memory read resolution) are not
    instrumented — see not_claimed. What is counted here is every satisfiability
    question the harness asks about the property.
    """

    def __init__(self) -> None:
        self.acc = SolverAccounting()
        self.details: list[dict[str, str]] = []

    def ask(self, state, constraints, label: str) -> str:
        started = time.monotonic()
        self.acc.eval += 1
        try:
            answer = state.solver.satisfiable(extra_constraints=list(constraints))
        except Exception as exc:  # noqa: BLE001 - a crashing query is not a pass
            self.acc.unknown += 1
            self.details.append({"query": label, "result": "unknown", "detail": repr(exc)})
            return "unknown"
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if elapsed_ms > QUERY_TIMEOUT_MS:
            self.acc.timeouts += 1
            self.acc.unknown += 1
            self.details.append({"query": label, "result": "unknown"})
            return "unknown"
        if answer:
            self.acc.sat += 1
            self.details.append({"query": label, "result": "sat"})
            return "sat"
        self.acc.unsat += 1
        self.details.append({"query": label, "result": "unsat"})
        return "unsat"


def _symbol(project: angr.Project, name: str) -> int:
    sym = project.loader.find_symbol(name)
    if sym is None:
        raise SystemExit(f"symbol not found in binary: {name}")
    return sym.rebased_addr


class Harness:
    def __init__(self, binary: Path, entry_name: str) -> None:
        self.binary = binary
        self.entry_name = entry_name
        self.project = angr.Project(str(binary), auto_load_libs=False)
        self.entry = _symbol(self.project, entry_name)
        self.freed_global = "freed_pointers"

    # -- hooks -------------------------------------------------------------
    def _install(self) -> None:
        harness = self

        class HookMalloc(angr.SimProcedure):
            def run(self, size):
                addr = claripy.BVS("heap_base", 64)
                self.state.solver.add(addr != 0)
                self.state.solver.add(addr % 16 == 0)
                self.state.solver.add(addr >= 0x10000)
                self.state.solver.add(addr < 0x7FFF_0000_0000)
                return addr

        class HookMemset(angr.SimProcedure):
            def run(self, dest, value, n):
                return dest

        class HookFree(angr.SimProcedure):
            def run(self, ptr):
                harness._record_free(self.state, ptr)
                return 0

        class HookPrintLine(angr.SimProcedure):
            def run(self, text):
                harness._observe_print(self.state, text)
                return 0

        class HookExit(angr.SimProcedure):
            def run(self, code):
                self.exit(0)

        for name, impl in (
            ("malloc", HookMalloc),
            ("memset", HookMemset),
            ("free", HookFree),
            ("printLine", HookPrintLine),
            ("exit", HookExit),
        ):
            addr = self.project.loader.find_symbol(name)
            if addr is None:
                raise SystemExit(f"cannot hook {name}: symbol missing")
            # replace=True: angr already has simprocedures on the PLT entries, and
            # the point of this harness is to observe those calls, not to run them.
            self.project.hook(addr.rebased_addr, impl(), replace=True)

    # -- observation -------------------------------------------------------
    @staticmethod
    def _record_free(state, ptr) -> None:
        # SimStateGlobals is mapping-like but has no setdefault; keep the list
        # object in the mapping so later appends are visible to the next hook.
        freed = state.globals.get("freed_pointers")
        if freed is None:
            freed = []
            state.globals["freed_pointers"] = freed
        freed.append(ptr)
        state.globals["free_calls"] = (state.globals.get("free_calls") or 0) + 1

    def _observe_print(self, state, text) -> None:
        """Ask the property question at every printLine call.

        The question is exactly "is this argument equal to a pointer freed
        earlier on this path?". With no free() on the path the disjunction is
        empty and the honest answer is unsat, so the question is still asked
        rather than skipped — skipping would leave the repaired case with no
        solver answer at all and make `unsat` a claim about nothing.
        """
        freed = state.globals.get("freed_pointers") or []
        state.globals["print_calls"] = (state.globals.get("print_calls") or 0) + 1
        if freed:
            claims = [text == ptr for ptr in freed]
            constraint = claims[0] if len(claims) == 1 else claripy.Or(*claims)
            label = f"printline_arg in freed[{len(freed)}]"
        else:
            constraint = claripy.false()
            label = "printline_arg in freed[0] (none freed on this path)"
        answer = self.solver.ask(state, [constraint], label)
        if answer == "sat":
            state.globals["violation"] = {
                "freed_index": 0,
                "print_calls_seen": state.globals.get("print_calls"),
                "solver": "sat",
            }
        elif answer == "unknown":
            state.globals["unknown_observation"] = label

    # -- one analysis ------------------------------------------------------
    def analyse(self, label: str) -> tuple[V4Case, dict]:
        self.solver = CountingSolver()
        self._install()

        state = self.project.factory.call_state(
            self.entry,
            add_options={
                angr.options.ZERO_FILL_UNCONSTRAINED_MEMORY,
                angr.options.ZERO_FILL_UNCONSTRAINED_REGISTERS,
            },
        )
        state.globals["freed_pointers"] = []
        state.globals["print_calls"] = 0

        simgr = self.project.factory.simgr(state)
        steps = 0
        while simgr.stashes.get("active") and steps < MAX_STEPS:
            simgr.step()
            steps += 1

        def stash(name: str) -> list:
            # a stash that was never created simply has no states
            return list(simgr.stashes.get(name, []))

        counts = StateAccounting(
            initial=1,
            deadended=len(stash("deadended")),
            errored=len(stash("errored")),
            unconstrained=len(stash("unconstrained")),
            deferred=len(stash("deferred")),
            active=len(stash("active")),
            pruned=len(stash("pruned")),
        )

        violation = None
        unknown_observation = None
        for st in stash("deadended"):
            v = st.globals.get("violation")
            if v and violation is None:
                violation = dict(v, state="deadended")
            if st.globals.get("unknown_observation"):
                unknown_observation = st.globals.get("unknown_observation")

        plain_witness = None
        if violation is None:
            # No violation found: record what was actually observed, so the
            # "holds" is not a bare word. free_calls == 0 is the whole reason.
            for st in stash("deadended"):
                plain_witness = {
                    "free_calls": st.globals.get("free_calls") or 0,
                    "print_calls": st.globals.get("print_calls") or 0,
                    "solver": "unsat",
                }
                break

        if violation:
            observed = "violated"
        elif unknown_observation or counts.errored or counts.active:
            observed = "unknown"
        else:
            observed = "holds"
        expected = "violated" if label == "known_bad" else "holds"

        case = V4Case(
            id="known_bad" if label == "known_bad" else "known_good",
            kind="known_bad" if label == "known_bad" else "known_good",
            binary_sha256=hashlib.sha256(self.binary.read_bytes()).hexdigest(),
            expected=expected,
            observed=observed,
            property_text="a pointer passed to free() is later passed to printLine()",
            steps=steps,
            max_steps=MAX_STEPS,
            states=counts,
            solver=self.solver.acc,
            witness=violation or plain_witness,
            notes=(
                ["unsat comes from an empty disjunction: no free() occurs on this path, "
                 "so the question is unsatisfiable rather than decided by a constraint"]
                if label != "known_bad" else
                ["sat witness: the same symbolic pointer reaches free() and printLine()"]
            ),
        )
        extra = {"queries": self.solver.details, "states": counts}
        return case, extra


def digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="produce V4 evidence for the CWE416 no-input fixture")
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--replay-runs", type=int, default=2)
    args = ap.parse_args(argv)

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    entry_name = contract["target_entry"]
    entry_addrs = {
        p.name: _symbol(angr.Project(str(p), auto_load_libs=False), entry_name)
        for p in (args.candidate, args.original)
    }
    if len(set(entry_addrs.values())) != 1:
        raise SystemExit(f"entry address differs between the two binaries: {entry_addrs}")
    contract_sha = hashlib.sha256(args.contract.read_bytes()).hexdigest()

    runs: list[dict] = []
    cases: list[V4Case] = []
    solver_total = SolverAccounting()
    steps_total = 0

    for run_index in range(args.replay_runs):
        good = Harness(args.candidate, entry_name)
        good_case, good_extra = good.analyse("known_good")
        bad = Harness(args.original, entry_name)
        bad_case, bad_extra = bad.analyse("known_bad")

        run_payload = {
            "known_good": {**asdict(good_case), "queries": good_extra["queries"]},
            "known_bad": {**asdict(bad_case), "queries": bad_extra["queries"]},
        }
        runs.append({"digest": digest(run_payload), "cases": [good_case, bad_case]})
        if run_index == 0:
            cases = [good_case, bad_case]
            for c in cases:
                solver_total.add(c.solver)
                steps_total += c.steps

    states_total = StateAccounting()
    for c in cases:
        states_total.initial += c.states.initial
        states_total.deadended += c.states.deadended
        states_total.errored += c.states.errored
        states_total.unconstrained += c.states.unconstrained
        states_total.deferred += c.states.deferred
        states_total.active += c.states.active
        states_total.pruned += c.states.pruned

    unexplored: list[str] = []
    if states_total.active:
        unexplored.append(f"active={states_total.active}")
    if states_total.deferred:
        unexplored.append(f"deferred={states_total.deferred}")
    if states_total.unconstrained:
        unexplored.append(f"unconstrained={states_total.unconstrained}")

    evidence = V4Evidence(
        gate="V4",
        candidate_sha256=hashlib.sha256(args.candidate.read_bytes()).hexdigest(),
        original_sha256=hashlib.sha256(args.original.read_bytes()).hexdigest(),
        contract_sha256=contract_sha,
        target_entry=entry_name,
        entry_address=hex(next(iter(entry_addrs.values()))),
        property_text="on every execution, no pointer passed to free() is later passed to printLine()",
        input_domain="none: the entry takes no arguments, reads no stdin, opens no file; only the "
                     "address returned by malloc() is symbolic",
        hooks=HOOKS,
        cases=cases,
        claimed_scope="model",
        not_claimed=[
            "a binary-level proof: this is a model-level result over the target function only",
            "memory safety anywhere outside the target function",
            "absence of the defect under a different allocator or a different libc",
            "equivalence with the C source: the model reads the ELF, not the source",
            "solver queries issued inside angr (branch and memory resolution) are not counted",
            "a deep proof on the repaired side: its unsat is the empty-disjunction case — no free() "
            "occurs on the path — not a constraint that was solved",
        ],
        complete=not unexplored,
        unexplored=unexplored,
        unknown=solver_total.unknown,
        timeouts=solver_total.timeouts,
        steps=steps_total,
        max_steps=MAX_STEPS * len(cases),
        solver=solver_total,
        states=states_total,
        replay=Replay(runs=args.replay_runs, digests=[r["digest"] for r in runs]),
        engine={
            "angr": angr.__version__,
            "claripy": getattr(claripy, "__version__", "bundled with angr"),
            "python": sys.version.split()[0],
        },
    )

    path = write_v4_evidence(args.out, evidence)
    print(json.dumps(evidence.payload(), indent=2, sort_keys=True))
    print(f"\nwritten: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
