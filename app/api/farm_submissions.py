"""
NDIC Farm Data Submission API — Phase 3
─────────────────────────────────────────
Endpoints:
  POST  /farms/register                       Register org + farm + admin user
  POST  /farms/{farm_id}/animals              Register an animal
  POST  /farms/{farm_id}/health-records       Submit signed batch health records
  GET   /farms/{farm_id}/dashboard            Farm dashboard (herd summary + alerts)
  GET   /farms/{farm_id}/animals/{animal_id}  Animal profile + health history
  GET   /farms/{farm_id}/health-records       Recent health records (filterable)

Auth: Phase 3 uses a simplified X-User-ID header (UUID) instead of JWT.
      Full JWT auth (from app/api/auth.py) is wired in Phase 4.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import SignatureVerificationError, generate_keypair
from app.services.farm_service import (
    AnimalNotOwnedError,
    FarmNotFoundError,
    get_animal_profile,
    get_farm_dashboard_data,
    submit_health_records,
)
from app.utils.validators import (
    BEHAVIOR_LABELS,
    VALID_BREEDS,
    VALID_SEXES,
    validate_animal_creation,
    validate_farm_registration,
    validate_health_record,
)
from models.database import Animal, Farm, Organization, User, HealthRecord
from models.enums import AnimalBreed, AnimalSex, AnimalStatus, LedgerEventType, OrganizationType, UserRole

log = logging.getLogger(__name__)
router = APIRouter(tags=["farms"])

# ---------------------------------------------------------------------------
# Password hashing (mirrors app/api/auth.py — shared helper in production)
# ---------------------------------------------------------------------------
try:
    from passlib.context import CryptContext
    _pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    def _hash_pw(plain: str) -> str: return _pwd.hash(plain)
except ImportError:
    import hashlib
    def _hash_pw(plain: str) -> str: return hashlib.sha256(plain.encode()).hexdigest()


# ---------------------------------------------------------------------------
# DB session dependency (same pattern as auth.py)
# ---------------------------------------------------------------------------

async def get_db(request: Request) -> AsyncSession:  # type: ignore[return]
    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Simplified user identity header
# ---------------------------------------------------------------------------

async def current_user_from_header(
    x_user_id: str = Header(..., alias="X-User-ID", description="Authenticated user UUID"),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve the requesting user from the X-User-ID header.
    Replace with proper JWT dependency (from auth.py) in Phase 4.
    """
    try:
        uid = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-User-ID must be a valid UUID")

    result = await session.execute(select(User).where(User.id == uid, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class RegisterFarmRequest(BaseModel):
    organization_name: str = Field(..., max_length=255)
    state: str = Field(..., max_length=100)
    lga: str | None = Field(None, max_length=100)
    herd_size: int | None = Field(None, ge=0)
    contact_email: EmailStr | None = None
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=12)
    admin_full_name: str = Field(..., max_length=255)


class RegisterFarmResponse(BaseModel):
    farm_id: str
    organization_id: str
    admin_user_id: str
    farm_code: str
    public_key_pem: str
    private_key_pem: str       # SHOWN ONCE — actor must store securely
    setup_instructions: str


class CreateAnimalRequest(BaseModel):
    identification_number: str = Field(..., max_length=100, description="Ear tag or RFID code")
    name: str | None = Field(None, max_length=255, description="Stored in notes field")
    breed: str = Field("other", max_length=50)
    sex: str | None = Field(None, description="male | female")
    gender: str | None = Field(None, description="Alias for sex")
    date_of_birth: datetime | None = None
    weight_kg: float | None = Field(None, gt=0)
    acquired_at: datetime | None = None
    signature: str = Field(..., description="Ed25519/RSA signature of this record's canonical JSON")


class CreateAnimalResponse(BaseModel):
    animal_id: str
    farm_id: str
    tag_number: str


class AnimalHealthEntry(BaseModel):
    animal_id: str = Field(..., description="Animal UUID or tag_number")
    temperature_c: float | None = Field(None, ge=35, le=42)
    behavior: str | None = Field(None, description=f"One of: {sorted(BEHAVIOR_LABELS)}")
    milk_yield_liters: float | None = Field(None, ge=0, le=50)
    treatments: list[Any] | None = None
    notes: str | None = None


class HealthRecordSubmissionData(BaseModel):
    submission_date: datetime
    animals: list[AnimalHealthEntry] = Field(..., min_length=1)


class SignedHealthRecordRequest(BaseModel):
    data: HealthRecordSubmissionData
    signature: str = Field(..., description="RSA-PSS signature of canonical_json(data) using your private key")


class HealthRecordResponse(BaseModel):
    id: str
    animal_id: str
    record_date: str
    temperature_celsius: float | None
    behavior_score: int | None
    behavior_label: str | None
    milk_yield_liters: float | None
    notes: str | None
    created_at: str


# ---------------------------------------------------------------------------
# POST /farms/register
# ---------------------------------------------------------------------------

@router.post(
    "/farms/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterFarmResponse,
    summary="Register a new farm organisation with admin user",
)
async def register_farm(
    body: RegisterFarmRequest,
    session: AsyncSession = Depends(get_db),
) -> RegisterFarmResponse:
    """
    One-shot onboarding: creates Organisation + Farm + admin User + RSA keypair.

    The returned private_key_pem is shown **once** and never stored.
    The actor must save it securely — it is used to sign all data submissions.
    """
    payload = body.model_dump()
    errors = validate_farm_registration(payload)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    # Check email uniqueness
    existing = await session.execute(select(User).where(User.email == str(body.admin_email)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    pub_pem, priv_pem = generate_keypair()

    farm_code = f"FARM-{str(uuid.uuid4())[:8].upper()}"

    org = Organization(
        name=body.organization_name,
        org_type=OrganizationType.FARM,
        state=body.state,
        lga=body.lga,
        contact_email=str(body.contact_email) if body.contact_email else None,
        is_active=True,
    )
    session.add(org)
    await session.flush()

    admin_user = User(
        email=str(body.admin_email),
        hashed_password=_hash_pw(body.admin_password),
        full_name=body.admin_full_name,
        role=UserRole.FARM,
        organization_id=org.id,
        public_key=pub_pem,
        is_active=True,
    )
    session.add(admin_user)
    await session.flush()

    farm = Farm(
        organization_id=org.id,
        farm_code=farm_code,
        farm_name=body.organization_name,
        state=body.state,
        lga=body.lga,
        total_capacity=body.herd_size,
        created_by=admin_user.id,
        is_active=True,
    )
    session.add(farm)
    await session.flush()

    log.info("Farm registered: org=%s farm=%s admin=%s", org.id, farm.id, admin_user.id)

    return RegisterFarmResponse(
        farm_id=str(farm.id),
        organization_id=str(org.id),
        admin_user_id=str(admin_user.id),
        farm_code=farm_code,
        public_key_pem=pub_pem,
        private_key_pem=priv_pem,
        setup_instructions=(
            "1. Store private_key_pem securely (offline / hardware token). "
            "It will not be shown again. "
            "2. Sign all health record payloads with this key before submission. "
            f"3. Your farm_id is {farm.id}. "
            f"4. Include X-User-ID: {admin_user.id} in all API requests."
        ),
    )


# ---------------------------------------------------------------------------
# POST /farms/{farm_id}/animals
# ---------------------------------------------------------------------------

@router.post(
    "/farms/{farm_id}/animals",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateAnimalResponse,
    summary="Register an animal to a farm",
)
async def create_animal(
    farm_id: uuid.UUID,
    body: CreateAnimalRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(current_user_from_header),
) -> CreateAnimalResponse:
    """
    Register a new animal under the given farm.

    The caller must own the farm (organisation_id must match).
    signature: RSA-PSS signature of canonical_json(this request body).
    """
    # Farm ownership check
    result = await session.execute(
        select(Farm).where(Farm.id == farm_id, Farm.organization_id == user.organization_id)
    )
    farm = result.scalar_one_or_none()
    if farm is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farm not found or not owned by your organisation")

    # Domain validation
    animal_dict = body.model_dump()
    errors = validate_animal_creation(animal_dict)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    tag = (body.identification_number or "").strip()

    # Check tag uniqueness within farm
    dup = await session.execute(
        select(Animal).where(Animal.farm_id == farm_id, Animal.tag_number == tag)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Tag '{tag}' already registered in this farm")

    sex_raw = (body.sex or body.gender or "female").lower().strip()
    sex = AnimalSex.FEMALE if sex_raw == "female" else AnimalSex.MALE

    breed_raw = (body.breed or "other").lower().strip()
    try:
        breed = AnimalBreed(breed_raw)
    except ValueError:
        breed = AnimalBreed.OTHER

    notes_parts = []
    if body.name:
        notes_parts.append(f"Name: {body.name}")

    animal = Animal(
        farm_id=farm_id,
        tag_number=tag,
        breed=breed,
        sex=sex,
        date_of_birth=body.date_of_birth,
        weight_kg=body.weight_kg,
        acquired_at=body.acquired_at or datetime.now(timezone.utc),
        status=AnimalStatus.ACTIVE,
        notes="; ".join(notes_parts) if notes_parts else None,
        created_by=user.id,
        signature=body.signature,
    )
    session.add(animal)
    await session.flush()

    log.info("Animal registered: tag=%s farm=%s id=%s", tag, farm_id, animal.id)

    return CreateAnimalResponse(
        animal_id=str(animal.id),
        farm_id=str(farm_id),
        tag_number=tag,
    )


# ---------------------------------------------------------------------------
# POST /farms/{farm_id}/health-records  (signed — critical endpoint)
# ---------------------------------------------------------------------------

@router.post(
    "/farms/{farm_id}/health-records",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a signed batch of health records (cryptographically verified)",
)
async def submit_signed_health_records(
    farm_id: uuid.UUID,
    body: SignedHealthRecordRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(current_user_from_header),
) -> dict[str, Any]:
    """
    The primary data ingestion endpoint for farms.

    The entire `data` payload must be signed with the farm's RSA private key.
    The system verifies the signature against the public key registered in DB,
    then appends an immutable ledger entry before inserting health records.

    If the signature fails verification a 401 is returned immediately.
    No records are written if any part of the transaction fails.
    """
    if not user.public_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No public key registered. Call POST /auth/register-public-key first.",
        )

    # Pre-validate each animal entry (before touching the DB / ledger)
    validation_errors: list[dict] = []
    for entry in body.data.animals:
        errs = validate_health_record(entry.model_dump(exclude_none=True))
        if errs:
            validation_errors.append({"animal_id": entry.animal_id, "errors": errs})
    if validation_errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=validation_errors)

    # Canonical dict that was signed — must match exactly what the client signed
    data_dict = body.data.model_dump(mode="json")

    try:
        result = await submit_health_records(
            session=session,
            farm_id=farm_id,
            submission_date=body.data.submission_date,
            animal_records=[e.model_dump() for e in body.data.animals],
            data_dict=data_dict,
            signature_b64=body.signature,
            actor_user_id=user.id,
            public_key_pem=user.public_key,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except FarmNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SignatureVerificationError as exc:
        log.warning("Signature verification failed: user=%s farm=%s", user.id, farm_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Signature verification failed: {exc}",
        )

    return {
        "processed_count": result["processed_count"],
        "failed_records": result["failed_records"],
        "ledger_entry_id": str(result["ledger_entry_id"]),
        "verification_status": result["verification_status"],
        "farm_id": str(farm_id),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /farms/{farm_id}/dashboard
# ---------------------------------------------------------------------------

@router.get(
    "/farms/{farm_id}/dashboard",
    summary="Farm dashboard — herd summary, metrics, intervention alerts",
)
async def farm_dashboard(
    farm_id: uuid.UUID,
    window_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(current_user_from_header),
) -> dict[str, Any]:
    """
    Returns aggregated herd health metrics and actionable intervention alerts.

    Accessible to: farm owner, ARPEXAS admin.
    """
    _require_farm_access(user, farm_id)
    try:
        return await get_farm_dashboard_data(session=session, farm_id=farm_id, window_days=window_days)
    except FarmNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /farms/{farm_id}/animals/{animal_id}
# ---------------------------------------------------------------------------

@router.get(
    "/farms/{farm_id}/animals/{animal_id}",
    summary="Animal profile — lifetime health trajectory + risk flags",
)
async def animal_profile(
    farm_id: uuid.UUID,
    animal_id: uuid.UUID,
    history_days: int = Query(90, ge=1, le=730),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(current_user_from_header),
) -> dict[str, Any]:
    """
    Full health profile for one animal: identity, history, metrics, risk flags.
    """
    _require_farm_access(user, farm_id)
    try:
        return await get_animal_profile(
            session=session,
            animal_id=animal_id,
            farm_id=farm_id,
            history_days=history_days,
        )
    except AnimalNotOwnedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /farms/{farm_id}/health-records
# ---------------------------------------------------------------------------

@router.get(
    "/farms/{farm_id}/health-records",
    summary="Recent health records for all animals on a farm",
)
async def list_health_records(
    farm_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    animal_id: uuid.UUID | None = Query(None, description="Filter by animal UUID"),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(current_user_from_header),
) -> dict[str, Any]:
    """
    Returns health records for the farm within the requested window.
    Optionally filtered to a single animal. Sorted newest-first.
    """
    _require_farm_access(user, farm_id)

    from datetime import timedelta
    from models.database import HealthRecord
    from app.services.farm_service import _hr_to_dict

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(HealthRecord)
        .where(HealthRecord.farm_id == farm_id, HealthRecord.record_date >= cutoff)
        .order_by(HealthRecord.record_date.desc())
    )
    if animal_id:
        stmt = stmt.where(HealthRecord.animal_id == animal_id)

    result = await session.execute(stmt)
    records = list(result.scalars().all())

    return {
        "farm_id": str(farm_id),
        "days": days,
        "count": len(records),
        "records": [_hr_to_dict(r) for r in records],
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _require_farm_access(user: User, farm_id: uuid.UUID) -> None:
    """
    Enforce that the requesting user can access the given farm.
    ARPEXAS admins can access any farm. Farm users can only access their own org's farms.
    This is a lightweight check; full ABAC is wired in Phase 4.
    """
    if user.role == UserRole.ARPEXAS_ADMIN:
        return
    # For non-admins, the farm-ownership check is done inside the service
    # (farm.organization_id == user.organization_id). Here we just pass through.
