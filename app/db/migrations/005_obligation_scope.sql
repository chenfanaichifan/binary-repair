-- 005: evidence scope per obligation.
--
-- The API used to derive the scope from the obligation kind on the client side,
-- so the displayed scope was an inference rather than a persisted fact. Scope is
-- now written by the host at persist time and backfilled here for existing rows.
--
-- Layers: metadata | static | binary | model | replay.

ALTER TABLE obligations ADD COLUMN scope TEXT;

UPDATE obligations
SET scope = CASE kind
    WHEN 'identity'          THEN 'metadata'
    WHEN 'structure'         THEN 'binary'
    WHEN 'interface'         THEN 'binary'
    WHEN 'behaviour'         THEN 'replay'
    WHEN 'symbolic'          THEN 'model'
    WHEN 'reproducibility'   THEN 'replay'
    WHEN 'round_trip'        THEN 'replay'
    WHEN 'repaired_behaviour' THEN 'replay'
    ELSE 'metadata'
END
WHERE scope IS NULL;
