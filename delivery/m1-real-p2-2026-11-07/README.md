# M1 real P2 run (2026-11-07)

- job: `eddaaf359af048fd92cdb3c5262c495d`
- run: `4672e45e4e114b88af9a922ee9342e84`
- route A: `ade2e48082f540f8bf5c91d6a930d383`
- route B: `7282288875e14aa8bf5c564366156b69`

Route A input is the real P3A package mapped to the generic schema; Route B is
the real P3B static bundle copied to the attempt's canonical `.routeb` path.
The host worker only invoked the Python adapter; no ELF was executed.

`p2_acceptance.py` exited 0 with `synthetic=false`; the job is `finished` and
the verdict is `inconclusive / required_check_not_run / interface`. No gate was
promoted.
