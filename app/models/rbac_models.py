"""
NDIC RBAC & Audit ORM Models  (Phase 5a)
─────────────────────────────────────────
New tables added in Phase 5a:
  role               — named permission bundle
  permission         — atomic (resource, action) capability
  role_permission    — many-to-many junction
  user_role_assignment — scoped user ↔ role mapping
  data_classification — sensitivity tag on every resource record
  audit_log          — immutable access history (3-year retention)
  audit_export       — tracks every data export event

All models share the same SQLAlchemy Base as the Phase 1 models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, Text, Integer, Boolean, DateTime,
    ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.database import Base, utc_now


# ---------------------------------------------------------------------------
# Data-class constants  (sensitivity labels)
# ---------------------------------------------------------------------------

DATA_CLASS_CONFIDENTIAL_FARM      = "confidential_farm"
DATA_CLASS_CONFIDENTIAL_PROCESSOR = "confidential_processor"
DATA_CLASS_CONFIDENTIAL_LENDER    = "confidential_lender"
DATA_CLASS_AGGREGATED             = "aggregated"
DATA_CLASS_PUBLIC                 = "public"

ALL_DATA_CLASSES: frozenset[str] = frozenset({
    DATA_CLASS_CONFIDENTIAL_FARM,
    DATA_CLASS_CONFIDENTIAL_PROCESSOR,
    DATA_CLASS_CONFIDENTIAL_LENDER,
    DATA_CLASS_AGGREGATED,
    DATA_CLASS_PUBLIC,
})


# ===========================================================================
# Role
# ===========================================================================

class Role(Base):
    """
    Named bundle of permissions.

    Eight built-in roles (seeded via scripts/seed_rbac.py):
      farm_manager, farm_admin,
      processor_analyst, processor_commercial,
      govt_analyst, govt_admin,
      lender_analyst, arpexas_admin
    """
    __tablename__ = "role"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    permissions: Mapped[List["RolePermission"]] = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )
    user_assignments: Mapped[List["UserRoleAssignment"]] = relationship(
        "UserRoleAssignment", back_populates="role"
    )

    def __repr__(self) -> str:
        return f"<Role name={self.name!r}>"


# ===========================================================================
# Permission
# ===========================================================================

class Permission(Base):
    """
    Atomic capability: (resource, action) pair.

    Examples:
        resource=animals,    action=read     → view animal records
        resource=intakes,    action=export   → download processor intake CSVs
        resource=audit_log,  action=read     → view audit trails (admin only)
        resource=users,      action=manage   → create / deactivate users
    """
    __tablename__ = "permission"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    role_links: Mapped[List["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
        Index("ix_permission_resource", "resource"),
    )

    def __repr__(self) -> str:
        return f"<Permission {self.resource}:{self.action}>"


# ===========================================================================
# RolePermission  (junction)
# ===========================================================================

class RolePermission(Base):
    """Many-to-many: Role ↔ Permission."""
    __tablename__ = "role_permission"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("role.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    role: Mapped["Role"] = relationship("Role", back_populates="permissions")
    permission: Mapped["Permission"] = relationship("Permission", back_populates="role_links")


# ===========================================================================
# UserRoleAssignment
# ===========================================================================

class UserRoleAssignment(Base):
    """
    Scoped assignment of a Role to a User within an Organisation.

    Rules:
    - organization_id = specific UUID  →  role is valid only within that org
    - organization_id = NULL           →  global scope (arpexas_admin only)
    - A user may hold multiple roles across different orgs.
    """
    __tablename__ = "user_role_assignment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("role.id", ondelete="CASCADE"), nullable=False
    )
    # NULL means global scope (arpexas_admin only)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role: Mapped["Role"] = relationship("Role", back_populates="user_assignments")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "organization_id",
                         name="uq_user_role_org"),
        Index("ix_user_role_user_id_org", "user_id", "organization_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserRoleAssignment user={self.user_id} "
            f"role={self.role_id} org={self.organization_id}>"
        )


# ===========================================================================
# DataClassification
# ===========================================================================

class DataClassification(Base):
    """
    Tags a specific record with a data sensitivity label.
    Enforced at the query layer so classified data is never sent to
    unauthorized users — filtering happens in WHERE clauses, not after fetch.

    data_class must be one of the DATA_CLASS_* constants.
    owner_org_id identifies the organisation that owns this record.
    """
    __tablename__ = "data_classification"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data_class: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_data_classification_resource", "resource_type", "resource_id"),
        Index("ix_data_classification_class", "data_class"),
    )

    def __repr__(self) -> str:
        return (
            f"<DataClassification {self.resource_type}/{self.resource_id}"
            f" → {self.data_class}>"
        )


# ===========================================================================
# AuditLog
# ===========================================================================

class AuditLog(Base):
    """
    Immutable record of every significant action taken on the platform.

    Retention: 3 years (FMARD compliance window).
    Privacy:   No PII stored — user IDs and resource IDs only.
    Actions:   view, export, create, update, delete, verify_signature,
               compliance_check, retention_cleanup.
    """
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    data_type: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False)  # allowed|denied|error
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    # Extra non-PII context: IP hash, endpoint path, row counts
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_audit_log_user_ts",  "user_id",        "timestamp"),
        Index("ix_audit_log_org_ts",   "organization_id", "timestamp"),
        Index("ix_audit_log_action",   "action"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.user_id} at {self.timestamp}>"


# ===========================================================================
# AuditExport
# ===========================================================================

class AuditExport(Base):
    """
    Records every data export event.

    file_hash: SHA-256 of the exported file content — enables post-hoc
    integrity verification ("was the file modified after export?").
    """
    __tablename__ = "audit_export"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    export_type: Mapped[str] = mapped_column(String(64), nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_audit_export_user_ts", "user_id", "timestamp"),
        Index("ix_audit_export_org_ts",  "organization_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditExport type={self.export_type} by={self.user_id}>"
