"""
Cow Passport API  — Animal Profiles, Sensor History, Vet Records, Photos
─────────────────────────────────────────────────────────────────────────
Endpoints:

  GET    /farms/{farm_id}/animals/{animal_id}/passport
  GET    /farms/{farm_id}/animals/{animal_id}/sensor-history
  GET    /farms/{farm_id}/animals/{animal_id}/vet-records
  POST   /farms/{farm_id}/animals/{animal_id}/vet-records         (write roles)
  PUT    /farms/{farm_id}/animals/{animal_id}/vet-records/{id}    (write roles)
  DELETE /farms/{farm_id}/animals/{animal_id}/vet-records/{id}    (write roles)
  GET    /farms/{farm_id}/animals/{animal_id}/photos
  POST   /farms/{farm_id}/animals/{animal_id}/photos              (write roles)
  DELETE /farms/{farm_id}/animals/{animal_id}/photos/{photo_id}   (write roles)
  POST   /animals/identify-from-photo                             (ML stub)

Write roles: farm_manager, farm_admin, farm_vet
Read roles:  all authenticated roles (farm + lender + govt + arpexas_admin)

All endpoints fall back to realistic mock data when the DB tables do not
yet exist (e.g. before the migration has been applied).  The mock flag is
clearly labelled in every response.
"""

from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.middleware.access_control import get_current_user
from app.services.storage_service import delete_photo, get_photo_url, save_photo

router = APIRouter(tags=["animals"])

# ── Role constants ────────────────────────────────────────────────────────────

WRITE_ROLES = {"farm_manager", "farm_admin", "farm_vet"}
READ_ROLES = WRITE_ROLES | {
    "processor_analyst", "processor_commercial",
    "govt_analyst", "govt_admin",
    "lender_analyst", "arpexas_admin",
}


