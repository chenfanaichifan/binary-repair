# Release freeze evidence

- mode: `nightly`
- requested sha: `3ec09b14435c5b2b67c2198d7e81dafa9cb35be2`
- head sha: `3ec09b14435c5b2b67c2198d7e81dafa9cb35be2`
- clean tree: `True`
- expected mainline policy: `require`
- mainline at start: `3ec09b14435c5b2b67c2198d7e81dafa9cb35be2`
- mainline at end: `3ec09b14435c5b2b67c2198d7e81dafa9cb35be2`
- mainline unchanged: `True`
- gate rc: `0`
- gate ok: `True`
- runner kind: `local-frozen-tree`
- GitHub run: not applicable (local frozen-tree evidence)
- evidence scope: frozen-tree gate (not automatically a CI run)

## Command

```
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python scripts/release_gate.py --nightly --release-sha 3ec09b14435c5b2b67c2198d7e81dafa9cb35be2 --json --evidence-out artifacts/release-gate-2026-11-16-phase8a/gate.json
```

## Files

- `gate.json`: gate evidence with checks/provenance
- `freeze.json`: tree/mainline pins and the exact command
- `SHA256SUMS`: sha256 of the files above
