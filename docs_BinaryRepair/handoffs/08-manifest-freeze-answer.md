# Manifest freeze answer: `a564f039…` is reproducible

**From:** Member 4 (verification)
**To:** Member 3 (fixture and execution environment)
**Date:** 2026-10-20
**Re:** your request for the full hash and the rule behind `MANIFEST_SET_SHA256`

---

## 1. Answer

- **Full value:** `a564f0397a741b1a4fc386a3149d54550c1bfe7c02958309e021fb6f03333a78`
- **It is a hash of a canonical JSON index, not of concatenated file bytes.** The
  implementation is `app/domain/manifests.py` (`manifest_set_json` /
  `manifest_set_sha256`); the canonical form is:

```json
{"case_id":"CWE121_src_char_declare_cpy_51b","manifests":[{"name":"invalid.json","sha256":"d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d"},{"name":"valid.json","sha256":"17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76"}],"original_sha256":"aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393","schema_version":1}
```

  Rules: JSON with sorted keys, compact separators (`,` and `:`), UTF-8
  (`ensure_ascii=False`), `manifests` sorted by `name`; then SHA-256 of the UTF-8
  bytes.
- **Files covered:** two files under
  `fixtures/public/CWE121_src_char_declare_cpy_51b/tests/`, with relative names
  `valid.json` and `invalid.json` (the directory is the hash root):

| File | Size | SHA-256 |
|---|---|---|
| `tests/valid.json` | 1,951 bytes | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` |
| `tests/invalid.json` | 1,460 bytes | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` |

- Fixed inputs: `case_id = CWE121_src_char_declare_cpy_51b`,
  `original_sha256 = aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`,
  `schema_version = 1`.

## 2. Why your local reproduction failed

The frozen values hash the **committed LF bytes exactly**. Verified from the git
blobs on `origin/main`:

- `valid.json`: 1,951 bytes, 0 CRLF, 75 LF -> `17b2ee39…` (raw matches)
- `invalid.json`: 1,460 bytes, 0 CRLF, 41 LF -> `d493f370…` (raw matches)

If the copies you hashed came through Windows/WeChat with CRLF line endings, the
same file hashes become `7f984a97…` (valid) and `c5e8dc0a…` (invalid), and the
set hash no longer matches. Concatenating file bytes or hashing JSON pairs/lists
also cannot match, because the rule is the canonical JSON index above — the file
*names* enter only as `"valid.json"` / `"invalid.json"`, sorted, and the case id
and original hash are part of the payload.

A second environment trap: **`main` currently has no `.gitattributes`**, so a
Windows checkout applies `core.autocrlf=true` and the JSON files become CRLF;
the same tests then fail on Windows while passing on Linux. Add
`* text=auto eol=lf` (and keep the fixture JSON as LF on disk) so the freeze is
portable.

## 3. What to do with the freeze record

- Keep `a564f039…` as the frozen set hash; it is consistent with the two
  per-file hashes and the documented rule.
- Record it as: `manifest_set_sha256 = a564f039…` over
  `{case_id, original_sha256, manifests[{name, sha256}]}` with the canonical
  JSON rule above.
- To re-verify on Linux/LF:
  `sha256sum fixtures/public/CWE121_src_char_declare_cpy_51b/tests/*.json` and
  `python -m pytest tests/test_fixture_v3_manifest.py -q -p no:cacheprovider`.
- Do not change the constants to the CRLF hashes. The mismatch is a checkout
  artifact, not a freeze error.
