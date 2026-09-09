"""
NDIC Authentication API
────────────────────────
Endpoints:
  POST  /auth/register-organization   Register org + admin user + return keypair
  POST  /auth/login                   Authenticate; return access + refresh tokens
  POST  /auth/refresh-token           Exchange refresh token for new access token
  POST  /auth/register-public-key     User uploads their RSA public key to DB
  GET   /ledger/integrity-check       Admin: walk and verify the full ledger chain

All routes use FastAPI with an async SQLAlchemy session dependency.
Passwords are hashed with bcrypt via passlib.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    generate_keypair,
    verify_jwt_token,
)
from app.services.ledger_service import verify_chain_integrity
from app.utils.crypto_utils import InvalidKeyError, is_valid_rsa_public_key
from config import get_settings
from models.database import Organization, User, LedgerLog
from models.enums import LedgerEventType, OrganizationType, UserRole
from models.schemas import OrganizationResponse, UserResponse

log = logging.getLogger(__name__)
router = APIRouter()
bearer_scheme = HTTPBearer()

# ---------------------------------------------------------------------------
# Passlib for password hashing (install: pip install passlib[bcrypt])
# ---------------------------------------------------------------------------
try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(plain: str) -> str:
        return _pwd_context.hash(plain)

    def verify_password(plain: str, hashed: str) -> bool:
        return _pwd_context.verify(plain, hashed)

except ImportError:
    # Fallback for environments without passlib; NOT for production
    import hashlib

    def hash_password(plain: str) -> str:
        return hashlib.sha256(plain.encode()).hexdigest()

    def verify_password(plain: str, hashed: str) -> bool:
        return hashlib.sha256(plain.encode()).hexdigest() == hashed


from app.dependencies import get_db

DB = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# JWT current-user dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    session: DB,
) -> User:
    """
    Decode the Bearer JWT and return the matching User ORM object.
    Raises 401 on any token problem, 404 if user no longer exists.
    """
    settings = get_settings()
    try:
        payload = verify_jwt_token(credentials.credentials, settings.jwt_secret_key)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected access token",
        )

    user_id = payload.get("sub")
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole):
    """Return a FastAPI dependency that enforces one of the allowed roles."""
    async def _check(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires role: {[r.value for r in roles]}",
            )
        return current_user
    return _check


# ---------------------------------------------------------------------------
# Request / response schemas (auth-specific; not in models/schemas.py)
# ---------------------------------------------------------------------------

class RegisterOrganizationRequest(BaseModel):
    # Organisation details
    org_name: str = Field(..., max_length=255)
    org_type: OrganizationType
    state: str = Field(..., max_length=100)
    lga: str | None = Field(None, max_length=100)
    registration_number: str | None = Field(None, max_length=100)
    contact_email: EmailStr | None = None
    # First admin user for this organisation
    admin_full_name: str = Field(..., max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=12)


class RegisterOrganizationResponse(BaseModel):
    organization_id: uuid.UUID
    admin_user_id: uuid.UUID
    # We generate a demo keypair for the actor.
    # In production, organisations generate their own key pair externally
    # and call POST /auth/register-public-key to upload the public half.
    public_key_pem: str
    private_key_pem: str   # MUST be stored securely by the actor; platform does NOT retain this
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterPublicKeyRequest(BaseModel):
    public_key_pem: str = Field(..., description="RSA-2048 public key in PEM format")


class IntegrityCheckResponse(BaseModel):
    is_valid: bool
    entries_checked: int
    broken_at: str | None
    errors: list[dict[str, Any]]
    checked_at: datetime


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/register-organization",
    response_model=RegisterOrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new organisation and its first admin user",
    tags=["auth"],
)
async def register_organization(
    body: RegisterOrganizationRequest,
    session: DB,
) -> RegisterOrganizationResponse:
    """
    Create an Organisation + first admin User in a single atomic transaction.

    A demo RSA-2048 key pair is generated and returned.
    **The private key is shown only once — the actor must store it securely.**
    The platform retains only the public key.

    In a production deployment, organisations would generate their own key pair
    externally (e.g. via `openssl genpkey`) and call POST /auth/register-public-key.
    """
    # Check email uniqueness
    existing = await session.execute(select(User).where(User.email == body.admin_email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email already registered: {body.admin_email}",
        )

    # Generate keypair for the demo/onboarding flow
    public_key_pem, private_key_pem = generate_keypair()

    # Map org_type → admin role
    role_map: dict[OrganizationType, UserRole] = {
        OrganizationType.FARM: UserRole.FARM,
        OrganizationType.PROCESSING_COMPANY: UserRole.PROCESSOR,
        OrganizationType.GOVERNMENT_AGENCY: UserRole.GOVERNMENT,
        OrganizationType.FINANCE_INSTITUTION: UserRole.LENDER,
    }
    admin_role = role_map.get(body.org_type, UserRole.FARM)

    org = Organization(
        name=body.org_name,
        org_type=body.org_type,
        state=body.state,
        lga=body.lga,
        registration_number=body.registration_number,
        contact_email=str(body.contact_email) if body.contact_email else None,
    )
    session.add(org)
    await session.flush()  # populate org.id

    admin_user = User(
        email=str(body.admin_email),
        hashed_password=hash_password(body.admin_password),
        full_name=body.admin_full_name,
        role=admin_role,
        organization_id=org.id,
        public_key=public_key_pem,
    )
    session.add(admin_user)
    await session.flush()

    log.info("Registered organisation %s (id=%s) admin=%s", org.name, org.id, admin_user.id)

    return RegisterOrganizationResponse(
        organization_id=org.id,
        admin_user_id=admin_user.id,
        public_key_pem=public_key_pem,
        private_key_pem=private_key_pem,
        message=(
            "Organisation registered. Store the private_key_pem securely — "
            "it will NOT be shown again. Use it to sign all data submissions."
        ),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
    tags=["auth"],
)
async def login(body: LoginRequest, session: DB) -> TokenResponse:
    """
    Verify credentials and return a short-lived access token (60 min)
    plus a long-lived refresh token (7 days).
    """
    settings = get_settings()
    result = await session.execute(select(User).where(User.email == body.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last_login (this is NOT a ledger event — it's a session concern)
    user.last_login = datetime.now(timezone.utc)

    access_token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        secret=settings.jwt_secret_key,
    )
    refresh_token = create_refresh_token(user_id=user.id, secret=settings.jwt_secret_key)

    expire_seconds = settings.jwt_access_token_expire_minutes * 60
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=expire_seconds,
    )


@router.post(
    "/refresh-token",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access token",
    tags=["auth"],
)
async def refresh_token(body: RefreshRequest, session: DB) -> TokenResponse:
    """
    Validate a refresh token and issue a new access token.
    The refresh token itself is NOT rotated (stateless design).
    """
    settings = get_settings()
    try:
        payload = verify_jwt_token(body.refresh_token, settings.jwt_secret_key)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected refresh token",
        )

    user_id = payload["sub"]
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user: User | None = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        secret=settings.jwt_secret_key,
    )
    refresh_token_new = create_refresh_token(user_id=user.id, secret=settings.jwt_secret_key)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_new,
        expires_in_seconds=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/register-public-key",
    status_code=status.HTTP_200_OK,
    summary="Register or update a user's RSA public key",
    tags=["auth"],
)
async def register_public_key(
    body: RegisterPublicKeyRequest,
    current_user: CurrentUser,
    session: DB,
) -> dict[str, str]:
    """
    Store the caller's RSA-2048 public key (PEM).
    The public key is used by the server to verify all subsequent record submissions.

    Callers generate their key pair externally::

        openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
        openssl pkey -in private.pem -pubout -out public.pem

    Then POST the content of public.pem here.
    """
    if not is_valid_rsa_public_key(body.public_key_pem):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provided PEM is not a valid RSA public key",
        )

    current_user.public_key = body.public_key_pem.strip()
    log.info("Public key registered for user %s", current_user.id)
    return {"message": "Public key registered successfully", "user_id": str(current_user.id)}


# ---------------------------------------------------------------------------
# Ledger integrity check
# ---------------------------------------------------------------------------

@router.get(
    "/ledger/integrity-check",
    response_model=IntegrityCheckResponse,
    summary="Verify the ledger hash chain (admin only)",
    tags=["ledger"],
    dependencies=[Depends(require_role(UserRole.ARPEXAS_ADMIN))],
)
async def ledger_integrity_check(
    session: DB,
    actor_user_id: uuid.UUID | None = None,
    target_table: str | None = None,
    limit: int = 10_000,
) -> IntegrityCheckResponse:
    """
    Walk the ledger hash chain and verify every link.

    Optional filters:
      - `actor_user_id`: check only entries submitted by a specific user.
      - `target_table`:  check only entries for a specific domain table.
      - `limit`:         maximum entries to scan (default 10,000).

    This is a potentially slow O(n) operation.  It should be run as a
    scheduled background job in production, not on a user-facing request.
    Results should be stored and served from cache.
    """
    result = await verify_chain_integrity(
        session=session,
        actor_user_id=actor_user_id,
        target_table=target_table,
        limit=limit,
    )
    return IntegrityCheckResponse(
        **result,
        checked_at=datetime.now(timezone.utc),
    )
