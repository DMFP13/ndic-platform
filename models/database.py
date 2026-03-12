"""
SQLAlchemy 2.0 ORM models for the Nigerian Dairy Intelligence Consortium (NDIC).

Design principles:
- UUID primary keys throughout
- All timestamps in UTC
- Immutable audit columns (created_by, created_at, signature) on every domain table
- LedgerLog is append-only; enforced at DB level via trigger (see schema.sql) and app layer
- Ed25519 signatures stored as base64-encoded strings
- JSONB for structured sub-documents (treatments, vaccinations, coordinates)
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    String, Text, Float, Integer, Boolean, DateTime,
    ForeignKey, Enum as SAEnum, Index, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs

from models.enums import (
    UserRole, OrganizationType, AnimalBreed, AnimalSex, AnimalStatus,
    DiseaseType, AlertConfirmationStatus, AlertSeverity,
    QualityGrade, CollateralConfidence, LedgerEventType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(AsyncAttrs, DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Organization  (root of the ownership hierarchy)
# ---------------------------------------------------------------------------

class Organization(Base):
    """
    Legal entity that owns data submitted to the consortium.
    org_type determines which domain tables an organization can write to.
    """
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_type: Mapped[OrganizationType] = mapped_column(
        SAEnum(OrganizationType, name="organizationtype"), nullable=False
    )
    registration_number: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True
    )
    country: Mapped[str] = mapped_column(String(100), default="Nigeria", nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    lga: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="organization")
    farms: Mapped[List["Farm"]] = relationship("Farm", back_populates="organization")
    processor_intakes: Mapped[List["ProcessorIntake"]] = relationship(
        "ProcessorIntake", back_populates="processor_org"
    )
    disease_alerts: Mapped[List["DiseaseAlert"]] = relationship(
        "DiseaseAlert", back_populates="reporting_org"
    )
    lender_assessments: Mapped[List["LenderAssessment"]] = relationship(
        "LenderAssessment", back_populates="lender_org"
    )

    __table_args__ = (
        Index("ix_organizations_org_type", "org_type"),
        Index("ix_organizations_state", "state"),
        Index("ix_organizations_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.name!r} type={self.org_type}>"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    """
    Platform user.  role determines data-write permissions.
    public_key holds the user's Ed25519 public key (PEM) used to verify
    the signatures they attach to every record they submit.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole"), nullable=False
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # Ed25519 public key, PEM-encoded. Null until user registers their key pair.
    public_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", back_populates="users"
    )
    ledger_entries: Mapped[List["LedgerLog"]] = relationship(
        "LedgerLog", back_populates="actor"
    )

    __table_args__ = (
        Index("ix_users_role", "role"),
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"


# ---------------------------------------------------------------------------
# Farm
# ---------------------------------------------------------------------------

class Farm(Base):
    """
    A physical dairy farm owned by a FARM-type Organization.
    Farms are the root owner of Animals and HealthRecords.
    """
    __tablename__ = "farms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    farm_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    farm_name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    lga: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    established_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Audit
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="farms"
    )
    animals: Mapped[List["Animal"]] = relationship("Animal", back_populates="farm")
    health_records: Mapped[List["HealthRecord"]] = relationship(
        "HealthRecord", back_populates="farm"
    )
    intake_records: Mapped[List["ProcessorIntake"]] = relationship(
        "ProcessorIntake", back_populates="origin_farm"
    )
    lender_assessments: Mapped[List["LenderAssessment"]] = relationship(
        "LenderAssessment", back_populates="farm"
    )

    __table_args__ = (
        Index("ix_farms_organization_id_created_at", "organization_id", "created_at"),
        Index("ix_farms_state", "state"),
    )

    def __repr__(self) -> str:
        return f"<Farm id={self.id} code={self.farm_code!r}>"


# ---------------------------------------------------------------------------
# Animal
# ---------------------------------------------------------------------------

