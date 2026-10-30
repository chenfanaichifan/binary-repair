# P2-real — end to end acceptance on the real fixture (2026-10-30)

Two controller jobs were created through the HTTP API from the frozen fixture
`CWE121_src_char_declare_cpy_51b/original.elf`
(`aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`),
approved, started, consumed by `app.services.worker`, and checked with
`tools/p2_acceptance.py`. Both runs exited 0, which means the snapshot was
complete and internally consistent — not that the repair succeeded.

| job | id | verdict | failing obligation |
|---|---|---|---|
| job1 | e2fe0f46350648a284c785254c30ee67 | inconclusive / required_check_not_run | route_a V2 interface: not_run |
| job2 | 8b0f2856086c4fe69117374e09d376bf | rejected / regression_failed | route_b V2 interface: failed |

job1 carries only the obligation values that already existed in P3A v6 / P3B v5.
job2 differs from job1 in exactly two cells: V2 and V5 now carry measured
evidence from this window. Nothing else was changed between the two runs, so the
delta between the two verdicts is attributable to the V2/V5 evidence.

## What V2 measured

`probes/v2_interface.py` ran inside the guest against real bytes and compared
each candidate with the shared original across 16 checks: ELF class, machine,
type, OS/ABI, entry, PT_INTERP, DT_NEEDED set, exported dynamic symbols,
preservation of the original PT_LOAD bases, count and permissions of added
PT_LOAD segments, absence of W+X, GNU_STACK, relocation type subset, actual
execution, and stdout equality with the original on the valid path.

* Route A (`c4a159…aa82`): 16/16 — passed.
* Route B (`63fcafa6…6d01`): 15/16 — **failed** on
  `extra_load_segments_within_contract`: the candidate adds 2 PT_LOAD segments
  (`0x4058a8` R-E, `0x407000` R) while `contract.json` `authorized_edits[2]`
  allows at most one new R-X PT_LOAD and only as the fallback when the R-X tail
  extension is rejected. Raw `readelf` output for all three binaries is under
  `readelf/`.

This is a measurement, not an adjudication. If the reviewers read
`authorized_edits[2]` differently, the check name and the raw dumps are here to
be re-judged; nothing else in the package depends on that reading.

## What V5 measured

* Route A: `regen_c4a159.py` was re-run twice in the guest from the frozen
  original; both outputs are byte identical to the shipped candidate
  `c4a159…aa82`.
* Route B: the shipped bytes were re-hashed against the two hashes recorded by
  the Route B executor's own reproducibility run. The Route B executor was **not**
  executed again in this window, and `v5-reproducibility.json` says so in its
  `limitation` field. This is a re-verification of a record, not a third run.

## Test suite at the same pinned head

`suite/host-suite-no-e2e.txt` — `pytest --ignore=tests/e2e` on the Windows host:
257 tests, 254 passed, 1 failed, 2 skipped, exit 1. The single failure is
`tests/test_routeb_executor.py::test_static_routeb_bundle` (`assert 7 >= 8`):
the bundle writes five `independent-views/` files only when `readelf` and
`objdump` exist, and this host has neither.

`suite/guest-routeb-executor.txt` — the same test file, copied to the guest
which does have binutils: 2 passed. So the failure is a host-tooling gap, not a
product regression, and the fix belongs to whoever owns that assertion (run the
suite where binutils exist, or gate the `>= 8` assertion on tool availability).

`suite/host-e2e-attempt.txt` — `pytest tests/e2e` on this host: exit 124 after a
90 s timeout with no output. Edge is installed and found by `cdp.find_edge()`,
the proxy variables were cleared, and the single journey still never returned.
The browser suite is therefore **unverified** here, not skipped and not passed.

## What is still not measured

V4 (bounded symbolic) is `not_run` for both routes, so neither route can reach
`success_within_scope` and job2's verdict is genuinely `rejected`, not a pass
that was withheld. No `gate4_pass` is claimed by this package.

Environment: Windows host, controller `app.controller_api` on 127.0.0.1:8000,
data dir `p2-real-2026-10-30/var/controller`; guest `binrepair-vm`,
Ubuntu 24.04.5, kernel 6.8.0-147-generic, binutils 2.42, snapshot uid 11
(`gate4-harness`).
