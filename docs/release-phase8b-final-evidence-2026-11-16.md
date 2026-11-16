# Phase-8B final release evidence (2026-11-16)

This evidence addendum is committed on the evidence branch. It binds the
final gated release commit to the frozen-tree gate and the hosted CI runs.

- Final gated mainline SHA: `227f45b39d85a7cd95e8589beb07dcfc89cd22d7`
- Tree SHA recorded by the gate: `5a9b94cb7062cefa2a03350f5680a2cf9f094c43`
- Local frozen-tree nightly gate: 13 required checks passed, 0 failed,
  0 unavailable; the bundle is `artifacts/release-gate-2026-11-16-phase8b/`
  (`gate.json`, `freeze.json`, `README.md`, `SHA256SUMS`), with
  `mainline_unchanged=true`.
- Hosted CI run on the final SHA: 43718302033 (`CI`), conclusion success
  (https://github.com/chenfanaichifan/binary-repair/actions/runs/43718302033).
- Hosted Ubuntu verification on the final SHA: 43718302188, conclusion success
  (https://github.com/chenfanaichifan/binary-repair/actions/runs/43718302188).
- The claims file on the gated commit cites the earlier hosted CI run
  43703724955 at code SHA `c5d87b5`; that run is also genuine and successful.
  Both are recorded here rather than conflated.
- Self-hosted Lima nightly: not_run (no self-hosted runner provisioned); not
  claimed.
- Phase-8B verifier evidence remains
  `artifacts/phase8b-benchmark-2026-11-16/`: 12 samples executed, 2 candidates,
  2 independently verified (`stack-strcpy-x86_64`, `heap-capacity-x86_64`),
  false_verified=0, verification_disagreements=0, oracle executed through
  `limactl`/`emulated_run`. The other 10 samples produced no candidate and are
  analysis-only.

This addendum is evidence, not a new capability claim. No whole-image proof,
hidden-benchmark generalization, capability promotion or Phase-8C..16 completion
is claimed.
