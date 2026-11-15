#!/usr/bin/env python3
"""Run the same RepairSpec/ABI benchmark for multiple provider:model pairs.

All models use the same case manifest, repair budget and acceptance gate.  The
script records typed failures and never turns an unavailable provider into a
success.  Reference fixes are not used here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError(f"expected provider:model, got {spec!r}")
    provider, model = spec.split(":", 1)
    return provider.strip(), model.strip()


def _run_model(spec: str, args: argparse.Namespace) -> dict:
    provider, model = _parse(spec)
    slug = (provider + '-' + model).replace('/', '_').replace(':', '_')
    out = args.out / slug
    env = dict(os.environ)
    env['BINARYREPAIR_PROVIDER'] = provider
    env['BINARYREPAIR_ASSISTANT_MODEL'] = model
    env['BINARYREPAIR_STRICT_MODEL_IDENTITY'] = '1'
    cmd = [
        sys.executable, str(ROOT / 'scripts' / 'run_hard_benchmark.py'),
        '--out', str(out), '--cases', str(args.cases), '--client', 'real',
        '--allow-calls', '--repair-plan', '--abi-strict', '--semantic-retry',
        '--max-repair-rounds', str(args.max_repair_rounds),
        '--repeats', str(args.repeats),
    ]
    if args.case:
        cmd += ['--case', args.case]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                          text=True, timeout=args.timeout)
    record: dict = {
        'spec': spec, 'provider': provider, 'model_requested': model,
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout[-1500:],
        'stderr_tail': proc.stderr[-1500:],
        'summary_path': str(out / 'summary.json'),
        'manifest_path': str(out / 'run-manifest.json'),
    }
    try:
        summary = json.loads((out / 'summary.json').read_text())
    except (OSError, json.JSONDecodeError):
        record['status'] = 'no_summary'
        return record
    funnel = summary.get('funnel') or {}
    cases = summary.get('cases') or []
    record.update({
        'status': 'completed',
        'ai_verified': summary.get('ai_verified'),
        'ai_increment': summary.get('ai_increment'),
        'funnel': funnel,
        'case_results': [
            {'case': r.get('case', {}).get('id'),
             'gate': (r.get('candidate') or {}).get('gate'),
             'repair_status': (r.get('candidate') or {}).get('repair_status'),
             'candidate_sha256': (r.get('candidate') or {}).get('candidate_sha256')}
            for r in cases
        ],
        'provider_metadata': summary.get('provider_metadata'),
    })
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--models', nargs='+', required=True)
    ap.add_argument('--cases', type=Path,
                    default=ROOT / 'fixtures' / 'repair-benchmark' / 'cases.json')
    ap.add_argument('--case', default='')
    ap.add_argument('--repeats', type=int, default=1)
    ap.add_argument('--max-repair-rounds', type=int, default=2)
    ap.add_argument('--timeout', type=int, default=3600)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for spec in args.models:
        try:
            records.append(_run_model(spec, args))
        except Exception as exc:  # noqa: BLE001
            records.append({'spec': spec, 'status': 'error',
                            'error': f'{type(exc).__name__}: {exc}'})
    payload = {
        'schema_version': 1,
        'kind': 'model_qualification',
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'cases_path': str(args.cases),
        'records': records,
    }
    (args.out / 'summary.json').write_text(json.dumps(payload, indent=2) + '\n')
    lines = ['# Model qualification', '', '| model | status | verified | funnel |',
             '|---|---|---:|---|']
    for r in records:
        lines.append(f"| {r.get('spec')} | {r.get('status')} | "
                     f"{r.get('ai_verified', '?')} | `{json.dumps(r.get('funnel', {}))}` |")
    (args.out / 'README.md').write_text('\n'.join(lines) + '\n')
    sums = [f"{_sha(p)}  {p.name}" for p in sorted(args.out.iterdir())
            if p.is_file() and p.name != 'SHA256SUMS']
    (args.out / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
    print(json.dumps({'out': str(args.out), 'records': len(records)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
