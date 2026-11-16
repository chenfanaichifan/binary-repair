# Release freeze evidence

- mode: `nightly`
- requested sha: `2bfa112591614aa39d4d6b55ad9bb962b9718e7c`
- head sha: `2bfa112591614aa39d4d6b55ad9bb962b9718e7c`
- clean tree: `True`
- expected mainline policy: `require`
- mainline at start: `2bfa112591614aa39d4d6b55ad9bb962b9718e7c`
- mainline at end: `2bfa112591614aa39d4d6b55ad9bb962b9718e7c`
- mainline unchanged: `True`
- gate rc: `0`
- gate ok: `True`
- runner kind: `local-frozen-tree`
- GitHub run: not applicable (local frozen-tree evidence)
- evidence scope: frozen-tree gate (not automatically a CI run)

## Command

```
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python scripts/release_gate.py --nightly --release-sha 2bfa112591614aa39d4d6b55ad9bb962b9718e7c --json --evidence-out artifacts/release-gate-2026-11-15-autonomy/gate.json
```

## Files

- `gate.json`: gate evidence with checks/provenance
- `freeze.json`: tree/mainline pins and the exact command
- `SHA256SUMS`: sha256 of the files above
