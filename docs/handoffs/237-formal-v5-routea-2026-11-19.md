# 237 — Formal V5 clean-snapshot replay, Route A (2026-11-19 specification)

- Date: 2026-11-19
- Owner: Lead
- Status: **formal V5 for one Route A final candidate is measured, independently
  reviewed and accepted in the product path; run-level/two-route success is not
  claimed (only Route A ran).**
- Branch: `p0/routea-trust-boundary-2026-11-13` (local, not pushed before this
  record; commit `2fd6a61` carries the V5 schema + host acceptance + assembler)
- Supersedes the "formal V5 remains `not_run`" limitation stated in record 236
  §4 for the Route A candidate. Everything else in record 236 stands.

## 1. Approved clean snapshot and restore receipt

No snapshot had been formally designated "approved clean snapshot" before this
run. The Lead designates `p1-prewindow-20261107` (snapshot uid 15, file
`D:\VMs\binrepair-u2404-x64-01\BinRepair-Lab-Snapshot15.vmsn`) as the approved
clean snapshot for this replay, because it is the recorded pre-window baseline
that contains the executor installation; the team should ratify this choice.

Host-captured receipt (`.tmp/guest-window-2026-11-19/v5-formal/restore-receipt.json`,
sha256 `9154caf7d88fa8caf04d0b98f2911bcc17a1f7b89154e05fdda7bf4fb2989438`):

```text
vmrun -T ws stop <vmx> soft                 rc 0   (vm list after: 0 running)
vmrun -T ws revertToSnapshot <vmx> p1-prewindow-20261107  rc 0
vmrun -T ws start <vmx> nogui               rc 0
snapshot_name  p1-prewindow-20261107
snapshot_uid   15
snapshot_file_sha256 80219366a3f3b8eca10a7d089d2f14827218494ebbe11bccc4d75677db38cc64
power_state_before poweredOn -> power_state_after_revert poweredOff
restore_started_at 2026-11-19T11:36:34Z
restore_finished_at 2026-11-19T11:36:57Z
booted_at 2026-11-19T11:37:54Z
boot_id 4b4a9fd9-3324-4f18-bbb2-9c0f8678331f   (pre-restore boot was 2504a5a5-…, so the restore is visible)
```

The reviewer independently recomputed the vmsn sha256 from the real file and
cross-checked `BinRepair-Lab.vmsd` (`snapshot10.uid=15`,
`displayName=p1-prewindow-20261107`, `snapshot.current=15`).

## 2. Clean-state verification in the restored guest

Measured after boot (`clean-state-measured.txt`), and matching
`snapshot-state.json`:

```text
hostname binrepair-vm · Ubuntu 24.04.5 LTS · kernel 6.8.0-147-generic · python 3.12.3
boot_id 4b4a9fd9-3324-4f18-bbb2-9c0f8678331f
85be8aef…2f60  /usr/local/sbin/jobwrap-executor
1176b03a…e9a72 /opt/binrepair/executor-repo/workers/executor/run_job.py
5e14234a…c5c5  /opt/binrepair/executor-repo/workers/route_a/worker.py
4aa85d09…00c5  /opt/binrepair/executor-repo/workers/route_a/result_bundle.py
15915823…2b94  /opt/binrepair/executor-repo/routeb/executor.py
workers/route_a/run_candidate.py: absent (2026-11-07 snapshot state)
```

No host code was staged into the snapshot: the executor state is the snapshot's
own installation.

## 3. Behaviour rerun through the existing broker

The frozen Route A final ELF (`2a96b108…970e`) was carried by a fixed-mode
Route B harness package (the clean snapshot's broker only exposes Route B
execution; this is a behaviour replay, not a Route B repair). The candidate hash
proves identity. Approved inputs: original `c9c2632e…23c9`, tests/valid.json
`33be1edf…80b08`, canonical contract `c1684f15…4f7c`, package SHA256SUMS
`660145a6…1087`. The package verified with the snapshot's own
`verify_package` (5 files).

Invoked as `lab` through the fixed `/usr/local/sbin/jobwrap-executor executor`
mode; wrapper rc 0; bundle SHA256SUMS `97fbc7534a8d68b6fe7c1c4402133d8f75b07d7890b065b1bbf457efd8021158`;
generated after the 11:37:54Z restore boot.

```text
gates  V0 passed, V1 passed, V3 passed, V2/V4/V5 not_run by broker design
manifest-repaired.json:
  binary_sha256 2a96b108…970e
  case valid-no-input ok=true
  expected rc 0, stdout 99×"A"+LF, stderr empty
  observed rc 0, stdout_sha256 028411ec…f043, stderr empty, valid 1/1, repaired_pass true
isolation: uid/expected_uid 1003, CapEff 0000000000000000, NoNewPrivs 1,
           seccomp 2, netns 4026532219, root-owned jobwrap attestation 2306
```

First attempt (kept as `attempt-1-failed/`) failed at candidate execution
because the ELFs were staged 0644; the fix was `chmod 0755` on the staged
original/candidate. The failed attempt is preserved and this record does not
pretend it did not happen.

## 4. Independent build replay (separate evidence)

The fresh-context `verifier` agent replayed `patch_routea.py`
(sha256 `f5d9ba04…bcb9`) twice in the guest *before* the clean restore
(boot `2504a5a5…`): both outputs equal the frozen candidate, byte-identical
(`replay.json` sha256 `93180f8b…0ea6`). This env is the cross-run
reproducibility envelope; the clean-snapshot rerun is the broker bundle above.
The reviewer flagged this provenance split as a deviation, not a failure.

