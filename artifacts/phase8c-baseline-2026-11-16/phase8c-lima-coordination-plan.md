# Phase-8C Lima serialization and guest coordination plan

Status: inventory + design. No global lock is implemented in C1.

## Inventory of guest/limactl call sites

| file | present | hit count | role |
|---|---|---|---|
| app/services/guest_runner.py | True | 29 | limactl probe/list/shell/run |
| app/services/poc_runner.py | True | 11 | select guest runner + staged run |
| scripts/run_hard_benchmark.py | True | 0 | benchmark reproductions |
| scripts/run_repair_benchmark.py | True | 0 | independent verification runs |
| scripts/release_gate.py | True | 14 | nightly real-Lima acceptance + identity probe |
| scripts/verify_repair_benchmark.py | True | 2 | verifier benchmark oracle evidence |
| scripts/verify_repair.py | True | 0 | verifier CLI oracle injection |
| app/services/independent_verifier.py | True | 0 | oracle evidence validation |

## Current status

- serialization: `not_implemented_no_global_lock`
- measured guest: {'available': True, 'kind': 'lima', 'tier': 'emulated_run', 'tool': '/opt/homebrew/bin/limactl', 'instance': 'binaryrepair'}
- no repository-wide advisory lock/lease exists; the guest is shared by poc_runner, release gate capture, benchmark runners and verifier oracle runs, so concurrent execution can interleave limactl calls.

## Design (C9)

- lock file: `$HOME/.binaryrepair/locks/lima-guest.lock`
- mechanism: fcntl.flock exclusive advisory lock with a JSON lease (run_id,pid,acquired_at,ttl_s,attempt,operation)
- reentrancy: per-run token passed through callers; nested guest calls reuse the lease instead of re-locking
- timeout/staleness: bounded acquire timeout + explicit attempt record; expiry/stale lease detection by pid+ttl
- evidence fields: ['run_id', 'operation', 'attempt', 'lock_wait_ms', 'lease_acquired', 'timeout', 'released']
- acquire => run => record attempt => release in a `finally` block; crash/stale lease detection via pid+ttl; bounded wait returns explicit `lock_timeout` not_run evidence, never a fake pass
- callers (poc_runner/release gate/benchmark runners/verifier) must pass a run token; nested calls reuse the lease instead of re-locking

## Tests

- existing: ['tests/test_guest_runner.py', 'tests/test_poc_runner.py', 'tests/test_verify_test_serial.py', 'tests/test_repair_benchmark_fixtures.py']
- add: acquire/release, timeout, reentrancy, stale-pid, concurrent serialization, evidence fields, no deadlock
- acceptance: serialized runs produce identical evidence and no overlapping limactl invocations
