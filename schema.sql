-- ============================================================================
-- NDIC Platform — PostgreSQL Schema
-- Nigerian Dairy Intelligence Consortium
-- ============================================================================
-- Copy-paste into psql or use as the baseline Alembic migration.
-- Requires PostgreSQL 14+.
-- Run as a superuser or the ndic_owner role.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Database & role setup  (run once as superuser; skip if already done)
-- ---------------------------------------------------------------------------
-- CREATE DATABASE ndic
--     ENCODING = 'UTF8'
--     LC_COLLATE = 'en_NG.UTF-8'
--     LC_CTYPE  = 'en_NG.UTF-8'
--     TEMPLATE = template0;
--
-- CREATE ROLE ndic_app   LOGIN PASSWORD '<<strong_password>>';
-- CREATE ROLE ndic_owner LOGIN PASSWORD '<<strong_password>>' CREATEROLE;
-- GRANT CONNECT ON DATABASE ndic TO ndic_app, ndic_owner;

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";    -- gen_random_uuid(), digest()

-- ---------------------------------------------------------------------------
-- ENUM types
-- ---------------------------------------------------------------------------

CREATE TYPE userrole AS ENUM (
    'farm',
    'processor',
    'government',
    'lender',
    'arpexas_admin'
);

CREATE TYPE organizationtype AS ENUM (
    'farm',
    'processing_company',
    'government_agency',
    'finance_institution'
);

CREATE TYPE animalsex AS ENUM (
    'male',
    'female'
);

CREATE TYPE animalstatus AS ENUM (
    'active',
    'deceased',
    'sold',
    'transferred',
    'quarantined'
);

CREATE TYPE animalbreed AS ENUM (
    'bunaji',
    'rahaji',
    'azawak',
    'shuwa_arab',
    'muturu',
    'keteku',
    'friesian',
    'jersey',
    'brown_swiss',
    'friesian_bunaji_cross',
    'crossbreed',
    'other'
);

CREATE TYPE diseasetype AS ENUM (
    'foot_and_mouth',
    'cbpp',
    'brucellosis',
    'lumpy_skin_disease',
    'anthrax',
    'mastitis',
    'trypanosomiasis',
    'bovine_tuberculosis',
    'haemorrhagic_septicaemia',
    'east_coast_fever',
    'rift_valley_fever',
    'other'
);

CREATE TYPE alertconfirmationstatus AS ENUM (
    'suspected',
    'confirmed',
    'resolved',
    'false_alarm'
);

CREATE TYPE alertseverity AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

CREATE TYPE qualitygrade AS ENUM (
    'A',
    'B',
    'C',
    'rejected'
);

CREATE TYPE collateralconfidence AS ENUM (
    'low',
    'medium',
    'high'
);

CREATE TYPE ledgereventtype AS ENUM (
    'animal_registered',
    'animal_status_changed',
    'health_record_submitted',
    'processor_intake_submitted',
    'disease_alert_submitted',
    'disease_alert_status_updated',
    'lender_assessment_submitted',
    'user_created',
    'organization_registered',
    'farm_registered',
    'access_granted',
    'access_revoked'
);

-- ===========================================================================
-- LAYER 1 — DATA OWNERSHIP
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- organizations
-- ---------------------------------------------------------------------------
CREATE TABLE organizations (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid(),
    name                VARCHAR(255) NOT NULL,
    org_type            organizationtype NOT NULL,
    registration_number VARCHAR(100) UNIQUE,
    country             VARCHAR(100) NOT NULL DEFAULT 'Nigeria',
    state               VARCHAR(100) NOT NULL,
    lga                 VARCHAR(100),
    address             TEXT,
    contact_email       VARCHAR(255),
    contact_phone       VARCHAR(50),
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_organizations PRIMARY KEY (id)
);

CREATE INDEX ix_organizations_org_type  ON organizations (org_type);
CREATE INDEX ix_organizations_state     ON organizations (state);
CREATE INDEX ix_organizations_created_at ON organizations (created_at);

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            userrole    NOT NULL,
    organization_id UUID        REFERENCES organizations (id) ON DELETE RESTRICT,
    -- Ed25519 public key, PEM-encoded
    public_key      TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX ix_users_role            ON users (role);
CREATE INDEX ix_users_organization_id ON users (organization_id);
CREATE INDEX ix_users_email           ON users (email);

