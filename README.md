# NDIC Platform — Data Models & Schema

Nigerian Dairy Intelligence Consortium
A multi-party cryptographic data system for Nigeria's dairy sector.

---

## File Map

```
ndic/
├── config.py            Database engine, session factory, all settings
├── schema.sql           PostgreSQL DDL — copy-paste or baseline Alembic migration
└── models/
    ├── __init__.py
    ├── enums.py         All Enum types (UserRole, AnimalBreed, DiseaseType, …)
    ├── database.py      SQLAlchemy 2.0 async ORM models
    └── schemas.py       Pydantic v2 request/response schemas
```

---

## Data Relationships

```
Organization (1) ──────── (N) User
     │
     │ org_type=farm
     └──── (N) Farm (1) ──────── (N) Animal (1) ──────── (N) HealthRecord
                 │
                 │ ◄── (N) ProcessorIntake   (processor org → farm)
                 │ ◄── (N) LenderAssessment  (lender org → farm)
                 │
Organization (org_type=government_agency)
     └──── (N) DiseaseAlert

Every write to any domain table ──► LedgerLog (append-only)
```

### Ownership by actor

| Actor | Writes to |
|---|---|
| Farm user | `animals`, `health_records` |
| Processor user | `processor_intakes` |
| Government user | `disease_alerts` |
| Lender user | `lender_assessments` |
| ARPEXAS admin | `organizations`, `users`, `farms` (setup only) |

---

## Immutability Strategy

The platform enforces immutability at **three layers**:

### Layer 1 — PostgreSQL triggers (schema.sql)

`tg_ledger_log_no_update` and `tg_ledger_log_no_delete` fire before any
`UPDATE` or `DELETE` on `ledger_log` and raise a `restrict_violation`
exception. No application bug or misconfigured ORM can silently mutate a
ledger entry.

`tg_<table>_audit_immutable` prevents overwriting `created_by`,
`created_at`, and `signature` on all domain tables.

### Layer 2 — Application layer (service functions)

The ORM models expose **no update path** for domain records. Service
functions only call `session.add(new_record)`. There is no
`session.execute(update(...))` path for domain data.

### Layer 3 — Cryptographic chaining (LedgerLog)

Each `LedgerLog` row carries:

```
payload_hash   = SHA-256( canonical_json(target_record) )
chain_input    = payload_hash || (previous_hash OR "GENESIS")
signature      = Ed25519_sign(actor_private_key, chain_input)
```

Tamper detection: re-computing `payload_hash` over the target record and
verifying the Ed25519 signature against the actor's stored `public_key`
(in `users.public_key`) proves both **who wrote** the record and that
**the record has not changed** since it was signed.

**Correction workflow** (no mutations, ever):
Submit a new record with `notes` referencing the original record ID.
The original remains in the ledger. Both records appear in the animal's
health trajectory, and the ledger chain for the actor links both entries.

---

## Key Design Decisions

### UUID primary keys
All tables use `UUID` (v4) primary keys. This allows records to be
pre-assigned IDs client-side before insertion, enables sharding, and
prevents enumeration attacks.

### JSONB for sub-documents
`treatments`, `vaccinations`, `coordinates`, and `supporting_data` are
stored as JSONB. This avoids premature normalisation of sparse, evolving
structures while remaining queryable with PostgreSQL operators.

### Denormalised `farm_id` on `health_records`
`health_records.farm_id` duplicates `animals.farm_id`. This is intentional:
farm-level time-series queries (`WHERE farm_id = ? AND record_date > ?`)
avoid a join on the hot analytical path, and the composite index
`(farm_id, record_date)` covers them efficiently.

### `supporting_data` snapshot on `lender_assessments`
When a lender submits a collateral assessment they include a JSONB snapshot
of the data they relied on (health score averages, milk yield trends,
processor prices). Even if underlying records are superseded by new
submissions, the assessment remains self-contained and auditable.

### No foreign key from `ledger_log.target_record_id`
`target_record_id` is a bare UUID, not a FK. This is intentional: a single
ledger table must reference rows across multiple domain tables. `target_table`
identifies which table the ID belongs to.

---

## Quick Start

### 1. Create the database and apply the schema

```bash
psql -U postgres -c "CREATE DATABASE ndic;"
psql -U postgres -d ndic -f schema.sql
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set DB_PASSWORD, JWT_SECRET_KEY, etc.
```

### 3. Install dependencies

```bash
pip install sqlalchemy[asyncio] asyncpg pydantic pydantic-settings
```

### 4. Run Alembic migrations (alternative to schema.sql)

```bash
pip install alembic psycopg2-binary
alembic init alembic
# In alembic/env.py, import Base from models.database and set target_metadata = Base.metadata
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_HOST` | No | `localhost` | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |
| `DB_NAME` | No | `ndic` | Database name |
| `DB_USER` | No | `ndic_app` | Database user |
| `DB_PASSWORD` | **Yes** | — | Database password |
| `DB_SSL_MODE` | No | `require` | `require` for RDS, `disable` for local |
| `JWT_SECRET_KEY` | **Yes (prod)** | — | HS256 signing secret |
| `PLATFORM_KEY_SECRET_ARN` | Prod | — | AWS Secrets Manager ARN for platform Ed25519 key |
| `ENVIRONMENT` | No | `production` | `local` \| `staging` \| `production` |
| `DEBUG` | No | `false` | Enables SQL echo; forbidden in production |
| `AWS_REGION` | No | `eu-west-1` | AWS region for RDS IAM + Secrets Manager |
| `USE_RDS_IAM_AUTH` | No | `false` | Use IAM token instead of password |
