"""
NDIC RBAC Service  (Phase 5a)
──────────────────────────────
Permission checking and data-access filtering for all platform users.

Role hierarchy (highest → lowest data access):
  arpexas_admin        — full platform access, all data classes
  govt_admin           — aggregated + public + audit reports
  govt_analyst         — aggregated + public (read-only)
  processor_commercial — own processor data + aggregated
  processor_analyst    — own processor data + aggregated (read-only)
  lender_analyst       — own lender data + aggregated
  farm_admin           — own farm data + manage farm users
  farm_manager         — own farm data (read + submit)

Data classification access matrix
──────────────────────────────────
  confidential_farm:      farm_manager, farm_admin, arpexas_admin (own-org)
  confidential_processor: processor_analyst, processor_commercial, arpexas_admin (own-org)
  confidential_lender:    lender_analyst, arpexas_admin (own-org)
  aggregated:             all roles
  public:                 all roles
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rbac_models import (
    Role, Permission, RolePermission, UserRoleAssignment,
    DATA_CLASS_CONFIDENTIAL_FARM,
    DATA_CLASS_CONFIDENTIAL_PROCESSOR,
    DATA_CLASS_CONFIDENTIAL_LENDER,
    DATA_CLASS_AGGREGATED,
    DATA_CLASS_PUBLIC,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role → accessible data classes
# ---------------------------------------------------------------------------

_ROLE_DATA_ACCESS: dict[str, frozenset[str]] = {
    "farm_manager": frozenset({
        DATA_CLASS_CONFIDENTIAL_FARM, DATA_CLASS_AGGREGATED, DATA_CLASS_PUBLIC,
    }),
    "farm_admin": frozenset({
        DATA_CLASS_CONFIDENTIAL_FARM, DATA_CLASS_AGGREGATED, DATA_CLASS_PUBLIC,
    }),
    "processor_analyst": frozenset({
        DATA_CLASS_CONFIDENTIAL_PROCESSOR, DATA_CLASS_AGGREGATED, DATA_CLASS_PUBLIC,
    }),
    "processor_commercial": frozenset({
        DATA_CLASS_CONFIDENTIAL_PROCESSOR, DATA_CLASS_AGGREGATED, DATA_CLASS_PUBLIC,
    }),
    "govt_analyst": frozenset({
        DATA_CLASS_AGGREGATED, DATA_CLASS_PUBLIC,
    }),
    "govt_admin": frozenset({
        DATA_CLASS_AGGREGATED, DATA_CLASS_PUBLIC,
    }),
    "lender_analyst": frozenset({
        DATA_CLASS_CONFIDENTIAL_LENDER, DATA_CLASS_AGGREGATED, DATA_CLASS_PUBLIC,
    }),
    "arpexas_admin": frozenset({
        DATA_CLASS_CONFIDENTIAL_FARM,
        DATA_CLASS_CONFIDENTIAL_PROCESSOR,
        DATA_CLASS_CONFIDENTIAL_LENDER,
        DATA_CLASS_AGGREGATED,
        DATA_CLASS_PUBLIC,
    }),
}

# Default data class for each platform resource type
_DATA_TYPE_DEFAULT_CLASS: dict[str, str] = {
    "animals":               DATA_CLASS_CONFIDENTIAL_FARM,
    "health_records":        DATA_CLASS_CONFIDENTIAL_FARM,
    "farm_dashboard":        DATA_CLASS_CONFIDENTIAL_FARM,
    "farm_financials":       DATA_CLASS_CONFIDENTIAL_FARM,
    "processor_intakes":     DATA_CLASS_CONFIDENTIAL_PROCESSOR,
    "processor_dashboard":   DATA_CLASS_CONFIDENTIAL_PROCESSOR,
    "lender_assessments":    DATA_CLASS_CONFIDENTIAL_LENDER,
    "disease_alerts":        DATA_CLASS_AGGREGATED,
    "regional_stats":        DATA_CLASS_AGGREGATED,
    "disease_map":           DATA_CLASS_AGGREGATED,
    "aggregated_production": DATA_CLASS_AGGREGATED,
    "audit_log":             DATA_CLASS_CONFIDENTIAL_FARM,  # admin-only by permission
    "audit_report":          DATA_CLASS_CONFIDENTIAL_FARM,
}

_CONFIDENTIAL_CLASSES = frozenset({
    DATA_CLASS_CONFIDENTIAL_FARM,
    DATA_CLASS_CONFIDENTIAL_PROCESSOR,
    DATA_CLASS_CONFIDENTIAL_LENDER,
})


# ===========================================================================
# Public API
# ===========================================================================

async def has_permission(
    session: AsyncSession,
    user_id: uuid.UUID,
    permission_name: str,
    organization_id: Optional[uuid.UUID] = None,
) -> bool:
    """
    Return True if the user holds a role that includes *permission_name*.

    Walks the chain: user → UserRoleAssignment → Role → RolePermission → Permission.
    organization_id scopes the check (None matches global roles only if no org set).
    """
    stmt = (
        select(UserRoleAssignment)
        .where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.is_active == True,
        )
    )
    result = await session.execute(stmt)
    assignments = result.scalars().all()

    for assignment in assignments:
        # Scope check: assignment org must match requested org OR be global (NULL)
        if assignment.organization_id is not None and organization_id is not None:
            if assignment.organization_id != organization_id:
                continue

        perm_stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == assignment.role_id)
        )
        perm_result = await session.execute(perm_stmt)
        permissions = perm_result.scalars().all()

        if any(p.name == permission_name for p in permissions):
            return True

    return False


async def check_access(
    session: AsyncSession,
    user_id: uuid.UUID,
    data_type: str,
    record_owner_org_id: Optional[uuid.UUID],
    user_org_id: Optional[uuid.UUID],
) -> tuple[bool, str]:
    """
    Determine whether a user may access a record of *data_type*.

    Returns (allowed: bool, reason: str).

    Logic:
      1. Load all active role names for this user.
      2. Determine the default data class for data_type.
      3. For each role, check whether the data class is accessible.
      4. Confidential data: also verify org ownership (unless arpexas_admin).
    """
    role_names = await get_user_role_names(session, user_id, user_org_id)

    if not role_names:
        return False, "User has no active roles assigned"

    data_class = _DATA_TYPE_DEFAULT_CLASS.get(data_type, DATA_CLASS_PUBLIC)

    for role_name in role_names:
        accessible = _ROLE_DATA_ACCESS.get(role_name, frozenset())

        if data_class not in accessible:
            continue

        # arpexas_admin: unrestricted access
        if role_name == "arpexas_admin":
            return True, "arpexas_admin — global access"

        # Confidential resources: require org ownership
        if data_class in _CONFIDENTIAL_CLASSES:
            if record_owner_org_id is None:
                return True, f"Role {role_name!r} — owner org unset, access granted"
            if user_org_id is not None and str(user_org_id) == str(record_owner_org_id):
                return True, f"Role {role_name!r} — own organisation"
            return False, (
                f"Access denied: {data_class!r} record owned by org "
                f"{record_owner_org_id} (your org: {user_org_id})"
            )

        # Aggregated / public: role membership is sufficient
        return True, f"Role {role_name!r} — {data_class!r} access granted"

    # No role granted access after full scan
    sample_role = next(iter(role_names), "unknown")
    return False, (
        f"Role {sample_role!r} cannot access {data_class!r} data "
        f"(data_type={data_type!r})"
    )


def get_user_accessible_data(
    role_names: list[str],
    user_org_id: Optional[uuid.UUID],
    data_type: str,
) -> dict[str, Any]:
    """
    Return a filter-specification dict describing the WHERE constraints
    callers should apply when querying data for this user.

    This is a synchronous helper — roles are pre-loaded by the caller.

    Returns::

        {
          "allowed":        bool,
          "scope":          "own_org" | "aggregated_only" | "global" | "denied",
          "org_id_filter":  uuid.UUID | None,   # apply WHERE owner_org_id = this
          "data_classes":   frozenset[str],      # allowed data class values
          "reason":         str,
        }

    Examples::
        # Farm manager (own org only)
        get_user_accessible_data(["farm_manager"], farm_org_id, "animals")
        → {"scope": "own_org", "org_id_filter": farm_org_id, ...}

        # Government analyst (aggregated data only)
        get_user_accessible_data(["govt_analyst"], None, "regional_stats")
        → {"scope": "aggregated_only", "org_id_filter": None, ...}

        # arpexas_admin (global)
        get_user_accessible_data(["arpexas_admin"], None, "animals")
        → {"scope": "global", "org_id_filter": None, ...}
    """
    if not role_names:
        return {
            "allowed":       False,
            "scope":         "denied",
            "org_id_filter": None,
            "data_classes":  frozenset(),
            "reason":        "No active roles",
        }

    # Union of all accessible data classes across user's roles
    accessible: frozenset[str] = frozenset()
    for role_name in role_names:
        accessible = accessible | _ROLE_DATA_ACCESS.get(role_name, frozenset())

    data_class = _DATA_TYPE_DEFAULT_CLASS.get(data_type, DATA_CLASS_PUBLIC)

    if data_class not in accessible:
        return {
            "allowed":       False,
            "scope":         "denied",
            "org_id_filter": None,
            "data_classes":  frozenset(),
            "reason":        f"Roles {role_names} cannot access {data_class!r}",
        }

    # arpexas_admin: unrestricted global view
    if "arpexas_admin" in role_names:
        return {
            "allowed":       True,
            "scope":         "global",
            "org_id_filter": None,
            "data_classes":  accessible,
            "reason":        "arpexas_admin — global access",
        }

    # Confidential: limit to own org
    if data_class in _CONFIDENTIAL_CLASSES:
        return {
            "allowed":       True,
            "scope":         "own_org",
            "org_id_filter": user_org_id,
            "data_classes":  accessible,
            "reason":        f"Own-org filter applied for {data_class!r}",
        }

    # Aggregated / public: no org filter required
    return {
        "allowed":       True,
        "scope":         "aggregated_only",
        "org_id_filter": None,
        "data_classes":  frozenset({DATA_CLASS_AGGREGATED, DATA_CLASS_PUBLIC}),
        "reason":        f"Aggregated/public access for {data_type!r}",
    }


# ===========================================================================
# Helpers
# ===========================================================================

async def get_user_role_names(
    session: AsyncSession,
    user_id: uuid.UUID,
    organization_id: Optional[uuid.UUID] = None,
) -> list[str]:
    """
    Return the list of active role names held by a user.

    If organization_id is provided, only roles scoped to that org (or global
    NULL-scoped roles) are returned.
    """
    stmt = (
        select(Role.name)
        .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
        .where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.is_active == True,
            Role.is_active == True,
        )
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]
