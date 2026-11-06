# M5 access — accounts, install, rehearsal

| file | what it shows |
|---|---|
| `00-accounts.txt` | `m4verify` (uid 1004) and `m5verify` (uid 1005): own group, no sudo group, password locked, **zero** authorised keys at delivery |
| `01-rehearsal.txt` | a throwaway key installed with `USERNAME=m5verify`, login, `sha256sum -c` on both trees, `verify_all.sh` exit 0, then the key removed |

The rehearsal is M3's, not M5's. It proves the account, the paths and the
permissions work; it is not evidence of independence and it is not a gate result.

The installed trees are root-owned and read-only:

```
/opt/binrepair-handoff/M4-v4-handoff-2026-11-06/   12 checks, 13 files
/opt/binrepair-handoff/T8.3-evidence-2026-11-06/   29 rows
/opt/binrepair-handoff/T8.3-supplement-2026-11-06/ 4 files
```

Nothing here carries a `verified_by` value. V4 is still `not_run` and T8.3 is
still blocked.
