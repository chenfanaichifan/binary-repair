#!/usr/bin/env bash
# Read-only evidence reproduction for stack-strcpy-x86_64.
# Writes nothing to the repository and executes no untrusted binary.
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' disagreement-stack-strcpy-x86_64/original.elf
python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' disagreement-stack-strcpy-x86_64/candidate.bin

# Re-run the deterministic engine and print the measured facts (no repository writes).
.venv/bin/python scripts/audit_phase8b_verifier_semantics.py --reproduce stack-strcpy-x86_64 --json

# Reproduce the current verifier CLI report on the saved evidence.
# (Exit 1 is expected: the baseline is a recorded disagreement.)
set +e
.venv/bin/python scripts/verify_repair.py --original disagreement-stack-strcpy-x86_64/original.elf --candidate disagreement-stack-strcpy-x86_64/candidate.bin --metadata disagreement-stack-strcpy-x86_64/metadata.json --poc fixtures/poc/elf-x86_64-strcpy.json --json
