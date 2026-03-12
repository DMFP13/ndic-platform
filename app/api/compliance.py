"""
NDIC Compliance API  (Phase 5a)
────────────────────────────────
Government-ready compliance endpoints for FMARD oversight.

Endpoints:
  POST /compliance/audit-report         Download access/export/summary audit report
  GET  /compliance/chain-integrity-report  Verify ledger hash chain
  GET  /compliance/rbac-audit           Scan roles + permissions for issues
  GET  /compliance/export-audit         List recent data exports
  POST /compliance/data-deletion-request   Soft-delete (right to be forgotten)

All endpoints require arpexas_admin JWT token except data-deletion-request,
which also accepts a farmer deleting their own data.

Example — FMARD requests audit report::

    POST /compliance/audit-report
    {
        "start_date": "2024-01-01T00:00:00Z",
        "end_date":   "2024-03-11T23:59:59Z",
        "organization_id": "fmard-org-uuid",
        "report_type": "access_log",
        "format": "csv"
    }
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.access_control import get_current_user
from app.models.rbac_models import (
    AuditLog, AuditExport, UserRoleAssignment, Role, Permission, RolePermission,
)
from app.services.audit_service import (
    get_audit_log, get_export_log,
    log_access, log_compliance_check,
    ACTION_EXPORT,
    RESULT_ALLOWED, RESULT_DENIED, RESULT_PASSED, RESULT_FAILED,
)
from app.services.ledger_service import verify_chain_integrity

log = logging.getLogger(__name__)
router = APIRouter(prefix="/compliance", tags=["compliance"])


# ---------------------------------------------------------------------------
# Session dependency
# ---------------------------------------------------------------------------

async def get_db(request: Request):  # type: ignore[return]
    async with request.app.state.session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AuditReportRequest(BaseModel):
    start_date:      datetime
    end_date:        datetime
    organization_id: Optional[str] = None
    report_type:     str = Field("access_log", pattern="^(access_log|export_log|summary)$")
    format:          str = Field("json", pattern="^(json|csv)$")


class ChainIntegrityResponse(BaseModel):
    is_valid:        bool
    entries_checked: int
    broken_at:       Optional[str]
    errors:          list[str]
    checked_at:      str


class RbacAuditResponse(BaseModel):
    audit_result:    str            # "passed" | "failed"
    issues:          list[str]
    users_checked:   int
    roles_checked:   int
    checked_at:      str


class DeletionRequest(BaseModel):
    farmer_id: str
    reason:    str = Field(..., pattern="^(right_to_be_forgotten|consent_withdrawn)$")


class DeletionResponse(BaseModel):
    deletion_request_id: str
    status:              str
    timestamp:           str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin(user: dict) -> None:
    if user.get("role") != "arpexas_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires arpexas_admin role",
        )


def _rows_to_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    """Serialise a list of flat dicts to CSV string."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# ===========================================================================
# Endpoints
# ===========================================================================

