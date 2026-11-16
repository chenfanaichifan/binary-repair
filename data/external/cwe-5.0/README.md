# CWE 5.0 external knowledge snapshot

This directory is a bounded, normalized projection of MITRE CWE 5.0
(catalog date 2026-10-28, XML schema 8.0). It is external knowledge input for
Phase-8D, not a capability or support claim.

Sources (official MITRE CWE):

- catalog: https://cwe.mitre.org/data/xml/cwec_v5.0.xml.zip
- schema: https://cwe.mitre.org/data/xsd/cwe_schema_v8.0.xsd
- prior baseline: https://cwe.mitre.org/data/xml/cwec_v4.19.xml.zip
- terms: https://cwe.mitre.org/about/termsofuse.html

Files:

- `snapshot.json`: catalog metadata, all 984 weakness ids/names and compact
  fields, plus new/removed ids against 4.19 and schema-drift facts. Description
  prose is stored as SHA-256, not copied.
- `schema-drift.json`: namespace/schema/count changes and structural breaking
  changes between the 4.19 and 5.0 catalogs.
- `provenance.json`: source URLs, byte sizes, SHA-256 of downloaded official
  archives/XSD/XML, retrieval date, normalization rules and limitations.

Measured facts (not briefing approximations):

- 984 weaknesses in the 5.0 XML; prior 4.19 has 969; **15 new ids**, 0 removed.
- The briefing says approximately 16 new; the measured 4.19-to-5.0 difference
  is 15. The repository records the measured value and does not assert 16.
- Namespace changes from `http://cwe.mitre.org/cwe-7` (schema 7.3) to
  `http://cwe.mitre.org/cwe-8` (schema 8.0); Categories disappear from the
  weakness catalog layout and 431 Groupings appear.

The raw 19 MB XML and 131 KB XSD are not committed; their hashes are in
`provenance.json`. The scanner is offline by default and a live check is
optional and never used in tests.