-- ---------------------------------------------------------------------------
-- farms
-- ---------------------------------------------------------------------------
CREATE TABLE farms (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations (id) ON DELETE RESTRICT,
    farm_code       VARCHAR(50) NOT NULL,
    farm_name       VARCHAR(255) NOT NULL,
    state           VARCHAR(100) NOT NULL,
    lga             VARCHAR(100),
    latitude        DOUBLE PRECISION CHECK (latitude  BETWEEN -90  AND 90),
    longitude       DOUBLE PRECISION CHECK (longitude BETWEEN -180 AND 180),
    total_capacity  INTEGER      CHECK (total_capacity > 0),
    established_date TIMESTAMPTZ,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,

    -- Audit
    created_by      UUID        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_farms PRIMARY KEY (id),
    CONSTRAINT uq_farms_code UNIQUE (farm_code)
);

CREATE INDEX ix_farms_organization_id_created_at ON farms (organization_id, created_at);
CREATE INDEX ix_farms_state                      ON farms (state);

-- ---------------------------------------------------------------------------
-- animals
-- ---------------------------------------------------------------------------
CREATE TABLE animals (
    id            UUID        NOT NULL DEFAULT gen_random_uuid(),
    farm_id       UUID        NOT NULL REFERENCES farms (id) ON DELETE RESTRICT,
    tag_number    VARCHAR(100) NOT NULL,
    breed         animalbreed NOT NULL,
    sex           animalsex   NOT NULL,
    date_of_birth TIMESTAMPTZ,
    weight_kg     DOUBLE PRECISION CHECK (weight_kg > 0),
    status        animalstatus NOT NULL DEFAULT 'active',
    acquired_at   TIMESTAMPTZ NOT NULL,
    notes         TEXT,
    metadata      JSONB,       -- e.g. {"rfid": "...", "sire_tag": "...", "dam_tag": "..."}

    -- Audit + cryptographic proof
    created_by    UUID        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    signature     TEXT        NOT NULL,   -- Ed25519 sig (base64url) of SHA-256(canonical JSON)

    CONSTRAINT pk_animals PRIMARY KEY (id),
    CONSTRAINT uq_animal_farm_tag UNIQUE (farm_id, tag_number)
);

CREATE INDEX ix_animals_farm_id_created_at ON animals (farm_id, created_at);
CREATE INDEX ix_animals_status             ON animals (status);
CREATE INDEX ix_animals_breed              ON animals (breed);

-- ---------------------------------------------------------------------------
-- health_records
-- ---------------------------------------------------------------------------
CREATE TABLE health_records (
    id                    UUID        NOT NULL DEFAULT gen_random_uuid(),
    animal_id             UUID        NOT NULL REFERENCES animals (id) ON DELETE RESTRICT,
    farm_id               UUID        NOT NULL REFERENCES farms   (id) ON DELETE RESTRICT,
    record_date           TIMESTAMPTZ NOT NULL,
    temperature_celsius   DOUBLE PRECISION,
    behavior_score        INTEGER,
    milk_yield_liters     DOUBLE PRECISION,
    body_condition_score  DOUBLE PRECISION,
    treatments            JSONB,      -- [{drug_name,dose_mg,administered_at,administered_by,...}]
    vaccinations          JSONB,      -- [{vaccine_name,batch_number,administered_at,next_due}]
    notes                 TEXT,

    -- Audit + cryptographic proof
    created_by  UUID        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    signature   TEXT        NOT NULL,

    CONSTRAINT pk_health_records PRIMARY KEY (id),
    CONSTRAINT ck_temperature_range
        CHECK (temperature_celsius IS NULL OR temperature_celsius BETWEEN 30 AND 45),
    CONSTRAINT ck_behavior_score_range
        CHECK (behavior_score IS NULL OR behavior_score BETWEEN 1 AND 5),
    CONSTRAINT ck_milk_yield_non_negative
        CHECK (milk_yield_liters IS NULL OR milk_yield_liters >= 0),
    CONSTRAINT ck_bcs_range
        CHECK (body_condition_score IS NULL OR body_condition_score BETWEEN 1.0 AND 5.0)
);

CREATE INDEX ix_health_records_farm_id_record_date   ON health_records (farm_id, record_date);
CREATE INDEX ix_health_records_animal_id_record_date ON health_records (animal_id, record_date);

