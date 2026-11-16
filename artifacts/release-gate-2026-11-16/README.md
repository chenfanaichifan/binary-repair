# Release freeze evidence

- mode: `nightly`
- requested sha: `a8934fefe918b95069b89b42399095dd28bf8710`
- head sha: `a8934fefe918b95069b89b42399095dd28bf8710`
- clean tree: `True`
- expected mainline policy: `require`
- mainline at start: `a8934fefe918b95069b89b42399095dd28bf8710`
- mainline at end: `a8934fefe918b95069b89b42399095dd28bf8710`
- mainline unchanged: `True`
- gate rc: `0`
- gate ok: `True`
- runner kind: `local-frozen-tree`
- GitHub run: not applicable (local frozen-tree evidence)
- evidence scope: frozen-tree gate (not automatically a CI run)

## Command

```
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python scripts/release_gate.py --nightly --release-sha a8934fefe918b95069b89b42399095dd28bf8710 --json --evidence-out artifacts/release-gate-2026-11-16/gate.json
```

## Files

- `gate.json`: gate evidence with checks/provenance
- `freeze.json`: tree/mainline pins and the exact command
- `SHA256SUMS`: sha256 of the files above
