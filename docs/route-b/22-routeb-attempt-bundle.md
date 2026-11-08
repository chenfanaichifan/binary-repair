# Route B attempt writer — bundle → worker JSON

`routeb/attempt_writer.py` maps one Route B static bundle to the worker's
per-attempt JSON at:

```text
<data>/jobs/<job>/runs/<run>/attempts/<attempt>.json
```

It never invents `passed`. Static bundle → V0/V1 measured, V2–V5 `not_run`;
therefore the attempt verdict is **inconclusive**, not a Gate 4 pass.

## Direct command

```bash
PYTHON=/opt/angr-venv/bin/python

"$PYTHON" -m routeb.executor \
  --original fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf \
  --candidate routeb/out/gate4/roundtrip.elf \
  --func CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink \
  --mode roundtrip \
  --out-dir var/jobs/routeb/roundtrip

"$PYTHON" -m routeb.attempt_writer \
  --bundle var/jobs/routeb/roundtrip \
  --data-dir var \
  --job <job-id> --run <run-id> --attempt <attempt-id>
```

`--attempt` may be omitted; the latest `route_b` attempt of the run is used.

## Worker-driven command

```bash
export PYTHON=/opt/angr-venv/bin/python
export BINARYREPAIR_DATA_DIR="$PWD/var"
export BINARYREPAIR_ROUTEB_BUNDLE="$PWD/var/jobs/routeb/roundtrip"
export BINARYREPAIR_ATTEMPT_CMD="$PWD/routeb/attempt_writer.sh"

"$PYTHON" -m app.services.worker --data-dir var --once
```

`routeb/attempt_writer.sh` just calls `python -m routeb.attempt_writer
--from-env`; the worker provides `BINARYREPAIR_JOB_ID/RUN_ID/ATTEMPT_ID/ROUTE`.
No provider key and no network are used.

## Actual output sample

Run against the frozen Gate 4 round-trip ELF (26,792 B):

```json
{
  "path": "/tmp/rb-attempt-demo/var/jobs/de877f24e8e4435f905c99e4d04628f1/runs/aebec39e8fd9487f8af0d16437489ec2/attempts/445e173c3d374ff480f5b28a8937129c.json",
  "payload": {
    "route": "route_b",
    "candidate_sha256": "decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b",
    "results": {
      "V0": "passed",
      "V1": "passed",
      "V2": "not_run",
      "V3": "not_run",
      "V4": "not_run",
      "V5": "not_run"
    },
    "evidence": {
      "V0": "c8dfa430d0d54acfbd335781d04a99ee",
      "V1": "d339450cd9334da7a0dacd74ee556aec"
    },
    "details": {
      "V0": "original aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393 vs job aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393",
      "V1": "static ELF audit passed",
      "V2": "interface check not implemented in Route B executor",
      "V3": "no runtime manifest in bundle",
      "V4": "symbolic check not run",
      "V5": "build-twice not_run"
    }
  }
}
```

Worker result after `run_once`:

```text
processed 1
attempt 445e... phase=finished outcome=inconclusive
reason=required_check_not_run failing_obligation=interface
obligations: identity=passed, structure=passed,
             interface/behaviour/symbolic/reproducibility=not_run
```

## Mapping rules

| Gate | Static bundle | Runtime bundle |
|---|---|---|
| V0 identity | `passed` if bundle original == job original; candidate artifact registered | same |
| V1 structure | `passed` if `audit.json.pass`; audit artifact registered | same |
| V2 interface | `not_run` | not implemented by this executor |
| V3 behaviour | `not_run` | `passed` only if `manifest-compare.json.gate4_pass` or `manifest-repaired.json.repaired_pass` |
| V4 symbolic | `not_run` | not implemented |
| V5 reproducibility | `not_run` | `passed` only if `reproducibility.json.state=measured` and `pass=true` |

A static bundle therefore cannot produce `success_within_scope`; V2–V5 are
required and remain `not_run`. Do not send “verified” to the UI from this bundle.

## Provider / executor separation

- provider returns `candidate.replacement_c`; no key/network in the executor;
- write that C to a file and pass `--c-source` to `routeb.executor`;
- executor and attempt writer operate only on local files;
- runtime `--run-manifest` remains guest-only; no host execution by default.
