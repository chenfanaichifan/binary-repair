# Release freeze evidence

- mode: `nightly`
- requested sha: `cdeab74b6a6f012ed7f46f0db8d918ff5648c8ae`
- head sha: `cdeab74b6a6f012ed7f46f0db8d918ff5648c8ae`
- clean tree: `True`
- expected mainline policy: `require`
- mainline at start: `cdeab74b6a6f012ed7f46f0db8d918ff5648c8ae`
- mainline at end: `f2392fd9c0f9cf5a83ae7b04a09e2ec0695c073a`
- mainline unchanged: `False`
- gate rc: `0`
- gate ok: `True`
- evidence scope: local frozen-tree gate (not a CI run)

## Command

```
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python scripts/release_gate.py --nightly --release-sha cdeab74b6a6f012ed7f46f0db8d918ff5648c8ae --json --evidence-out artifacts/release-gate-2026-11-14/gate.json
```

## Files

- `gate.json`: gate evidence with checks/provenance
- `freeze.json`: tree/mainline pins and the exact command
- `SHA256SUMS`: sha256 of the files above
