# Release freeze evidence

- mode: `nightly`
- requested sha: `4a7b2355ffc5225d013a777bc7d588abac58f944`
- head sha: `4a7b2355ffc5225d013a777bc7d588abac58f944`
- clean tree: `True`
- expected mainline policy: `record`
- mainline at start: `4a7b2355ffc5225d013a777bc7d588abac58f944`
- mainline at end: `4a7b2355ffc5225d013a777bc7d588abac58f944`
- mainline unchanged: `True`
- gate rc: `0`
- gate ok: `True`
- runner kind: `local-frozen-tree`
- GitHub run: not applicable (local frozen-tree evidence)
- evidence scope: frozen-tree gate (not automatically a CI run)

## Command

```
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python scripts/release_gate.py --nightly --release-sha 4a7b2355ffc5225d013a777bc7d588abac58f944 --json --evidence-out artifacts/release-gate-2026-11-16-phase8c/gate.json
```

## Files

- `gate.json`: gate evidence with checks/provenance
- `freeze.json`: tree/mainline pins and the exact command
- `SHA256SUMS`: sha256 of the files above