def _require_write(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Write access requires a farm role.")
    return user


def _require_read(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in READ_ROLES:
        raise HTTPException(status_code=403, detail="Access denied.")
    return user


# ── Mock data generators ──────────────────────────────────────────────────────

def _mock_sensor_series(animal_id: str, days: int = 30) -> list[dict]:
    """Generate a deterministic 30-day time-series of sensor readings."""
    rng = random.Random(animal_id)
    base_temp = rng.uniform(38.1, 38.6)
    base_weight = rng.uniform(320, 480)
    base_milk = rng.uniform(8.0, 14.0)
    base_hr = rng.randint(58, 72)
    base_feed = rng.uniform(12.0, 18.0)

    now = datetime.now(timezone.utc)
    readings = []
    for i in range(days * 2):          # twice-daily readings
        ts = now - timedelta(hours=(days * 24) - i * 12)
        noise = rng.gauss(0, 1)
        readings.append({
            "timestamp": ts.isoformat(),
            "temperature_celsius": round(base_temp + noise * 0.15 + math.sin(i / 6) * 0.2, 2),
            "weight_kg": round(base_weight + noise * 0.8 + i * 0.03, 1),
            "milk_yield_liters": round(max(0, base_milk + noise * 0.4 + math.sin(i / 8) * 0.6), 2),
            "heart_rate_bpm": max(40, int(base_hr + noise * 2)),
            "activity_index": round(max(0, min(100, 55 + noise * 8 + math.sin(i / 4) * 12)), 1),
            "feed_intake_kg": round(max(0, base_feed + noise * 0.5), 2),
            "is_mock": True,
            "device_id": "MOCK-SENSOR-001",
        })
    return readings


def _mock_current_snapshot(animal_id: str) -> dict:
    """Latest sensor snapshot (most recent reading)."""
    series = _mock_sensor_series(animal_id, days=1)
    snap = series[-1].copy()
    snap["as_of"] = snap.pop("timestamp")
    snap["is_mock"] = True
    return snap


def _mock_vet_records(animal_id: str) -> list[dict]:
    rng = random.Random(animal_id + "vet")
    now = datetime.now(timezone.utc)
    records = [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{animal_id}-vac1")),
            "record_type": "vaccination",
            "record_date": (now - timedelta(days=rng.randint(60, 180))).date().isoformat(),
            "title": "FMD Vaccination",
            "description": "Annual foot-and-mouth disease vaccination",
            "vaccine_name": "FOTIVAX®",
            "vaccine_batch": f"FV{rng.randint(1000,9999)}",
            "next_due_date": (now + timedelta(days=rng.randint(180, 365))).date().isoformat(),
            "vet_name": "Dr. Musa Ibrahim",
            "vet_contact": "musa.ibrahim@ndic.ng",
            "notes": None,
            "is_mock": True,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{animal_id}-vac2")),
            "record_type": "vaccination",
            "record_date": (now - timedelta(days=rng.randint(30, 60))).date().isoformat(),
            "title": "Brucellosis Vaccination",
            "description": "S19 Brucella abortus vaccine — heifers only",
            "vaccine_name": "Strain 19",
            "vaccine_batch": f"B{rng.randint(100,999)}",
            "next_due_date": None,
            "vet_name": "Dr. Adaeze Okonkwo",
            "vet_contact": "adaeze.okonkwo@ndic.ng",
            "notes": "Single dose, permanent immunity in adults.",
            "is_mock": True,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{animal_id}-tx1")),
            "record_type": "treatment",
            "record_date": (now - timedelta(days=rng.randint(7, 30))).date().isoformat(),
            "title": "Oxytetracycline — respiratory infection",
            "description": "Suspected respiratory infection following herd movement.",
            "drug_name": "Oxytetracycline LA 200",
            "dosage": "20 mg/kg",
            "route": "IM",
            "duration_days": 3,
            "withdrawal_period_days": 28,
            "vet_name": "Dr. Musa Ibrahim",
            "notes": "Monitor temperature daily for 5 days.",
            "is_mock": True,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{animal_id}-wt1")),
            "record_type": "weight_check",
            "record_date": (now - timedelta(days=rng.randint(14, 45))).date().isoformat(),
            "title": "Routine Weight Check",
            "description": f"Weight recorded: {rng.randint(340, 450)} kg",
            "vet_name": "Farm Manager",
            "notes": None,
            "is_mock": True,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{animal_id}-note1")),
            "record_type": "note",
            "record_date": (now - timedelta(days=rng.randint(1, 14))).date().isoformat(),
            "title": "Behavioural observation",
            "description": "Animal appeared slightly lethargic at morning check. Appetite normal. No temperature elevation. Monitoring.",
            "vet_name": "Farm Manager",
            "notes": None,
            "is_mock": True,
        },
    ]
    records.sort(key=lambda r: r["record_date"], reverse=True)
    return records


def _mock_passport(farm_id: str, animal_id: str) -> dict:
    rng = random.Random(animal_id)
    breeds = ["Bunaji (White Fulani)", "Friesian", "Friesian × Bunaji", "Rahaji", "Sokoto Gudali"]
    colours = ["White", "Black and white", "Fawn", "Brown", "Brown and white"]
    statuses = ["healthy", "at_risk", "healthy", "healthy", "critical"]
    dob = datetime.now(timezone.utc) - timedelta(days=rng.randint(365 * 2, 365 * 8))

    return {
        "is_mock": True,
        "animal_id": animal_id,
        "farm_id": farm_id,
        "identity": {
            "tag": f"NG-{rng.randint(100,999)}",
            "microchip": f"MC{rng.randint(10000000,99999999)}",
            "breed": rng.choice(breeds),
            "sex": rng.choice(["Female", "Female", "Female", "Male"]),
            "date_of_birth": dob.date().isoformat(),
            "age_months": int((datetime.now(timezone.utc) - dob).days / 30.44),
            "colour_markings": rng.choice(colours),
            "dam_tag": f"NG-{rng.randint(50,99)}",
            "sire_tag": f"NG-{rng.randint(1,49)}",
            "acquired_date": (dob + timedelta(days=rng.randint(1, 90))).date().isoformat(),
            "status": rng.choice(statuses),
        },
        "current_sensors": _mock_current_snapshot(animal_id),
        "vet_records": _mock_vet_records(animal_id),
        "photos": [],
    }


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class VetRecordCreate(BaseModel):
    record_type: str = Field(..., pattern="^(vaccination|treatment|disease|weight_check|pregnancy_check|calving|note|other)$")
    record_date: str
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    drug_name: Optional[str] = None
    dosage: Optional[str] = None
    route: Optional[str] = None
    duration_days: Optional[int] = None
    withdrawal_period_days: Optional[int] = None
    vaccine_name: Optional[str] = None
    vaccine_batch: Optional[str] = None
    next_due_date: Optional[str] = None
    disease_name: Optional[str] = None
    outcome: Optional[str] = None
    vet_name: Optional[str] = None
    vet_contact: Optional[str] = None
    notes: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/farms/{farm_id}/animals/{animal_id}/passport")
async def get_passport(
    farm_id: str = Path(...),
    animal_id: str = Path(...),
    user: dict = Depends(_require_read),
) -> Any:
    """Full cow passport — identity, current sensors, vet history, photos."""
    try:
        # TODO: replace with DB query once migration applied
        # async with get_session() as session:
        #     animal = await session.get(Animal, uuid.UUID(animal_id))
        #     ...
        return _mock_passport(farm_id, animal_id)
    except Exception as exc:
        return _mock_passport(farm_id, animal_id)


@router.get("/farms/{farm_id}/animals/{animal_id}/sensor-history")
async def get_sensor_history(
    farm_id: str = Path(...),
    animal_id: str = Path(...),
    days: int = 30,
    user: dict = Depends(_require_read),
) -> Any:
    """Time-series sensor readings for charts (last N days, twice-daily)."""
    days = max(1, min(days, 90))
    return {
        "animal_id": animal_id,
        "farm_id": farm_id,
        "days_requested": days,
        "is_mock": True,
        "readings": _mock_sensor_series(animal_id, days=days),
    }


@router.get("/farms/{farm_id}/animals/{animal_id}/vet-records")
async def list_vet_records(
    farm_id: str = Path(...),
    animal_id: str = Path(...),
    record_type: Optional[str] = None,
    user: dict = Depends(_require_read),
) -> Any:
    records = _mock_vet_records(animal_id)
    if record_type:
        records = [r for r in records if r["record_type"] == record_type]
    return {"animal_id": animal_id, "is_mock": True, "records": records}


@router.post("/farms/{farm_id}/animals/{animal_id}/vet-records", status_code=201)
async def create_vet_record(
    farm_id: str = Path(...),
    animal_id: str = Path(...),
    body: VetRecordCreate = ...,
    user: dict = Depends(_require_write),
) -> Any:
    """Create a new vet record. Returns the created record (mock until DB live)."""
    new_id = str(uuid.uuid4())
    record = {
        "id": new_id,
        "animal_id": animal_id,
        "farm_id": farm_id,
        "is_mock": True,
        "created_by": user.get("user_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **body.model_dump(exclude_none=True),
    }
    return record


@router.put("/farms/{farm_id}/animals/{animal_id}/vet-records/{record_id}")
async def update_vet_record(
    farm_id: str = Path(...),
    animal_id: str = Path(...),
    record_id: str = Path(...),
    body: VetRecordCreate = ...,
    user: dict = Depends(_require_write),
) -> Any:
    return {
        "id": record_id,
        "animal_id": animal_id,
        "farm_id": farm_id,
        "is_mock": True,
        "updated_by": user.get("user_id"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **body.model_dump(exclude_none=True),
    }


@router.delete("/farms/{farm_id}/animals/{animal_id}/vet-records/{record_id}", status_code=204)
async def delete_vet_record(
    farm_id: str = Path(...),
    animal_id: str = Path(...),
    record_id: str = Path(...),
    user: dict = Depends(_require_write),
) -> None:
    # TODO: DB delete
    return None


# ── Photos ────────────────────────────────────────────────────────────────────

@router.get("/farms/{farm_id}/animals/{animal_id}/photos")
async def list_photos(
    farm_id: str = Path(...),
    animal_id: str = Path(...),
    user: dict = Depends(_require_read),
) -> Any:
    # TODO: query DB + generate URLs
    return {"animal_id": animal_id, "is_mock": True, "photos": []}


@router.post("/farms/{farm_id}/animals/{animal_id}/photos", status_code=201)
async def upload_photo(
    farm_id: str = Path(...),
    animal_id: str = Path(...),
    file: UploadFile = File(...),
    user: dict = Depends(_require_write),
) -> Any:
    content = await file.read()
    try:
        meta = await save_photo(
            content=content,
            filename=file.filename or "photo.jpg",
            content_type=file.content_type or "image/jpeg",
            animal_id=animal_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    photo_id = str(uuid.uuid4())
    return {
        "id": photo_id,
        "animal_id": animal_id,
        "farm_id": farm_id,
        "url": meta["url"],
        "storage_key": meta["storage_key"],
        "filename": meta["filename"],
        "content_type": meta["content_type"],
        "file_size_bytes": meta["file_size_bytes"],
        "is_primary": False,
        "ml_confidence": None,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "uploaded_by": user.get("user_id"),
    }


@router.delete("/farms/{farm_id}/animals/{animal_id}/photos/{photo_id}", status_code=204)
async def delete_animal_photo(
    farm_id: str = Path(...),
    animal_id: str = Path(...),
    photo_id: str = Path(...),
    user: dict = Depends(_require_write),
) -> None:
    # TODO: look up storage_key from DB, then call delete_photo(storage_key)
    return None


# ── ML Identification ─────────────────────────────────────────────────────────

@router.post("/animals/identify-from-photo")
async def identify_from_photo(
    file: UploadFile = File(...),
    user: dict = Depends(_require_read),
) -> Any:
    """
    ML stub: upload a photo to identify which animal it is.
    Returns a mock confidence score.
    Replace body with real model inference once the ML pipeline is integrated.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Empty file.")

    # Deterministic mock result based on file hash
    import hashlib
    file_hash = hashlib.sha256(content).hexdigest()
    seed_val = int(file_hash[:8], 16)
    rng = random.Random(seed_val)

    confidence = round(rng.uniform(0.61, 0.97), 3)
    mock_tag = f"NG-{rng.randint(100, 999)}"

    return {
        "is_mock": True,
        "method": "mock_hash_similarity",
        "matched_tag": mock_tag,
        "confidence": confidence,
        "confidence_label": (
            "High" if confidence > 0.85
            else "Medium" if confidence > 0.70
            else "Low"
        ),
        "message": (
            "MOCK RESULT — connect a real CV model to replace this stub. "
            "See app/api/animals.py identify_from_photo()."
        ),
    }
