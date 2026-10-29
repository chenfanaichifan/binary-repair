# PR body — GUI section (for M1 to include; do not edit root README/MEMORY)

This branch adds the demo-pack deliverable on top of `member2/f5-export`:

- `start.sh` — Ubuntu 24.04 / Python 3.12 launcher (venv + uvicorn on
  127.0.0.1:8123), marked unverified until run on the target host.
- `docs/demo/README.md` — one-command setup, mock vs HTTP controller mode,
  setup -> compare -> evidence -> export journey, honest BLOCKED/Gate-4-NOT-RUN
  status.
- `docs/demo/01..05-*.png` — current-HEAD screenshots.
- `docs/demo/p0.log` — P0 acceptance 17/17.
- `docs/demo/e2e.log` — Edge journeys, 7/7 passed (32.14 s).

No changes to root `README.md`, `MEMORY.md`, controller, worker, acceptance,
fixtures or interface files.
