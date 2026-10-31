#!/usr/bin/env python3
"""Run the full V4 matrix and emit one structured evidence JSON."""
import json, sys, time
sys.path.insert(0, ".")
import importlib.util
spec = importlib.util.spec_from_file_location("v4_symbolic", "./v4_symbolic.py")
v4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v4)

BINARIES = {
    "original": {"path": "./original.elf",
                 "sha256": "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393"},
    "routea":   {"path": "./routea-candidate.elf",
                 "sha256": "c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82"},
    "routeb":   {"path": "./routeb-candidate.elf",
                 "sha256": "208574ab5b7753fab6f28860830069770622fb7b1fcb8d181fa50453f8656717"},
}

MODEL = {
    "function": "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink",
    "entry": "0x4012b0 (original); recompiled entry differs for Route B",
    "dest": "rbp-0x40 (dest[0]); dest_capacity_bytes=50 (includes NUL)",
    "data_arg": "rbp-0x48 / rdi at entry",
    "strcpy_plt": "0x4010d0 (hooked, length-aware model)",
    "printLine_plt": "0x401380 (hooked, returns)",
    "forbidden_write": "any write past dest[50] for inputs of length >= 50",
    "valid_domain": "C string 0..49 payload bytes + NUL (worst case 49+NUL)",
    "state_classification": ["active", "deadended(terminal)", "errored",
                              "unconstrained", "resource-pruned(timeout/steps)"],
    "library_hooks": ["strcpy@plt (length-aware)", "printLine@plt (stub)"],
    "calibration": {
        "original_violation": "original, arbitrary-length domain -> counterexample (overflow found)",
        "deliberately_defective": "the original binary IS the defective reference; "
                                   "its overflow is reproduced to prove the model can catch it",
    },
    "engine": "angr 10.0.4.post1 + z3-solver 5.1.0.0 (guest /opt/angr-venv)",
}

def main():
    out = {"model": MODEL, "runs": [], "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    for name, meta in BINARIES.items():
        for domain, dom_label in ((True, "valid"), (False, "free")):
            r = v4.explore(meta["path"], name, valid_domain=domain)
            r["binary"] = meta["path"]
            r["sha256"] = meta["sha256"]
            r["domain"] = dom_label
            out["runs"].append(r)
            print(f"[{name}/{dom_label}] verdict={r.get('verdict')} "
                  f"steps={r.get('steps')} oob={len(r.get('out_of_bounds_writes', []))}",
                  flush=True)
    with open("v4-evidence.json", "w") as f:
        json.dump(out, f, indent=2)
    print("wrote v4-evidence.json")

if __name__ == "__main__":
    main()