class Animal(Base):
    """
    Individual animal registered to a Farm.
    Once created, core identity fields (tag, breed, sex, farm) are immutable.
    Status transitions are tracked via LedgerLog events.
    """
    __tablename__ = "animals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    tag_number: Mapped[str] = mapped_column(String(100), nullable=False)
    breed: Mapped[AnimalBreed] = mapped_column(
        SAEnum(AnimalBreed, name="animalbreed"), nullable=False
    )
    sex: Mapped[AnimalSex] = mapped_column(
        SAEnum(AnimalSex, name="animalsex"), nullable=False
    )
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[AnimalStatus] = mapped_column(
        SAEnum(AnimalStatus, name="animalstatus"),
        default=AnimalStatus.ACTIVE, nullable=False,
    )
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Extensible metadata (e.g. RFID chip ID, sire/dam lineage)
    animal_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Audit + cryptographic proof
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    # Ed25519 signature of SHA-256(canonical_json(this record)), base64url-encoded
    signature: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    farm: Mapped["Farm"] = relationship("Farm", back_populates="animals")
    health_records: Mapped[List["HealthRecord"]] = relationship(
        "HealthRecord", back_populates="animal"
    )

    __table_args__ = (
        UniqueConstraint("farm_id", "tag_number", name="uq_animal_farm_tag"),
        Index("ix_animals_farm_id_created_at", "farm_id", "created_at"),
        Index("ix_animals_status", "status"),
        Index("ix_animals_breed", "breed"),
    )

    def __repr__(self) -> str:
        return f"<Animal id={self.id} tag={self.tag_number!r} farm={self.farm_id}>"


# ---------------------------------------------------------------------------
# HealthRecord
# ---------------------------------------------------------------------------

