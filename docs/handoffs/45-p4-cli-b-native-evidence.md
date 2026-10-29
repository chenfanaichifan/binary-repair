# 45 — P4 CLI B and native evidence

## CLI choice B

P4 uses the existing `gate4-harness` uid 11 / wrapper `b232d60b…`:

```bash
jobwrap gate4
```

No arguments. The runner, repo and work dir come from the root-owned
`gate4.conf`; M5/M3 must not add `-- <runner> <repo> <work>` to P4.

The older `jobwrap gate4 -- ...` invocation is withdrawn.

## P4 output

The runner produces `manifest-compare.json` only. It does **not** produce native
`case-01..06.json`.

If six case files are present, they are derived:

```json
{"derived_from":"manifest-compare.json","runner_native":false}
```

Native evidence is only `manifest-compare.json`. The six derived rows must not
be described as native raw evidence.

If a package claims native case raw and it is absent, record the missing item;
do **not** write `gate4_pass`. A P4 record may note `native_case_raw: missing`,
`derived_cases: present`, but that is not a formal pass.

## Gate 5

The fixed-script jobwrap mode (A) remains separate:

```bash
GATE5_SCRIPT=/path/M4-gate5-fixed.sh \
  jobwrap gate5 -- <repo>/routeb/jobwrap_gate5.sh <repo> /var/tmp/gate5-work
```

P4 must not add a second parameter entry point.