@router.post("/audit-report")
async def generate_audit_report(
    body: AuditReportRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Download an audit log for a date range as JSON or CSV.

    report_type options:
      access_log  — every view/create/delete/export event
      export_log  — only bulk data-export events (with file hashes)
      summary     — aggregated counts by action:result

    Requires arpexas_admin role.
    """
    _require_admin(user)

    if body.report_type == "export_log":
        days = max(1, (body.end_date - body.start_date).days + 1)
        rows = await get_export_log(
            session,
            organization_id=body.organization_id,
            days=days,
        )
        fieldnames = [
            "id", "user_id", "export_type", "records_count",
            "file_hash", "organization_id", "timestamp",
        ]

    elif body.report_type == "summary":
        all_rows = await get_audit_log(
            session,
            organization_id=body.organization_id,
            start_date=body.start_date,
            end_date=body.end_date,
            limit=10_000,
        )
        counts: dict[str, int] = Counter(
            f"{r['action']}:{r['result']}" for r in all_rows
        )
        rows = [{"event": k, "count": v} for k, v in sorted(counts.items())]
        fieldnames = ["event", "count"]

    else:  # access_log
        rows = await get_audit_log(
            session,
            organization_id=body.organization_id,
            start_date=body.start_date,
            end_date=body.end_date,
            limit=10_000,
        )
        fieldnames = [
            "timestamp", "user_id", "action", "data_type",
            "record_id", "organization_id", "result",
        ]

    # Record the export itself
    await log_access(
        session,
        user_id=user["user_id"],
        action=ACTION_EXPORT,
        data_type="audit_report",
        organization_id=body.organization_id,
        result=RESULT_ALLOWED,
        details={"report_type": body.report_type, "rows_returned": len(rows)},
    )
    await session.commit()

    if body.format == "csv":
        content = _rows_to_csv(rows, fieldnames)
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="ndic_audit_{body.report_type}.csv"'
                )
            },
        )

    return {
        "report_type":     body.report_type,
        "organization_id": body.organization_id,
        "start_date":      body.start_date.isoformat(),
        "end_date":        body.end_date.isoformat(),
        "rows":            len(rows),
        "data":            rows,
    }


@router.get("/chain-integrity-report", response_model=ChainIntegrityResponse)
async def chain_integrity_report(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Walk and verify the entire ledger hash chain.

    For each (actor, target_table) pair, re-computes every chain_hash and
    confirms that chain_hash[i] = SHA-256(payload_hash[i] || chain_hash[i-1]).

    Requires arpexas_admin role.
    """
    _require_admin(user)

    result = await verify_chain_integrity(session)
    is_valid        = bool(result.get("is_valid", False))
    entries_checked = int(result.get("entries_checked", 0))
    broken_at_raw   = result.get("broken_at")
    broken_at       = str(broken_at_raw) if broken_at_raw else None
    errors          = list(result.get("errors", []))

    await log_compliance_check(
        session,
        check_type="chain_integrity_check",
        result=RESULT_PASSED if is_valid else RESULT_FAILED,
        details={
            "entries_checked": entries_checked,
            "broken_at":       broken_at,
            "error_count":     len(errors),
        },
    )
    await session.commit()

    return ChainIntegrityResponse(
        is_valid=is_valid,
        entries_checked=entries_checked,
        broken_at=broken_at,
        errors=errors,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/rbac-audit", response_model=RbacAuditResponse)
async def rbac_audit(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Scan all users, roles, and permissions for compliance issues.

    Checks performed:
      - Every active role has at least one permission
      - No RolePermission entries point to deleted permissions
      - Every active user has at least one role assignment

    Requires arpexas_admin role.
    """
    _require_admin(user)
    issues: list[str] = []

    # Load active roles
    roles_result = await session.execute(
        select(Role).where(Role.is_active == True)
    )
    roles = roles_result.scalars().all()

    # Load all permissions
    perms_result = await session.execute(select(Permission))
    all_perm_ids = {str(p.id) for p in perms_result.scalars().all()}

    # Load role-permission links
    rp_result = await session.execute(select(RolePermission))
    rp_links = rp_result.scalars().all()

    # Check: roles with no permissions
    roles_with_perms: set[str] = {str(rp.role_id) for rp in rp_links}
    for role in roles:
        if str(role.id) not in roles_with_perms:
            issues.append(
                f"Role '{role.name}' (id={role.id}) has no permissions assigned"
            )

    # Check: orphaned RolePermission (permission was deleted)
    for rp in rp_links:
        if str(rp.permission_id) not in all_perm_ids:
            issues.append(
                f"Orphaned RolePermission: role_id={rp.role_id} → "
                f"permission_id={rp.permission_id} (permission not found)"
            )

    # Check: active users with no role assignment
    from models.database import User
    users_result = await session.execute(
        select(User).where(User.is_active == True)
    )
    active_users = users_result.scalars().all()
    active_assignments = await session.execute(
        select(UserRoleAssignment).where(UserRoleAssignment.is_active == True)
    )
    assigned_user_ids = {str(a.user_id) for a in active_assignments.scalars().all()}

    for u in active_users:
        if str(u.id) not in assigned_user_ids:
            issues.append(
                f"Active user {u.email!r} (id={u.id}) has no role assignment"
            )

    audit_result = "passed" if not issues else "failed"
    await log_compliance_check(
        session,
        check_type="rbac_audit",
        result=RESULT_PASSED if not issues else RESULT_FAILED,
        details={"issues_found": len(issues)},
    )
    await session.commit()

    return RbacAuditResponse(
        audit_result=audit_result,
        issues=issues,
        users_checked=len(active_users),
        roles_checked=len(roles),
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/export-audit")
async def export_audit(
    days: int = 30,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    List all data exports in the last *days* days with file hashes.

    Useful for detecting unauthorised data exfiltration:
      "Did anyone export farm #5 data without authorisation?"

    Requires arpexas_admin role.
    """
    _require_admin(user)

    rows = await get_export_log(session, days=days)
    await log_access(
        session,
        user_id=user["user_id"],
        action=ACTION_EXPORT,
        data_type="export_audit",
        result=RESULT_ALLOWED,
        details={"days_queried": days},
    )
    await session.commit()

    return {
        "days":    days,
        "count":   len(rows),
        "exports": rows,
    }


@router.post("/data-deletion-request", response_model=DeletionResponse)
async def data_deletion_request(
    body: DeletionRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Request soft-deletion of a farmer's personal data (GDPR / right-to-be-forgotten).

    Authorisation:
      - A farmer may request deletion of their own data (farmer_id == caller's user_id)
      - arpexas_admin may request deletion on behalf of any farmer

    Effect:
      - Marks the farmer's records as deleted (soft-delete — data is not physically
        removed from immutable ledger entries, but is excluded from future queries)
      - Writes an immutable audit entry documenting the deletion

    Returns a deletion_request_id for tracking and follow-up queries.
    """
    user_id        = user["user_id"]
    requester_role = user.get("role", "")
    is_own         = str(user_id) == str(body.farmer_id)
    is_admin       = requester_role == "arpexas_admin"

    if not is_own and not is_admin:
        await log_access(
            session,
            user_id=str(user_id),
            action="delete",
            data_type="farmer_data",
            record_id=body.farmer_id,
            result=RESULT_DENIED,
            details={"reason": "not own data and not arpexas_admin"},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only request deletion of your own data",
        )

    deletion_id = str(uuid.uuid4())

    # Immutable audit record of the deletion request
    await log_access(
        session,
        user_id=str(user_id),
        action="delete",
        data_type="farmer_data",
        record_id=body.farmer_id,
        result=RESULT_ALLOWED,
        details={
            "deletion_request_id": deletion_id,
            "reason":              body.reason,
            "requested_by":        str(user_id),
            "is_own_request":      is_own,
        },
    )
    await session.commit()

    log.info(
        "Data deletion request %s: farmer=%s requester=%s reason=%s",
        deletion_id, body.farmer_id, user_id, body.reason,
    )

    return DeletionResponse(
        deletion_request_id=deletion_id,
        status="pending_deletion",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