class HealthRecord(Base):
    """
    Daily or weekly observation submitted by a Farm user.
    Immutable once written — if a correction is needed, a new record is submitted
    with a note referencing the prior record ID. The LedgerLog chain preserves history.

    treatments: list of {drug_name, dose_mg, administered_at, administered_by, withdrawal_period_days}
    vaccinations: list of {vaccine_name, batch_number, administered_at, next_due}
    """
    __tablename__ = "health_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("animals.id", ondelete="RESTRICT"), nullable=False
    )
    # Denormalised for query performance — avoids a join on hot path
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    record_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    temperature_celsius: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 1=Normal, 2=Slightly lethargic, 3=Lethargic, 4=Distressed, 5=Critical
    behavior_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    milk_yield_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Body Condition Score: 1.0 (emaciated) – 5.0 (obese)
    body_condition_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    treatments: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    vaccinations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit + cryptographic proof
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    signature: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    animal: Mapped["Animal"] = relationship("Animal", back_populates="health_records")
    farm: Mapped["Farm"] = relationship("Farm", back_populates="health_records")

    __table_args__ = (
        Index("ix_health_records_farm_id_record_date", "farm_id", "record_date"),
        Index("ix_health_records_animal_id_record_date", "animal_id", "record_date"),
        CheckConstraint(
            "temperature_celsius IS NULL OR temperature_celsius BETWEEN 30 AND 45",
            name="ck_temperature_range",
        ),
        CheckConstraint(
            "behavior_score IS NULL OR behavior_score BETWEEN 1 AND 5",
            name="ck_behavior_score_range",
        ),
        CheckConstraint(
            "milk_yield_liters IS NULL OR milk_yield_liters >= 0",
            name="ck_milk_yield_non_negative",
        ),
        CheckConstraint(
            "body_condition_score IS NULL OR body_condition_score BETWEEN 1 AND 5",
            name="ck_bcs_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<HealthRecord id={self.id} animal={self.animal_id} "
            f"date={self.record_date.date()}>"
        )


# ---------------------------------------------------------------------------
# ProcessorIntake
# ---------------------------------------------------------------------------

class ProcessorIntake(Base):
    """
    Milk collection event recorded by a Processing Company.
    Links a processor to a source farm; price and quality are immutable once signed.
    total_amount_ngn is stored explicitly (not computed) so the signed value is
    the single source of truth even if price logic changes later.
    """
    __tablename__ = "processor_intakes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    processor_org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    origin_farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    intake_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    volume_liters: Mapped[float] = mapped_column(Float, nullable=False)
    quality_grade: Mapped[QualityGrade] = mapped_column(
        SAEnum(QualityGrade, name="qualitygrade"), nullable=False
    )
    fat_content_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    protein_content_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    somatic_cell_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temperature_at_receipt_celsius: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    price_per_liter_ngn: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount_ngn: Mapped[float] = mapped_column(Float, nullable=False)
    batch_reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit + cryptographic proof
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    signature: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    processor_org: Mapped["Organization"] = relationship(
        "Organization", back_populates="processor_intakes"
    )
    origin_farm: Mapped["Farm"] = relationship(
        "Farm", back_populates="intake_records"
    )

    __table_args__ = (
        Index(
            "ix_processor_intakes_org_id_intake_date",
            "processor_org_id", "intake_date",
        ),
        Index(
            "ix_processor_intakes_farm_id_intake_date",
            "origin_farm_id", "intake_date",
        ),
        CheckConstraint("volume_liters > 0", name="ck_volume_positive"),
        CheckConstraint("price_per_liter_ngn > 0", name="ck_price_positive"),
        CheckConstraint("total_amount_ngn > 0", name="ck_total_positive"),
        CheckConstraint(
            "fat_content_percent IS NULL OR fat_content_percent BETWEEN 0 AND 100",
            name="ck_fat_range",
        ),
        CheckConstraint(
            "protein_content_percent IS NULL OR protein_content_percent BETWEEN 0 AND 100",
            name="ck_protein_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProcessorIntake id={self.id} farm={self.origin_farm_id} "
            f"vol={self.volume_liters}L>"
        )


# ---------------------------------------------------------------------------
# DiseaseAlert
# ---------------------------------------------------------------------------

class DiseaseAlert(Base):
    """
    Outbreak or disease surveillance report submitted by a Government Agency.
    confirmation_status progresses: suspected → confirmed | false_alarm → resolved.
    Status updates are new LedgerLog entries; the original record is never mutated.
    """
    __tablename__ = "disease_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reporting_org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    alert_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    disease_type: Mapped[DiseaseType] = mapped_column(
        SAEnum(DiseaseType, name="diseasetype"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    lga: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # {lat: float, lng: float} — epicentre of outbreak
    coordinates: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    affected_animal_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    affected_farm_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confirmation_status: Mapped[AlertConfirmationStatus] = mapped_column(
        SAEnum(AlertConfirmationStatus, name="alertconfirmationstatus"),
        default=AlertConfirmationStatus.SUSPECTED,
        nullable=False,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity, name="alertseverity"),
        default=AlertSeverity.LOW,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # {quarantine_zone, movement_restriction, vaccination_campaign, ...}
    response_actions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Audit + cryptographic proof
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    signature: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    reporting_org: Mapped["Organization"] = relationship(
        "Organization", back_populates="disease_alerts"
    )

    __table_args__ = (
        Index(
            "ix_disease_alerts_org_id_alert_date",
            "reporting_org_id", "alert_date",
        ),
        Index(
            "ix_disease_alerts_state_disease_type",
            "state", "disease_type",
        ),
        Index("ix_disease_alerts_confirmation_status", "confirmation_status"),
        Index("ix_disease_alerts_severity", "severity"),
        CheckConstraint(
            "affected_animal_count IS NULL OR affected_animal_count >= 0",
            name="ck_affected_animals_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DiseaseAlert id={self.id} type={self.disease_type} "
            f"state={self.state!r} status={self.confirmation_status}>"
        )


# ---------------------------------------------------------------------------
# LenderAssessment
# ---------------------------------------------------------------------------

class LenderAssessment(Base):
    """
    Herd valuation and collateral risk assessment submitted by a Finance Institution.
    supporting_data is a JSONB snapshot of the data inputs used at assessment time
    (health scores, milk yield trends, processor prices) so the assessment is
    self-contained even if underlying records change.
    """
    __tablename__ = "lender_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lender_org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    herd_count: Mapped[int] = mapped_column(Integer, nullable=False)
    herd_valuation_ngn: Mapped[float] = mapped_column(Float, nullable=False)
    # 0 = no risk, 100 = maximum risk
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    collateral_confidence: Mapped[CollateralConfidence] = mapped_column(
        SAEnum(CollateralConfidence, name="collateralconfidence"), nullable=False
    )
    loan_amount_requested_ngn: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    loan_term_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    methodology_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Audit + cryptographic proof
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    signature: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    lender_org: Mapped["Organization"] = relationship(
        "Organization", back_populates="lender_assessments"
    )
    farm: Mapped["Farm"] = relationship("Farm", back_populates="lender_assessments")

    __table_args__ = (
        Index(
            "ix_lender_assessments_org_id_date",
            "lender_org_id", "assessment_date",
        ),
        Index(
            "ix_lender_assessments_farm_id_date",
            "farm_id", "assessment_date",
        ),
        CheckConstraint(
            "risk_score BETWEEN 0 AND 100", name="ck_risk_score_range"
        ),
        CheckConstraint("herd_count > 0", name="ck_herd_count_positive"),
        CheckConstraint(
            "herd_valuation_ngn > 0", name="ck_valuation_positive"
        ),
        CheckConstraint(
            "loan_amount_requested_ngn IS NULL OR loan_amount_requested_ngn > 0",
            name="ck_loan_amount_positive",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<LenderAssessment id={self.id} farm={self.farm_id} "
            f"risk={self.risk_score} confidence={self.collateral_confidence}>"
        )


# ---------------------------------------------------------------------------
# LedgerLog  (append-only)
# ---------------------------------------------------------------------------

class LedgerLog(Base):
    """
    Immutable, cryptographically chained audit ledger.

    Every write to a domain table (animals, health_records, processor_intakes,
    disease_alerts, lender_assessments) MUST produce a corresponding LedgerLog row.

    Hash chain:
      payload_hash   = SHA-256(canonical_json(target record))
      chain_input    = payload_hash + (previous_hash or "GENESIS")
      signature      = Ed25519_sign(actor_private_key, chain_input)
      entry_hash     = SHA-256(id + payload_hash + signature)   ← stored as previous_hash of NEXT entry

    Immutability is enforced at two levels:
      1. PostgreSQL trigger (see schema.sql): raises exception on UPDATE/DELETE
      2. Application layer: no ORM update path exposed; only INSERT is used

    ip_address and user_agent are stored for forensic purposes but are NOT
    exposed in normal API responses.
    """
    __tablename__ = "ledger_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[LedgerEventType] = mapped_column(
        SAEnum(LedgerEventType, name="ledgereventtype"), nullable=False
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    actor_org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    target_table: Mapped[str] = mapped_column(String(100), nullable=False)
    target_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    # SHA-256 hex digest of the canonical JSON of the target record
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Ed25519 signature of (payload_hash ‖ previous_hash), base64url-encoded
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    # SHA-256 of the previous ledger entry for this actor/table combination
    previous_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Forensic metadata — not surfaced in public API
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    actor: Mapped["User"] = relationship("User", back_populates="ledger_entries")

    __table_args__ = (
        Index("ix_ledger_log_actor_id_created_at", "actor_id", "created_at"),
        Index("ix_ledger_log_actor_org_id_created_at", "actor_org_id", "created_at"),
        Index("ix_ledger_log_target_record_id", "target_record_id"),
        Index("ix_ledger_log_event_type_created_at", "event_type", "created_at"),
        Index("ix_ledger_log_payload_hash", "payload_hash"),
    )

    def __repr__(self) -> str:
        return (
            f"<LedgerLog id={self.id} event={self.event_type} "
            f"actor={self.actor_id} target={self.target_record_id}>"
        )