-- ===========================================================================
-- LAYER 1 (continued) — PROCESSOR / GOVERNMENT / LENDER DATA
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- processor_intakes
-- ---------------------------------------------------------------------------
CREATE TABLE processor_intakes (
    id                              UUID            NOT NULL DEFAULT gen_random_uuid(),
    processor_org_id                UUID            NOT NULL REFERENCES organizations (id) ON DELETE RESTRICT,
    origin_farm_id                  UUID            NOT NULL REFERENCES farms          (id) ON DELETE RESTRICT,
    intake_date                     TIMESTAMPTZ     NOT NULL,
    volume_liters                   DOUBLE PRECISION NOT NULL,
    quality_grade                   qualitygrade    NOT NULL,
    fat_content_percent             DOUBLE PRECISION,
    protein_content_percent         DOUBLE PRECISION,
    somatic_cell_count              INTEGER,        -- cells/mL
    temperature_at_receipt_celsius  DOUBLE PRECISION,
    price_per_liter_ngn             DOUBLE PRECISION NOT NULL,
    total_amount_ngn                DOUBLE PRECISION NOT NULL,
    batch_reference                 VARCHAR(100),
    notes                           TEXT,

    -- Audit + cryptographic proof
    created_by  UUID        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    signature   TEXT        NOT NULL,

    CONSTRAINT pk_processor_intakes PRIMARY KEY (id),
    CONSTRAINT ck_volume_positive   CHECK (volume_liters > 0),
    CONSTRAINT ck_price_positive    CHECK (price_per_liter_ngn > 0),
    CONSTRAINT ck_total_positive    CHECK (total_amount_ngn > 0),
    CONSTRAINT ck_fat_range
        CHECK (fat_content_percent IS NULL OR fat_content_percent BETWEEN 0 AND 100),
    CONSTRAINT ck_protein_range
        CHECK (protein_content_percent IS NULL OR protein_content_percent BETWEEN 0 AND 100),
    CONSTRAINT ck_scc_non_negative
        CHECK (somatic_cell_count IS NULL OR somatic_cell_count >= 0)
);

CREATE INDEX ix_processor_intakes_org_id_intake_date  ON processor_intakes (processor_org_id, intake_date);
CREATE INDEX ix_processor_intakes_farm_id_intake_date ON processor_intakes (origin_farm_id, intake_date);

-- ---------------------------------------------------------------------------
-- disease_alerts
-- ---------------------------------------------------------------------------
CREATE TABLE disease_alerts (
    id                    UUID                    NOT NULL DEFAULT gen_random_uuid(),
    reporting_org_id      UUID                    NOT NULL REFERENCES organizations (id) ON DELETE RESTRICT,
    alert_date            TIMESTAMPTZ             NOT NULL,
    disease_type          diseasetype             NOT NULL,
    state                 VARCHAR(100)            NOT NULL,
    lga                   VARCHAR(100),
    coordinates           JSONB,                  -- {"lat": 9.0579, "lng": 7.4951}
    affected_animal_count INTEGER                 CHECK (affected_animal_count >= 0),
    affected_farm_count   INTEGER                 CHECK (affected_farm_count  >= 0),
    confirmation_status   alertconfirmationstatus NOT NULL DEFAULT 'suspected',
    severity              alertseverity           NOT NULL DEFAULT 'low',
    description           TEXT,
    response_actions      JSONB,
    resolved_at           TIMESTAMPTZ,

    -- Audit + cryptographic proof
    created_by  UUID        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    signature   TEXT        NOT NULL,

    CONSTRAINT pk_disease_alerts PRIMARY KEY (id)
);

CREATE INDEX ix_disease_alerts_org_id_alert_date   ON disease_alerts (reporting_org_id, alert_date);
CREATE INDEX ix_disease_alerts_state_disease_type  ON disease_alerts (state, disease_type);
CREATE INDEX ix_disease_alerts_confirmation_status ON disease_alerts (confirmation_status);
CREATE INDEX ix_disease_alerts_severity            ON disease_alerts (severity);

-- ---------------------------------------------------------------------------
-- lender_assessments
-- ---------------------------------------------------------------------------
CREATE TABLE lender_assessments (
    id                        UUID                  NOT NULL DEFAULT gen_random_uuid(),
    lender_org_id             UUID                  NOT NULL REFERENCES organizations (id) ON DELETE RESTRICT,
    farm_id                   UUID                  NOT NULL REFERENCES farms          (id) ON DELETE RESTRICT,
    assessment_date           TIMESTAMPTZ           NOT NULL,
    herd_count                INTEGER               NOT NULL,
    herd_valuation_ngn        DOUBLE PRECISION      NOT NULL,
    risk_score                DOUBLE PRECISION      NOT NULL,   -- 0–100
    collateral_confidence     collateralconfidence  NOT NULL,
    loan_amount_requested_ngn DOUBLE PRECISION,
    loan_term_months          INTEGER,
    methodology_notes         TEXT,
    supporting_data           JSONB,                -- snapshot of data inputs used

    -- Audit + cryptographic proof
    created_by  UUID        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    signature   TEXT        NOT NULL,

    CONSTRAINT pk_lender_assessments PRIMARY KEY (id),
    CONSTRAINT ck_risk_score_range    CHECK (risk_score BETWEEN 0 AND 100),
    CONSTRAINT ck_herd_count_positive CHECK (herd_count > 0),
    CONSTRAINT ck_valuation_positive  CHECK (herd_valuation_ngn > 0),
    CONSTRAINT ck_loan_amount_positive
        CHECK (loan_amount_requested_ngn IS NULL OR loan_amount_requested_ngn > 0)
);

