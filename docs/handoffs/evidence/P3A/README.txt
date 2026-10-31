# P3A Route A package (M3 -> M5)

- result-bundle.json: gates V0 pass / V1 pass / V2 not_run / V3 pass / V4 not_run / V5 not_run
  (this is the 10-29 original job's observed state — historical fact, not modified)
- candidate: c4a159...bcaa82; original: aa428157...8393
- V2 and V5 were measured later on 2026-10-30 and are supplied as supplements:
  - v2-routea-supplement.json  -> V2 interface 16/16 passed (candidate c4a159)
  - v5-routea-supplement.json  -> V5 reproducibility byte-identical x2
  - routea-candidate.readelf.txt -> raw readelf dump for the V2 probe
  The adapter should read these supplement files to score Route A V2/V5;
  they are NOT reflected in result-bundle.json (which stays as the 10-29 job record).
- V4 symbolic remains not_run (unchanged).
- all result-bundle gate evidence paths exist in this package
- handoff.json: id + files list
- No attempt JSON included: M5 generates it with the adapter and artifact ids.
- check_handoff.py: PASS 29/29 (re-run 2026-10-31 by M3+M5 agent, after adding V2/V5 supplements).
