# Release freeze evidence

- mode: `nightly`
- requested sha: `d37bfad81f39c2bfa3fc90babed7301d6244446d`
- head sha: `d37bfad81f39c2bfa3fc90babed7301d6244446d`
- clean tree: `True`
- expected mainline policy: `require`
- mainline at start: `d37bfad81f39c2bfa3fc90babed7301d6244446d`
- mainline at end: `d37bfad81f39c2bfa3fc90babed7301d6244446d`
- mainline unchanged: `True`
- gate rc: `0`
- gate ok: `True`
- runner kind: `local-frozen-tree`
- GitHub run: not applicable (local frozen-tree evidence)
- evidence scope: frozen-tree gate (not automatically a CI run)

## Command

```
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python scripts/release_gate.py --nightly --release-sha d37bfad81f39c2bfa3fc90babed7301d6244446d --json --evidence-out artifacts/release-gate-2026-11-17-phase8d-final/gate.json
```

## Files

- `gate.json`: gate evidence with checks/provenance
- `freeze.json`: tree/mainline pins and the exact command
- `SHA256SUMS`: sha256 of the files above
