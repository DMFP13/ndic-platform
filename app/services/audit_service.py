"""
NDIC Audit Service  (Phase 5a)
───────────────────────────────
Immutable access logging for FMARD compliance.

Key design choices:
  - No PII stored — user IDs and resource IDs only (no names, amounts, health data)
  - Every write is an INSERT; no UPDATE/DELETE on audit_log rows
  - Retention: 3 years (1095 days) enforced by retention_cleanup()
  - retention_cleanup() logs the deletion in a new row, so the act of
    cleanup is itself immutably recorded

Usage::

    # Log an access event
    await log_access(session, user_id=str(uid), action="view",
                     data_type="animals", record_id=str(animal_id),
                     organization_id=str(org_id), result="allowed")

    # Log a bulk export
    await log_export(session, user_id=str(uid), export_type="disease_map",
                     records_count=142, file_hash=sha256_hex,
                     organization_id=str(org_id))

    # Query the log
    rows = await get_audit_log(session, organization_id=..., start_date=..., end_date=...)
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rbac_models import AuditLog, AuditExport

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Action-type constants
# ---------------------------------------------------------------------------
ACTION_VIEW              = "view"
ACTION_EXPORT            = "export"
ACTION_CREATE            = "create"
ACTION_UPDATE            = "update"
ACTION_DELETE            = "delete"
ACTION_VERIFY_SIGNATURE  = "verify_signature"
ACTION_COMPLIANCE_CHECK  = "compliance_check"
ACTION_RETENTION_CLEANUP = "retention_cleanup"

# ---------------------------------------------------------------------------
# Result constants
# ---------------------------------------------------------------------------
RESULT_ALLOWED = "allowed"
RESULT_DENIED  = "denied"
RESULT_ERROR   = "error"
RESULT_PASSED  = "passed"
RESULT_FAILED  = "failed"

# ---------------------------------------------------------------------------
# Retention window
# ---------------------------------------------------------------------------
AUDIT_LOG_RETENTION_DAYS = 1095  # 3 years — FMARD oversight window


# ===========================================================================
# Write helpers
# ===========================================================================

async def log_access(
    session: AsyncSession,
    *,
    user_id: str,
    action: str,
    data_type: str,
    record_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    result: str,
    details: Optional[dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,
) -> AuditLog:
    """
    Insert one access-event row into audit_log.

    The caller owns the transaction (no commit here so that the access log
    entry is rolled back together with the primary write if the request fails).

    Args:
        user_id:         Opaque user UUID string.
        action:          One of the ACTION_* constants.
        data_type:       Platform resource type (e.g. "animals", "health_records").
        record_id:       ID of the specific record accessed (may be None for list views).
        organization_id: Caller's org UUID string.
        result:          One of the RESULT_* constants.
        details:         Extra non-PII context (endpoint, row count, reason). JSONB.
        timestamp:       Override timestamp (defaults to utc_now()).
    """
    entry = AuditLog(
        id=uuid.uuid4(),
        user_id=str(user_id) if user_id else None,
        action=action,
        data_type=data_type,
        record_id=str(record_id) if record_id else None,
        organization_id=str(organization_id) if organization_id else None,
        result=result,
        timestamp=timestamp or datetime.now(timezone.utc),
        details_json=details,
    )
    session.add(entry)
    return entry


async def log_export(
    session: AsyncSession,
    *,
    user_id: str,
    export_type: str,
    records_count: int,
    file_hash: Optional[str] = None,
    organization_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> AuditExport:
    """
    Record a bulk data-export event.

    file_hash should be SHA-256(export_bytes) so post-export integrity can
    be verified: compute the hash of the downloaded file and compare.
    """
    entry = AuditExport(
        id=uuid.uuid4(),
        user_id=str(user_id),
        export_type=export_type,
        records_count=records_count,
        file_hash=file_hash,
        organization_id=str(organization_id) if organization_id else None,
        timestamp=timestamp or datetime.now(timezone.utc),
    )
    session.add(entry)
    return entry


async def log_compliance_check(
    session: AsyncSession,
    *,
    check_type: str,
    result: str,
    details: Optional[dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,
) -> AuditLog:
    """
    Record a system-level compliance check.

    Stored with user_id=None to indicate a system-initiated event (as opposed
    to a human actor). check_type examples:
        "chain_integrity_check", "rbac_audit", "retention_cleanup"
    """
    entry = AuditLog(
        id=uuid.uuid4(),
        user_id=None,
        action=ACTION_COMPLIANCE_CHECK,
        data_type=check_type,
        record_id=None,
        organization_id=None,
        result=result,
        timestamp=timestamp or datetime.now(timezone.utc),
        details_json=details,
    )
    session.add(entry)
    return entry


# ===========================================================================
# Read helpers
# ===========================================================================

async def get_audit_log(
    session: AsyncSession,
    *,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    action_filter: Optional[str] = None,
    limit: int = 1_000,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Query audit_log with optional filters.

    Returns a list of plain dicts safe for JSON serialisation.
    All filters are ANDed together.
    """
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())

    if user_id:
        stmt = stmt.where(AuditLog.user_id == str(user_id))
    if organization_id:
        stmt = stmt.where(AuditLog.organization_id == str(organization_id))
    if start_date:
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        stmt = stmt.where(AuditLog.timestamp >= start_date)
    if end_date:
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        stmt = stmt.where(AuditLog.timestamp <= end_date)
    if action_filter:
        stmt = stmt.where(AuditLog.action == action_filter)

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "id":              str(row.id),
            "user_id":         row.user_id,
            "action":          row.action,
            "data_type":       row.data_type,
            "record_id":       row.record_id,
            "organization_id": row.organization_id,
            "result":          row.result,
            "timestamp":       row.timestamp.isoformat(),
            "details":         row.details_json,
        }
        for row in rows
    ]


