# 48 — P4 CLI B artifacts still missing

The CLI decision is accepted:

```text
jobwrap gate4        # no args
root-owned gate4.conf
wrapper b232d60b…
gate4-harness uid 11
```

But the executable artifacts are **not in any fetched ref / workspace**:

| Required | Status |
|---|---|
| wrapper `b232d60b…` original + full SHA-256 | missing |
| `gate4.conf` full text, hash, root/perms, fixed params | missing (old handoff only cites hash `f240c2f8…`) |
| new runner hash | missing; current `routeb/gate4_runner.sh` is `515c4d60…`, not confirmed as the wrapper target |
| jobwrap version/build hash | missing; old fingerprint cites `b0371c10…`, not confirmed new |
| no-arg behavior/output paths | documented as `gate4-status.json`, `manifest-compare.json`; not observed |

Therefore P4 CLI B remains **NOT EXECUTABLE** until M3/VMer publishes these
artifacts. M5 will not fabricate the wrapper/conf/runner hashes.

Native rule: only `manifest-compare.json` is native. Derived cases must be
marked `runner_native=false`, `derived_from=manifest-compare.json`; missing native
case raw is a missing item, never a `gate4_pass`.