CREATE INDEX ix_lender_assessments_org_id_date  ON lender_assessments (lender_org_id, assessment_date);
CREATE INDEX ix_lender_assessments_farm_id_date ON lender_assessments (farm_id, assessment_date);

-- ===========================================================================
-- LAYER 2 — GOVERNANCE: IMMUTABLE LEDGER
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- ledger_log  (APPEND-ONLY — protected by trigger below)
-- ---------------------------------------------------------------------------
CREATE TABLE ledger_log (
    id               UUID            NOT NULL DEFAULT gen_random_uuid(),
    event_type       ledgereventtype NOT NULL,
    actor_id         UUID            NOT NULL REFERENCES users         (id) ON DELETE RESTRICT,
    actor_org_id     UUID                     REFERENCES organizations (id) ON DELETE RESTRICT,
    target_table     VARCHAR(100)    NOT NULL,
    target_record_id UUID            NOT NULL,
    -- SHA-256 hex of canonical JSON of the target record
    payload_hash     CHAR(64)        NOT NULL,
    -- Ed25519 signature of (payload_hash || previous_hash), base64url-encoded
    signature        TEXT            NOT NULL,
    -- SHA-256 chain link to previous entry for this actor/table pair
    previous_hash    CHAR(64),
    -- Forensic only — not exposed via API
    ip_address       VARCHAR(45),
    user_agent       VARCHAR(500),
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT pk_ledger_log PRIMARY KEY (id)
);

CREATE INDEX ix_ledger_log_actor_id_created_at     ON ledger_log (actor_id, created_at);
CREATE INDEX ix_ledger_log_actor_org_id_created_at ON ledger_log (actor_org_id, created_at);
CREATE INDEX ix_ledger_log_target_record_id        ON ledger_log (target_record_id);
CREATE INDEX ix_ledger_log_event_type_created_at   ON ledger_log (event_type, created_at);
CREATE INDEX ix_ledger_log_payload_hash            ON ledger_log (payload_hash);

-- ── Immutability trigger ────────────────────────────────────────────────────
-- Prevents any UPDATE or DELETE on ledger_log at the database level.
-- This is a belt-and-suspenders measure on top of application-layer controls.

CREATE OR REPLACE FUNCTION fn_ledger_log_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION
            'ledger_log is append-only: UPDATE is forbidden. entry_id=%', OLD.id
            USING ERRCODE = 'restrict_violation';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'ledger_log is append-only: DELETE is forbidden. entry_id=%', OLD.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER tg_ledger_log_no_update
    BEFORE UPDATE ON ledger_log
    FOR EACH ROW EXECUTE FUNCTION fn_ledger_log_immutable();

CREATE TRIGGER tg_ledger_log_no_delete
    BEFORE DELETE ON ledger_log
    FOR EACH ROW EXECUTE FUNCTION fn_ledger_log_immutable();

-- ── Domain-record immutability triggers ─────────────────────────────────────
-- Prevent UPDATE of audit columns on domain tables.
-- Correction workflow: submit a new record with a notes field referencing the
-- original record ID — never mutate the original.

CREATE OR REPLACE FUNCTION fn_audit_columns_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.created_by  IS DISTINCT FROM OLD.created_by  OR
       NEW.created_at  IS DISTINCT FROM OLD.created_at  OR
       NEW.signature   IS DISTINCT FROM OLD.signature   THEN
        RAISE EXCEPTION
            'Audit columns (created_by, created_at, signature) are immutable on table %.', TG_TABLE_NAME
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;

-- Apply to every domain table that carries audit columns
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'animals', 'health_records', 'processor_intakes',
        'disease_alerts', 'lender_assessments'
    ] LOOP
        EXECUTE format(
            'CREATE TRIGGER tg_%s_audit_immutable
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION fn_audit_columns_immutable();',
            tbl, tbl
        );
    END LOOP;
END;
$$;

-- ===========================================================================
-- LAYER 3 — AGGREGATION VIEWS
-- ===========================================================================

