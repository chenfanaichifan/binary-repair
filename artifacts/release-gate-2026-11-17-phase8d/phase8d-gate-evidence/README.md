# Release freeze evidence

- mode: `nightly`
- requested sha: `996060d0b47374e9ad69e4fee5a3de4a11d164c1`
- head sha: `996060d0b47374e9ad69e4fee5a3de4a11d164c1`
- clean tree: `True`
- expected mainline policy: `ignore`
- mainline at start: `None`
- mainline at end: `None`
- mainline unchanged: `True`
- gate rc: `0`
- gate ok: `True`
- runner kind: `local-frozen-tree`
- GitHub run: not applicable (local frozen-tree evidence)
- evidence scope: frozen-tree gate (not automatically a CI run)

## Command

```
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python scripts/release_gate.py --nightly --release-sha 996060d0b47374e9ad69e4fee5a3de4a11d164c1 --json --evidence-out artifacts/release-gate-2026-11-17-phase8d/gate.json
```

## Files

- `gate.json`: gate evidence with checks/provenance
- `freeze.json`: tree/mainline pins and the exact command
- `SHA256SUMS`: sha256 of the files above