## 5. Typed formal V5 record

`app/domain/v5.py` (commit `2fd6a61`) is the single schema; `tools/assemble_v5_evidence.py`
assembles it from measured inputs only, and `app/domain/route_a_evidence.py::_check_v5`
validates `evidence/v5/formal-v5.json` first (including per-case comparison
against the approved manifest) and only then falls back to the pre-spec
replay envelope.

```text
formal-v5.json sha256 6a6f966699ce9b9c62fa604ca4b421c42a14629540e85078396655780f8dcd35
candidate 2a96b108…970e · original c9c2632e…23c9 · contract canonical c1684f15…4f7c
test_manifest_sha256 56d8d0d471a8330e9253b966bb128a9c02088140984a0a1a45f7fa98dcac5c80
restore receipt pins as above · 1/1 approved case matched · isolation attested
reviewed_by ai-agent:reviewer-2026-11-19 · independent true · result pass
```

## 6. Independent review

A fresh-context `reviewer` agent reviewed the exported evidence package without
SSH access and without executing anything on the host. Verdict: **PASS**;
`review.json` sha256 `a10f36e9d1ef7b5975652eda3fb2775dec47c3d2173eaddb1e10ca2a3c6508bf`.
It independently verified REVIEW-SHA256SUMS 32/32, broker-bundle SHA256SUMS
19/19 plus the circular `bundle-sha256.txt = sha256(SHA256SUMS)` chain, the
per-case expected/observed bytes, isolation fields, replay envelope, identity
pins and the restore receipt/vmsd.

Reviewer deviations, all recorded and none a required-check failure:

1. the build-replay envelope was measured in the pre-restore boot (provenance
   split described in §4);
2. the current `.vmx` sha256 differs from the receipt's pre-power `.vmx` hash
   (VMware rewrites `.vmx` during power operations; no approved pin exists);
3. `clean-state-measured.txt`/`environment.json` are host-assembled summaries of
   the SSH inventory; the raw SSH capture was not exported into the review
   package;
4. `environment.replay_package_sha256sums` is the sha256 of the frozen guest
   package manifest, which is not inside the review package;
5. the broker bundle's own V5 gate is `not_run` by executor design;
6. the broker bundle is a Route B fixed-mode harness carrying the frozen Route A
   ELF (candidate hash proves identity).

## 7. Product acceptance result

Scratch data dir (`.tmp/guest-window-2026-11-19/host-data`), product path
worker -> `attempt_driver` -> `attempt_writer --routea-bundle`; the canonical
bundle carried the fresh V4 marker (`3feb68a2…`) and `evidence/v5/formal-v5.json`:

```text
attempt attempt-p1-routea-rerun2-20261119  outcome success_within_scope
V0 passed · V1 passed · V2 passed (host recomputed 5/5) · V3 passed (guest_observed)
V4 passed (typed marker, model scope) · V5 passed
   V5 detail: host_verified: clean-snapshot restore receipt and per-case replay
   on the frozen candidate; every approved case matched its expectation
run: screening / waiting for both routes — Route B did not run, so no run-level
     or overall success is claimed.
```

## 8. Conformance to the 2026-11-19 V5 specification

| Requirement | Result |
|---|---|
| restore each route's VM from an approved clean snapshot before the rerun | done (receipt §1); snapshot approval is a Lead designation the team should ratify |
| verify SHA-256 of the frozen final ELF and approved test manifest | done (§2/§3; reviewer recomputed) |
| run the ELF through the existing broker | done via the snapshot's fixed `jobwrap-executor` mode (§3) |
| record snapshot restore receipt, candidate/manifest hashes, environment/tool versions | done in the typed record (§5) |
| per-case expected vs observed results | done (1/1, §3) |
| independent review of the record | done (fresh-context reviewer, PASS §6) |
| `passed` only if restore confirmed, both hashes match, every case meets expectations | satisfied for Route A |

Limitations: Route B V5 was not run in this re-run; the replay-envelope evidence
was produced pre-restore; M4 = Lead same operator; the restored guest was left
running with the V5 replay job dirs under `/var/lib/binrepair/jobs/` and `/tmp`
(the approved snapshot itself is unchanged).

## 9. Evidence locations

```text
.tmp/guest-window-2026-11-19/v5-formal/restore-receipt.json      sha256 9154caf7…
.tmp/guest-window-2026-11-19/v5-formal/formal-v5.json           sha256 6a6f9666…
.tmp/guest-window-2026-11-19/v5-formal/review-final.json        sha256 a10f36e9…
.tmp/guest-window-2026-11-19/v5-formal/v5-formal-out2/          broker bundle (SHA256SUMS 97fbc753…)
.tmp/guest-window-2026-11-19/v5-formal/attempt-1-failed/        preserved failed first attempt
.tmp/guest-window-2026-11-19/v5-formal/review-input/            independent review package
.tmp/guest-window-2026-11-19/v5-formal/package/                 replay package (SHA256SUMS 660145a6…)
.tmp/guest-window-2026-11-19/v5-replay/                         independent build replay (93180f8b…)
.tmp/guest-window-2026-11-19/host-data/                         scratch product attempt (success_within_scope)
```

## 10. Rollback

- Code: commits are local to `p0/routea-trust-boundary-2026-11-13`; nothing was
  merged or pushed before this record.
- Guest: the approved snapshot is unchanged; the VM is currently booted from it
  and can be reverted again with the same receipt procedure. V5 replay job dirs
  are disposable.
