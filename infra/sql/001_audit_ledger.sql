CREATE TABLE IF NOT EXISTS finora_audit_ledger (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    run_id TEXT NOT NULL,
    prediction JSONB NOT NULL,
    retrieved_evidence JSONB NOT NULL,
    model_version TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    forecast_timestamp TIMESTAMPTZ NOT NULL,
    inference_parameters JSONB NOT NULL,
    input_hash CHAR(64) NOT NULL,
    output_hash CHAR(64) NOT NULL,
    dataset_hash CHAR(64) NOT NULL,
    model_hash CHAR(64) NOT NULL,
    evidence_hash CHAR(64) NOT NULL,
    user_query_hash CHAR(64) NOT NULL,
    previous_hash CHAR(64),
    event_hash CHAR(64) NOT NULL UNIQUE
);

CREATE OR REPLACE FUNCTION finora_reject_audit_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'FINORA audit records are append-only';
END;
$$;

DROP TRIGGER IF EXISTS finora_audit_immutable ON finora_audit_ledger;
CREATE TRIGGER finora_audit_immutable
BEFORE UPDATE OR DELETE ON finora_audit_ledger
FOR EACH ROW EXECUTE FUNCTION finora_reject_audit_mutation();

CREATE INDEX IF NOT EXISTS finora_audit_run_id
ON finora_audit_ledger (run_id, occurred_at DESC);