-- Animal lifetime health trajectory
CREATE OR REPLACE VIEW v_animal_health_trajectory AS
SELECT
    a.id                        AS animal_id,
    a.tag_number,
    a.breed,
    a.farm_id,
    COUNT(hr.id)                AS total_records,
    ROUND(AVG(hr.temperature_celsius)::NUMERIC, 2)  AS avg_temperature_celsius,
    ROUND(AVG(hr.milk_yield_liters)::NUMERIC, 2)    AS avg_milk_yield_liters,
    ROUND(AVG(hr.behavior_score)::NUMERIC, 2)       AS avg_behavior_score,
    ROUND(AVG(hr.body_condition_score)::NUMERIC, 2) AS avg_body_condition_score,
    MIN(hr.record_date)         AS first_record_date,
    MAX(hr.record_date)         AS last_record_date
FROM animals a
LEFT JOIN health_records hr ON hr.animal_id = a.id
GROUP BY a.id, a.tag_number, a.breed, a.farm_id;

-- Farm monthly milk yield + revenue
CREATE OR REPLACE VIEW v_farm_monthly_productivity AS
SELECT
    f.id                                        AS farm_id,
    f.farm_code,
    DATE_TRUNC('month', hr.record_date)         AS month,
    COUNT(DISTINCT a.id)                        AS active_cow_count,
    ROUND(SUM(hr.milk_yield_liters)::NUMERIC, 2) AS total_milk_yield_liters,
    ROUND(AVG(hr.milk_yield_liters)::NUMERIC, 2) AS avg_daily_yield_per_cow,
    COUNT(hr.id)                                AS health_record_count
FROM farms f
JOIN animals a ON a.farm_id = f.id AND a.sex = 'female' AND a.status = 'active'
LEFT JOIN health_records hr ON hr.animal_id = a.id
GROUP BY f.id, f.farm_code, DATE_TRUNC('month', hr.record_date);

-- Regional disease surveillance
CREATE OR REPLACE VIEW v_regional_disease_profile AS
SELECT
    state,
    DATE_TRUNC('month', alert_date) AS month,
    COUNT(*)                        AS total_alerts,
    COUNT(*) FILTER (WHERE confirmation_status = 'confirmed') AS confirmed_alerts,
    COUNT(*) FILTER (WHERE confirmation_status NOT IN ('resolved', 'false_alarm')) AS active_alerts,
    MAX(severity::TEXT)             AS highest_severity,
    JSONB_OBJECT_AGG(
        disease_type,
        disease_count
    ) AS disease_breakdown
FROM (
    SELECT
        state, alert_date, confirmation_status, severity, disease_type,
        COUNT(*) AS disease_count
    FROM disease_alerts
    GROUP BY state, alert_date, confirmation_status, severity, disease_type
) sub
GROUP BY state, DATE_TRUNC('month', alert_date);

-- Lender collateral risk summary
CREATE OR REPLACE VIEW v_herd_finance_risk AS
SELECT
    la.farm_id,
    f.farm_code,
    COUNT(la.id)                                        AS assessment_count,
    ROUND(AVG(la.risk_score)::NUMERIC, 2)               AS avg_risk_score,
    MAX(la.assessment_date)                             AS latest_assessment_date,
    -- Most recent assessment values via DISTINCT ON
    (SELECT herd_valuation_ngn  FROM lender_assessments WHERE farm_id = la.farm_id ORDER BY assessment_date DESC LIMIT 1) AS latest_herd_valuation_ngn,
    (SELECT risk_score          FROM lender_assessments WHERE farm_id = la.farm_id ORDER BY assessment_date DESC LIMIT 1) AS latest_risk_score,
    (SELECT collateral_confidence FROM lender_assessments WHERE farm_id = la.farm_id ORDER BY assessment_date DESC LIMIT 1) AS latest_collateral_confidence
FROM lender_assessments la
JOIN farms f ON f.id = la.farm_id
GROUP BY la.farm_id, f.farm_code;

-- ===========================================================================
-- PERMISSIONS  (run as superuser; adjust role names to match your setup)
-- ===========================================================================

-- Application role: read + write domain tables, append ledger
GRANT SELECT, INSERT ON
    organizations, users, farms, animals,
    health_records, processor_intakes, disease_alerts, lender_assessments,
    ledger_log
TO ndic_app;

-- Views are read-only for the app role
GRANT SELECT ON
    v_animal_health_trajectory,
    v_farm_monthly_productivity,
    v_regional_disease_profile,
    v_herd_finance_risk
TO ndic_app;

-- No UPDATE or DELETE granted to ndic_app — enforced at both DB and app layer
-- (triggers provide the last line of defence)
