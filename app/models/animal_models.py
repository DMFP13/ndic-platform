"""
Cow Passport ORM Models
────────────────────────
New tables:
  sensor_readings  — time-series sensor data per animal (from IoT devices or mock)
  vet_records      — structured veterinary records (vaccination, treatment, disease, note, etc.)
  animal_photos    — photo storage metadata (local filesystem or S3)

All tables share the Base from models/database.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Float, Integer, Boolean, DateTime,
    ForeignKey, Index, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base, utc_now


# ---------------------------------------------------------------------------
# Sensor Reading
# ---------------------------------------------------------------------------

class SensorReading(Base):
    """
    One time-stamped sensor snapshot for a single animal.
    All metric fields are optional — only the sensors physically installed
    on the animal will have values.  is_mock=True flags generated data.
    """
    __tablename__ = "sensor_readings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("animals.id", ondelete="CASCADE"), nullable=False
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    temperature_celsius: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    milk_yield_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heart_rate_bpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 0–100 dimensionless activity index (steps + rumination composite)
    activity_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feed_intake_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    device_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_sensor_readings_animal_id_timestamp", "animal_id", "timestamp"),
        Index("ix_sensor_readings_farm_id_timestamp", "farm_id", "timestamp"),
        CheckConstraint(
            "temperature_celsius IS NULL OR temperature_celsius BETWEEN 30 AND 45",
            name="ck_sr_temp_range",
        ),
        CheckConstraint(
            "activity_index IS NULL OR activity_index BETWEEN 0 AND 100",
            name="ck_sr_activity_range",
        ),
    )

    def __repr__(self) -> str:
        return f"<SensorReading animal={self.animal_id} ts={self.timestamp}>"


# ---------------------------------------------------------------------------
# Vet Record
# ---------------------------------------------------------------------------

VET_RECORD_TYPES = (
    "vaccination",
    "treatment",
    "disease",
    "weight_check",
    "pregnancy_check",
    "calving",
    "note",
    "other",
)


class VetRecord(Base):
    """
    A single veterinary event for an animal.
    record_type determines which optional fields are relevant:
      vaccination   → vaccine_name, vaccine_batch, next_due_date
      treatment     → drug_name, dosage, route, duration_days, withdrawal_period_days
      disease       → disease_name, outcome
      weight_check  → uses description for weight value
      calving       → description for calf info
      note/other    → free-text description + notes
    """
    __tablename__ = "vet_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("animals.id", ondelete="CASCADE"), nullable=False
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False
    )

    record_type: Mapped[str] = mapped_column(String(50), nullable=False)
    record_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Treatment fields
    drug_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dosage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    withdrawal_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Vaccination fields
    vaccine_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vaccine_batch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    next_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Disease fields
    disease_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Vet identity
    vet_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vet_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # List of AnimalPhoto IDs attached to this record
    photo_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_vet_records_animal_id_record_date", "animal_id", "record_date"),
        Index("ix_vet_records_farm_id_record_type", "farm_id", "record_type"),
    )

    def __repr__(self) -> str:
        return f"<VetRecord {self.record_type} animal={self.animal_id} date={self.record_date.date()}>"


# ---------------------------------------------------------------------------
# Animal Photo
# ---------------------------------------------------------------------------

class AnimalPhoto(Base):
    """
    Metadata for a photo attached to an animal passport.
    Actual bytes are stored at storage_key on local filesystem (dev)
    or in S3 (production).  Switch via STORAGE_BACKEND env var.
    """
    __tablename__ = "animal_photos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("animals.id", ondelete="CASCADE"), nullable=False
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False
    )

    # Relative path from LOCAL_UPLOAD_DIR or S3 key
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ML individual-identification results
    ml_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ml_matched_animal_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ml_processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_animal_photos_animal_id_uploaded_at", "animal_id", "uploaded_at"),
    )

    def __repr__(self) -> str:
        return f"<AnimalPhoto animal={self.animal_id} primary={self.is_primary}>"
