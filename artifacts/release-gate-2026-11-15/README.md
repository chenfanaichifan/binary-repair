# Release freeze evidence

- mode: `nightly`
- requested sha: `fd6ca411f7cac0bab96b54e2306cec2134b839a8`
- head sha: `fd6ca411f7cac0bab96b54e2306cec2134b839a8`
- clean tree: `True`
- expected mainline policy: `require`
- mainline at start: `fd6ca411f7cac0bab96b54e2306cec2134b839a8`
- mainline at end: `fd6ca411f7cac0bab96b54e2306cec2134b839a8`
- mainline unchanged: `True`
- gate rc: `0`
- gate ok: `True`
- evidence scope: local frozen-tree gate (not a CI run)

## Command

```
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python scripts/release_gate.py --nightly --release-sha fd6ca411f7cac0bab96b54e2306cec2134b839a8 --json --evidence-out artifacts/release-gate-2026-11-15/gate.json
```

## Files

- `gate.json`: gate evidence with checks/provenance
- `freeze.json`: tree/mainline pins and the exact command
- `SHA256SUMS`: sha256 of the files above
