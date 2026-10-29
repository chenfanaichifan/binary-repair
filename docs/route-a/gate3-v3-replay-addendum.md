# Gate 3 v3 build/hash replay — addendum

**Status:** archival replay of a self-contained package; **not** a new Gate 3
decision and not a Gate 4 result.

The canonical Gate 3 record is approved at
`docs/route-a/gate3-record.md` SHA-256
`0b3b51e49f24c5759ff5d37a0569d44149af989dd4e72af6e51b279f0901f2da`
(Gate 3 approved 2026-10-22). This addendum does not modify that record or its
M4/Lead signature rows.

## 8.1 Handoff replay (2026-10-22, retained)

```text
handoff bundle zip: 957d73d4284a4e5ced27de451bacdfe8956751232bd4a1fa5aa6454dccdc108e
SHA256SUMS file:    640b448228ea8e16d15930c5c81a1478a11a82a1feddb122f6262157a87788dd
original:           aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393
candidate/replayed: c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
```

## 8.2 Formal v3 bundle replay

```text
v3 bundle:          1d0e5441925de0fc3cc814d8c36d6443d8c1a65b87e05a4d6d008beaac44271f
size:               35,887 B; 26 files
SHA256SUMS file:    faf30b6acb6918ad0d01f2c6a9ac35084a10e3d8cd3cca91120e8f37eee9bb52
sha256sum -c:       25/25 OK
candidate:          c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
original:           aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393
regen:              56331eedb4d72c55eec4e0f105fb20207576e6e6860b79ca4cedb175ed54e843
replayed:           c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82
cmp:                byte-identical
contract canonical: 24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
contract file:      15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df
```

**Result:** formal v3 build/hash replay = PASS. No candidate/replay mismatch.
The contract bytes are not packaged in v3; the file hash is bound by
`gate3-summary.json` / `guest-fingerprint.json` and separately verified in the
delivery set.

This does **not** create Route A/B success, Gate 4 formal pass, or fixture freeze.
Those remain pending in the real-execution path (handoff 34).