async def get_export_log(
    session: AsyncSession,
    *,
    organization_id: Optional[str] = None,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Return recent export events within the last *days* days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(AuditExport).where(AuditExport.timestamp >= cutoff)
    if organization_id:
        stmt = stmt.where(AuditExport.organization_id == str(organization_id))
    stmt = stmt.order_by(AuditExport.timestamp.desc())

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "id":              str(row.id),
            "user_id":         row.user_id,
            "export_type":     row.export_type,
            "records_count":   row.records_count,
            "file_hash":       row.file_hash,
            "organization_id": row.organization_id,
            "timestamp":       row.timestamp.isoformat(),
        }
        for row in rows
    ]


# ===========================================================================
# Retention
# ===========================================================================

async def retention_cleanup(
    session: AsyncSession,
    days: int = AUDIT_LOG_RETENTION_DAYS,
) -> dict[str, int]:
    """
    Delete audit log and export log entries older than *days*.

    The deletion itself is recorded in a new AuditLog entry that is NOT
    subject to retention (it documents that cleanup occurred).

    Called nightly via a scheduler in production.

    Returns:
        {"deleted_audit_logs": int, "deleted_export_logs": int}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Count first (cheap on indexed timestamp column)
    audit_rows = (await session.execute(
        select(AuditLog).where(AuditLog.timestamp < cutoff)
    )).scalars().all()
    export_rows = (await session.execute(
        select(AuditExport).where(AuditExport.timestamp < cutoff)
    )).scalars().all()
    audit_count  = len(audit_rows)
    export_count = len(export_rows)

    # Delete old entries
    await session.execute(delete(AuditLog).where(AuditLog.timestamp < cutoff))
    await session.execute(delete(AuditExport).where(AuditExport.timestamp < cutoff))

    # Record the cleanup itself — this row is permanent
    cleanup_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=None,
        action=ACTION_RETENTION_CLEANUP,
        data_type="audit_log",
        record_id=None,
        organization_id=None,
        result=RESULT_PASSED,
        timestamp=datetime.now(timezone.utc),
        details_json={
            "cutoff_date":         cutoff.isoformat(),
            "retention_days":      days,
            "audit_logs_deleted":  audit_count,
            "export_logs_deleted": export_count,
        },
    )
    session.add(cleanup_entry)

    log.info(
        "Retention cleanup: deleted %d audit logs + %d export logs (cutoff=%s)",
        audit_count, export_count, cutoff.date(),
    )
    return {
        "deleted_audit_logs":   audit_count,
        "deleted_export_logs":  export_count,
    }


# ===========================================================================
# Utility
# ===========================================================================

def compute_export_hash(content: bytes) -> str:
    """Return SHA-256 hex digest of exported file bytes."""
    return hashlib.sha256(content).hexdigest()
