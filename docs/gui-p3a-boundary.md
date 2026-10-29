# GUI P3A / provisional boundary (2026-10-29)

Governing rule: the GUI renders controller/acceptance state and **never computes
an outcome**. Real evidence is not connected until the P3A checker and M5 worker
JSON are accepted.

## 1. Read-only verdict

- `app/status.py:display_verdict` only maps `snapshot["verdict"]` to a label.
- `static/js/poll.js` renders `data.verdict`; it has no route aggregation.
- If a job is finished but has no verdict, the page shows
  `尚无 verdict（等待 acceptance engine）`, never success.

## 2. P3A / attempt display

The current real Route A attempt is exactly the expected P3A shape:

```
V0 passed, V1 passed, V3 passed, V2/V4/V5 not_run
=> attempt verdict: inconclusive / required_check_not_run / interface
```

The GUI renders `inconclusive` and the raw `not_run` obligations. It must not
display `success` or `verified` for this state.

## 3. Superseded source warning

Until the P3A checker passes, real Route A evidence is provisional:

- `8256c8501afd95c02b371a99a507c436e5e431f49bdc5e4641b9a3bab2cbe64f`
  (`gate3-bundle-v2-2026-10-22`)
- `0ef655464459dd0597f8259b3784ee15389884c9a75b26afa1299af7f54bf8d5`
  (`gate3-bundle-2026-10-22`)

`app/provisional.py` shows a `PROVISIONAL` banner on comparison/evidence pages:

> 来源 8256c850… / 旧 attempt；不覆盖 Gate 3 approved；等 P3A checker PASS +
> M5 worker JSON 后再接真实数据。

The banner disappears only when the controller snapshot provides an explicit
approval signal: `gate3_approved: true` or `p3a_checker: "passed"`. These are
read-only signals; the GUI does not decide approval itself.

## 4. Artifact id vs. evidence path

- Obligation evidence uses `evidence_artifact_id` and links to
  `/artifacts/<artifact_id>`.
- A file path (for example `route_a/audit.json`) is **display-only**.
- `evidence_files` from the attempt metadata is not a worker primary key and
  must not be used as an artifact id. If bytes are not exposed by the controller
  yet, `/artifacts/<id>` shows an explicit "无法读取 artifact 内容" state.
- The adapter/mapping step must register real evidence files and pass artifact
  ids as `evidence`; paths remain in `details` for humans.

## 5. UI tests

`tests/test_evidence_ui.py` covers:

1. `not_run` is rendered as `not_run`, never as pass; no success label.
2. finished + missing decision shows pending.
3. superseded source shows the PROVISIONAL warning and does not claim Gate 3.
4. artifact links use artifact ids; paths are not link keys.
5. `/artifacts/<id>` view uses the id.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_evidence_ui.py tests/test_status_honesty.py tests/test_verdict_view.py
```

## 6. Connection gate

Do not wire real data beyond a provisional display until:

- P3A checker reports PASS, and
- M5 worker JSON is available.

When those arrive, the controller snapshot should expose
`gate3_approved`/`p3a_checker`; the GUI will drop the provisional banner and
render the normal verdict/obligations without any UI-side decision logic.
