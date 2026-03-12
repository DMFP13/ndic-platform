"""
Pydantic v2 request/response schemas for the NDIC platform.

Naming convention:
  Create<Entity>   — inbound POST body (caller provides signature)
  <Entity>Response — outbound representation (read from DB)
  <Entity>Summary  — lightweight list-view representation

All UUIDs are str in JSON (serialised by Pydantic automatically).
Timestamps are ISO-8601 strings with UTC timezone (Z suffix).
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Optional, List, Any

from pydantic import (
    BaseModel,
    Field,
    EmailStr,
    field_validator,
    model_validator,
    ConfigDict,
)

from models.enums import (
    UserRole,
    OrganizationType,
    AnimalBreed,
    AnimalSex,
    AnimalStatus,
    DiseaseType,
    AlertConfirmationStatus,
    AlertSeverity,
    QualityGrade,
    CollateralConfidence,
    LedgerEventType,
)


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class NDICBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# ---------------------------------------------------------------------------
# Sub-document schemas (used inside JSONB fields)
# ---------------------------------------------------------------------------

class TreatmentEntry(NDICBase):
    drug_name: str = Field(..., max_length=200)
    dose_mg: float = Field(..., gt=0)
    route: Optional[str] = Field(None, max_length=50)   # oral, IV, IM, SC
    administered_at: datetime
    administered_by: str = Field(..., max_length=255)    # vet name or licence number
    withdrawal_period_days: Optional[int] = Field(None, ge=0)
    batch_number: Optional[str] = Field(None, max_length=100)


class VaccinationEntry(NDICBase):
    vaccine_name: str = Field(..., max_length=200)
    batch_number: Optional[str] = Field(None, max_length=100)
    dose_ml: Optional[float] = Field(None, gt=0)
    administered_at: datetime
    administered_by: str = Field(..., max_length=255)
    next_due: Optional[datetime] = None


class GeoCoordinates(NDICBase):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class CreateOrganization(NDICBase):
    name: str = Field(..., max_length=255)
    org_type: OrganizationType
    registration_number: Optional[str] = Field(None, max_length=100)
    country: str = Field("Nigeria", max_length=100)
    state: str = Field(..., max_length=100)
    lga: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)


class OrganizationResponse(CreateOrganization):
    id: uuid.UUID
    is_active: bool
    created_at: datetime


class OrganizationSummary(NDICBase):
    id: uuid.UUID
    name: str
    org_type: OrganizationType
    state: str
    is_active: bool


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class CreateUser(NDICBase):
    email: EmailStr
    full_name: str = Field(..., max_length=255)
    password: str = Field(..., min_length=12, description="Plain-text; hashed before storage")
    role: UserRole
    organization_id: Optional[uuid.UUID] = None
    # Ed25519 public key, PEM-encoded.  Must be registered before signing records.
    public_key: Optional[str] = Field(None, description="Ed25519 public key (PEM)")


class UserResponse(NDICBase):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    organization_id: Optional[uuid.UUID]
    public_key: Optional[str]
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime


# ---------------------------------------------------------------------------
# Farm
# ---------------------------------------------------------------------------

class CreateFarm(NDICBase):
    organization_id: uuid.UUID
    farm_code: str = Field(..., max_length=50, pattern=r"^[A-Z0-9_-]+$")
    farm_name: str = Field(..., max_length=255)
    state: str = Field(..., max_length=100)
    lga: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    total_capacity: Optional[int] = Field(None, gt=0)
    established_date: Optional[datetime] = None


class FarmResponse(NDICBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    farm_code: str
    farm_name: str
    state: str
    lga: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    total_capacity: Optional[int]
    established_date: Optional[datetime]
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime


class FarmSummary(NDICBase):
    id: uuid.UUID
    farm_code: str
    farm_name: str
    state: str
    total_capacity: Optional[int]
    is_active: bool


# ---------------------------------------------------------------------------
# Animal
# ---------------------------------------------------------------------------

class CreateAnimal(NDICBase):
    farm_id: uuid.UUID
    tag_number: str = Field(..., max_length=100)
    breed: AnimalBreed
    sex: AnimalSex
    date_of_birth: Optional[datetime] = None
    weight_kg: Optional[float] = Field(None, gt=0)
    acquired_at: datetime
    notes: Optional[str] = None
    animal_metadata: Optional[dict] = None
    # Caller MUST sign SHA-256(canonical_json(this payload)) with their Ed25519 key
    signature: str = Field(..., description="Ed25519 signature (base64url) of record hash")


class AnimalResponse(NDICBase):
    id: uuid.UUID
    farm_id: uuid.UUID
    tag_number: str
    breed: AnimalBreed
    sex: AnimalSex
    date_of_birth: Optional[datetime]
    weight_kg: Optional[float]
    status: AnimalStatus
    acquired_at: datetime
    notes: Optional[str]
    animal_metadata: Optional[dict]
    created_by: uuid.UUID
    created_at: datetime
    signature: str


class AnimalSummary(NDICBase):
    id: uuid.UUID
    tag_number: str
    breed: AnimalBreed
    sex: AnimalSex
    status: AnimalStatus
    farm_id: uuid.UUID


# ---------------------------------------------------------------------------
# HealthRecord
# ---------------------------------------------------------------------------

class CreateHealthRecord(NDICBase):
    animal_id: uuid.UUID
    farm_id: uuid.UUID
    record_date: datetime
    temperature_celsius: Optional[float] = Field(
        None, ge=30, le=45,
        description="Normal bovine range: 38.0–39.5°C",
    )
    behavior_score: Optional[int] = Field(
        None, ge=1, le=5,
        description="1=Normal … 5=Critical",
    )
    milk_yield_liters: Optional[float] = Field(None, ge=0)
    body_condition_score: Optional[float] = Field(
        None, ge=1.0, le=5.0,
        description="BCS 1=emaciated, 5=obese; target 2.5–3.5 for dairy",
    )
    treatments: Optional[List[TreatmentEntry]] = None
    vaccinations: Optional[List[VaccinationEntry]] = None
    notes: Optional[str] = None
    signature: str = Field(..., description="Ed25519 signature (base64url) of record hash")

    @field_validator("record_date")
    @classmethod
    def record_date_not_future(cls, v: datetime) -> datetime:
        from datetime import timezone
        if v > datetime.now(timezone.utc):
            raise ValueError("record_date cannot be in the future")
        return v


class HealthRecordResponse(NDICBase):
    id: uuid.UUID
    animal_id: uuid.UUID
    farm_id: uuid.UUID
    record_date: datetime
    temperature_celsius: Optional[float]
    behavior_score: Optional[int]
    milk_yield_liters: Optional[float]
    body_condition_score: Optional[float]
    treatments: Optional[List[TreatmentEntry]]
    vaccinations: Optional[List[VaccinationEntry]]
    notes: Optional[str]
    created_by: uuid.UUID
    created_at: datetime
    signature: str


# ---------------------------------------------------------------------------
# ProcessorIntake
# ---------------------------------------------------------------------------

class CreateProcessorIntake(NDICBase):
    processor_org_id: uuid.UUID
    origin_farm_id: uuid.UUID
    intake_date: datetime
    volume_liters: float = Field(..., gt=0)
    quality_grade: QualityGrade
    fat_content_percent: Optional[float] = Field(None, ge=0, le=100)
    protein_content_percent: Optional[float] = Field(None, ge=0, le=100)
    somatic_cell_count: Optional[int] = Field(
        None, ge=0,
        description="Cells per mL; <200,000 = Grade A threshold",
    )
    temperature_at_receipt_celsius: Optional[float] = Field(
        None, description="Target: ≤4°C at receipt"
    )
    price_per_liter_ngn: float = Field(..., gt=0)
    total_amount_ngn: float = Field(..., gt=0)
    batch_reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    signature: str = Field(..., description="Ed25519 signature (base64url) of record hash")

    @model_validator(mode="after")
    def validate_total_matches_unit_price(self) -> "CreateProcessorIntake":
        expected = round(self.volume_liters * self.price_per_liter_ngn, 2)
        if abs(self.total_amount_ngn - expected) > 1.0:   # ±₦1 rounding tolerance
            raise ValueError(
                f"total_amount_ngn ({self.total_amount_ngn}) does not match "
                f"volume × price ({expected})"
            )
        return self


class ProcessorIntakeResponse(NDICBase):
    id: uuid.UUID
    processor_org_id: uuid.UUID
    origin_farm_id: uuid.UUID
    intake_date: datetime
    volume_liters: float
    quality_grade: QualityGrade
    fat_content_percent: Optional[float]
    protein_content_percent: Optional[float]
    somatic_cell_count: Optional[int]
    temperature_at_receipt_celsius: Optional[float]
    price_per_liter_ngn: float
    total_amount_ngn: float
    batch_reference: Optional[str]
    notes: Optional[str]
    created_by: uuid.UUID
    created_at: datetime
    signature: str


# ---------------------------------------------------------------------------
# DiseaseAlert
# ---------------------------------------------------------------------------

class CreateDiseaseAlert(NDICBase):
    reporting_org_id: uuid.UUID
    alert_date: datetime
    disease_type: DiseaseType
    state: str = Field(..., max_length=100)
    lga: Optional[str] = Field(None, max_length=100)
    coordinates: Optional[GeoCoordinates] = None
    affected_animal_count: Optional[int] = Field(None, ge=0)
    affected_farm_count: Optional[int] = Field(None, ge=0)
    severity: AlertSeverity = AlertSeverity.LOW
    description: Optional[str] = None
    # {quarantine_zone, movement_restriction, vaccination_campaign, sample_ids, ...}
    response_actions: Optional[dict] = None
    signature: str = Field(..., description="Ed25519 signature (base64url) of record hash")


class DiseaseAlertResponse(NDICBase):
    id: uuid.UUID
    reporting_org_id: uuid.UUID
    alert_date: datetime
    disease_type: DiseaseType
    state: str
    lga: Optional[str]
    coordinates: Optional[GeoCoordinates]
    affected_animal_count: Optional[int]
    affected_farm_count: Optional[int]
    confirmation_status: AlertConfirmationStatus
    severity: AlertSeverity
    description: Optional[str]
    response_actions: Optional[dict]
    resolved_at: Optional[datetime]
    created_by: uuid.UUID
    created_at: datetime
    signature: str


class DiseaseAlertSummary(NDICBase):
    id: uuid.UUID
    disease_type: DiseaseType
    state: str
    severity: AlertSeverity
    confirmation_status: AlertConfirmationStatus
    alert_date: datetime


# ---------------------------------------------------------------------------
# LenderAssessment
# ---------------------------------------------------------------------------

class CreateLenderAssessment(NDICBase):
    lender_org_id: uuid.UUID
    farm_id: uuid.UUID
    assessment_date: datetime
    herd_count: int = Field(..., gt=0)
    herd_valuation_ngn: float = Field(..., gt=0)
    risk_score: float = Field(
        ..., ge=0, le=100,
        description="0 = no risk, 100 = maximum risk",
    )
    collateral_confidence: CollateralConfidence
    loan_amount_requested_ngn: Optional[float] = Field(None, gt=0)
    loan_term_months: Optional[int] = Field(None, gt=0, le=360)
    methodology_notes: Optional[str] = None
    # Snapshot of data inputs used — self-contained for audit purposes
    supporting_data: Optional[dict] = None
    signature: str = Field(..., description="Ed25519 signature (base64url) of record hash")


class LenderAssessmentResponse(NDICBase):
    id: uuid.UUID
    lender_org_id: uuid.UUID
    farm_id: uuid.UUID
    assessment_date: datetime
    herd_count: int
    herd_valuation_ngn: float
    risk_score: float
    collateral_confidence: CollateralConfidence
    loan_amount_requested_ngn: Optional[float]
    loan_term_months: Optional[int]
    methodology_notes: Optional[str]
    created_by: uuid.UUID
    created_at: datetime
    signature: str


# ---------------------------------------------------------------------------
# LedgerLog
# ---------------------------------------------------------------------------

class LedgerEntryResponse(NDICBase):
    """
    Public-facing representation of a ledger entry.
    ip_address and user_agent are intentionally omitted (forensic use only).
    """
    id: uuid.UUID
    event_type: LedgerEventType
    actor_id: uuid.UUID
    actor_org_id: Optional[uuid.UUID]
    target_table: str
    target_record_id: uuid.UUID
    payload_hash: str = Field(..., description="SHA-256 hex of canonical record JSON")
    signature: str = Field(..., description="Ed25519 signature over (payload_hash ‖ previous_hash)")
    previous_hash: Optional[str] = Field(
        None, description="Links this entry to the previous one in the chain"
    )
    created_at: datetime


class LedgerVerificationResult(BaseModel):
    """
    Result of verifying a single ledger entry's signature and chain link.
    Actual cryptographic verification is performed in the service layer
    using the actor's registered public key.
    """
    entry_id: uuid.UUID
    is_signature_valid: bool
    is_chain_valid: bool
    verification_message: str
    verified_at: datetime
    verifier_id: uuid.UUID   # the admin user who ran the verification


# ---------------------------------------------------------------------------
# Aggregation / read-model schemas
# ---------------------------------------------------------------------------

class AnimalHealthTrajectory(NDICBase):
    """Lifetime health profile for a single animal — aggregation view."""
    animal_id: uuid.UUID
    tag_number: str
    breed: AnimalBreed
    farm_id: uuid.UUID
    total_records: int
    avg_temperature_celsius: Optional[float]
    avg_milk_yield_liters: Optional[float]
    avg_behavior_score: Optional[float]
    avg_body_condition_score: Optional[float]
    first_record_date: Optional[datetime]
    last_record_date: Optional[datetime]


class FarmProductivitySummary(NDICBase):
    """Yield + cost trend for a farm — aggregation view."""
    farm_id: uuid.UUID
    farm_code: str
    period_start: datetime
    period_end: datetime
    total_milk_yield_liters: float
    avg_daily_yield_per_cow_liters: Optional[float]
    total_intake_revenue_ngn: float
    active_animal_count: int
    health_records_count: int


class RegionalDiseaseProfile(NDICBase):
    """Disease surveillance summary for a state — aggregation view."""
    state: str
    period_start: datetime
    period_end: datetime
    total_alerts: int
    confirmed_alerts: int
    active_alerts: int
    disease_breakdown: dict   # {disease_type: count}
    highest_severity: Optional[AlertSeverity]


class HerdFinanceRisk(NDICBase):
    """Collateral confidence summary for lender decision support — aggregation view."""
    farm_id: uuid.UUID
    farm_code: str
    latest_assessment_date: Optional[datetime]
    latest_herd_valuation_ngn: Optional[float]
    latest_risk_score: Optional[float]
    latest_collateral_confidence: Optional[CollateralConfidence]
    assessment_count: int
    avg_risk_score: Optional[float]
