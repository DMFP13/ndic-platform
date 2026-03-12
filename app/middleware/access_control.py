"""
NDIC Access Control Middleware  (Phase 5a)
───────────────────────────────────────────
FastAPI dependency functions for RBAC enforcement on all protected endpoints.

Design: FastAPI-style dependency injection (not ASGI middleware) so that:
  - Dependency resolution is visible in OpenAPI docs
  - 401/403 errors are raised before any business logic runs
  - Audit logging is co-located with the access decision

Usage in an endpoint::

    from app.middleware.access_control import get_current_user, require_admin

    @router.get("/farms/{farm_id}/animals/{animal_id}")
    async def get_animal(
        farm_id: str,
        animal_id: str,
        user: dict = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ):
        allowed, reason = await check_resource_access(
            session, user["user_id"], "animals",
            record_id=animal_id, action="view",
            user_org_id=user["org_id"],
            record_owner_org_id=farm_org_id,   # fetched from DB
        )
        if not allowed:
            raise HTTPException(403, detail=reason)
        ...
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.security import TokenError, verify_jwt_token
from config import get_settings

log = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Session dependency  (mirrors auth.py pattern)
# ---------------------------------------------------------------------------

async def get_db(request: Request):  # type: ignore[return]
    """FastAPI dependency: yields an async DB session."""
    async with request.app.state.session_factory() as session:
        yield session


# ===========================================================================
# JWT extraction
# ===========================================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict[str, Any]:
    """
    Decode the Bearer JWT and return a plain user-context dict.

    Returns::

        {
          "user_id":    str (UUID),
          "org_id":     str | None,
          "role":       str,
          "email":      str | None,
          "token_type": str,
        }

    Raises HTTP 401 if token is missing or invalid.

    Note: this dependency does NOT hit the database; it only verifies the JWT
    signature.  Endpoints that need the full User ORM object should use
    get_current_user() from app/api/auth.py instead.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required — no Bearer token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    try:
        payload = verify_jwt_token(credentials.credentials, settings.jwt_secret_key)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected an access token (not a refresh token)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id":    payload.get("sub"),
        "org_id":     payload.get("org"),
        "role":       payload.get("role"),
        "email":      payload.get("email"),
        "token_type": payload.get("type", "access"),
    }


# ===========================================================================
# Resource-level access check
# ===========================================================================

async def check_resource_access(
    session: Any,
    user_id: str | uuid.UUID,
    resource: str,
    *,
    record_id: Optional[str] = None,
    action: str,
    user_org_id: Optional[str | uuid.UUID] = None,
    record_owner_org_id: Optional[str | uuid.UUID] = None,
) -> tuple[bool, str]:
    """
    Verify RBAC + data-classification access, then write an audit entry.

    Returns (allowed: bool, reason: str).
    Callers should raise HTTPException(403, reason) when allowed is False.

    Imports are deferred to avoid circular-import cycles.
    """
    from app.services.rbac_service import check_access
    from app.services.audit_service import (
        log_access, RESULT_ALLOWED, RESULT_DENIED,
    )

    user_id_str   = str(user_id)
    org_id_uuid   = uuid.UUID(str(user_org_id))         if user_org_id         else None
    owner_id_uuid = uuid.UUID(str(record_owner_org_id)) if record_owner_org_id else None
    user_id_uuid  = uuid.UUID(user_id_str)

    allowed, reason = await check_access(
        session,
        user_id=user_id_uuid,
        data_type=resource,
        record_owner_org_id=owner_id_uuid,
        user_org_id=org_id_uuid,
    )

    await log_access(
        session,
        user_id=user_id_str,
        action=action,
        data_type=resource,
        record_id=str(record_id) if record_id else None,
        organization_id=str(user_org_id) if user_org_id else None,
        result=RESULT_ALLOWED if allowed else RESULT_DENIED,
        details={"reason": reason},
    )
    return allowed, reason


# ===========================================================================
# Role-guard dependencies
# ===========================================================================

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """
    FastAPI dependency that denies access to non-admin users.

    Usage::

        @router.get("/admin-only")
        async def endpoint(admin: dict = Depends(require_admin)):
            ...
    """
    if user.get("role") != "arpexas_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires arpexas_admin role",
        )
    return user


def require_role(*allowed_roles: str):
    """
    Return a FastAPI dependency that enforces one of the allowed roles.

    Usage::

        @router.post("/intakes")
        async def submit_intake(
            user: dict = Depends(require_role("processor_analyst", "processor_commercial")),
        ):
            ...
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires one of: {list(allowed_roles)}",
            )
        return user
    return _check


# ===========================================================================
# Farm-ownership guard
# ===========================================================================

async def require_farm_access(
    request: Request,
    user: dict = Depends(get_current_user),
    session: Any = Depends(get_db),
) -> dict:
    """
    FastAPI dependency for farm-scoped endpoints.

    Verifies that the authenticated user's org owns the farm in the URL path.
    arpexas_admin bypasses the ownership check.

    Returns a context dict::

        {"user": user_dict, "farm_id": str, "access": "own_org" | "global"}

    Usage::

        @router.get("/farms/{farm_id}/dashboard")
        async def dashboard(ctx: dict = Depends(require_farm_access)):
            user    = ctx["user"]
            farm_id = ctx["farm_id"]
            ...
    """
    from models.database import Farm
    from sqlalchemy import select

    farm_id   = request.path_params.get("farm_id")
    user_role = user.get("role", "")
    user_org  = user.get("org_id")

    if user_role == "arpexas_admin":
        return {"user": user, "farm_id": farm_id, "access": "global"}

    if farm_id:
        try:
            farm_uuid = uuid.UUID(farm_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid farm_id format")

        result = await session.execute(select(Farm).where(Farm.id == farm_uuid))
        farm = result.scalar_one_or_none()

        if farm is None:
            raise HTTPException(status_code=404, detail="Farm not found")

        if str(farm.organization_id) != str(user_org):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied: farm {farm_id} does not belong "
                    f"to your organisation"
                ),
            )

    return {"user": user, "farm_id": farm_id, "access": "own_org"}
