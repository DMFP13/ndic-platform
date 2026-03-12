#!/usr/bin/env python3
"""
NDIC RBAC Seed Script  (Phase 5a)
───────────────────────────────────
Initialise the 8 canonical roles, their permissions, and default data
classifications for all platform resource types.

Usage::

    # Dry-run (print what would be created, no DB writes):
    python scripts/seed_rbac.py --dry-run

    # Seed against a live database:
    DATABASE_URL=postgresql+asyncpg://user:pass@localhost/ndic \\
        python scripts/seed_rbac.py

    # Assign a role to an existing user:
    python scripts/seed_rbac.py --assign-role \\
        --user-id <uuid> --role farm_manager --org-id <uuid>

Roles created
─────────────
  farm_manager        — daily submissions + own-farm dashboard
  farm_admin          — farm_manager + register animals + manage farm users
  processor_analyst   — view processor intakes + aggregated data
  processor_commercial— processor_analyst + submit intakes + financials
  govt_analyst        — aggregated + public data (read-only)
  govt_admin          — govt_analyst + export + audit reports
  lender_analyst      — lender assessments + aggregated herd data
  arpexas_admin       — full platform access
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Role + permission definitions
# ---------------------------------------------------------------------------

ROLES: list[dict] = [
    {"name": "farm_manager",          "description": "Daily health submissions and own-farm dashboard"},
    {"name": "farm_admin",            "description": "Farm manager + animal registration + user management"},
    {"name": "processor_analyst",     "description": "View processor intakes and aggregated production data"},
    {"name": "processor_commercial",  "description": "Processor analyst + submit intakes + financial data"},
    {"name": "govt_analyst",          "description": "Read-only access to aggregated and public data"},
    {"name": "govt_admin",            "description": "Government analyst + export + audit report requests"},
    {"name": "lender_analyst",        "description": "Lender assessments + aggregated herd collateral data"},
    {"name": "arpexas_admin",         "description": "Full platform access — ARPEXAS staff only"},
]

# Each permission: (name, resource, action, description)
PERMISSIONS: list[tuple[str, str, str, str]] = [
    # ── Animals
    ("view_own_animals",         "animals",         "read",   "View animals registered to own farm"),
    ("register_animals",         "animals",         "write",  "Register new animals"),
    ("view_all_animals",         "animals",         "admin",  "View animals across all farms"),

    # ── Health Records
    ("submit_health_records",    "health_records",  "write",  "Submit health observations"),
    ("view_own_health_records",  "health_records",  "read",   "View health records for own farm"),
    ("view_all_health_records",  "health_records",  "admin",  "View health records across all farms"),

    # ── Dashboards
    ("view_farm_dashboard",      "farm_dashboard",  "read",   "View own farm summary dashboard"),
    ("view_processor_dashboard", "processor_dashboard", "read", "View own processor analytics"),

    # ── Processor Intakes
    ("submit_intakes",           "intakes",         "write",  "Submit processor milk intake records"),
    ("view_own_intakes",         "intakes",         "read",   "View own processor intake history"),
    ("view_aggregated_intakes",  "intakes",         "aggregated", "View aggregated intake statistics"),

    # ── Aggregated / Public Data
    ("view_aggregated_data",     "aggregated",      "read",   "View regional aggregated production data"),
    ("view_disease_map",         "disease_map",     "read",   "View disease alert map"),
    ("view_regional_stats",      "regional_stats",  "read",   "View state/LGA production statistics"),

    # ── Lender Assessments
    ("submit_lender_assessments","lender_assessments","write","Submit collateral assessments"),
    ("view_own_assessments",     "lender_assessments","read", "View own lender assessment history"),
    ("view_aggregated_herd_data","herd_aggregated", "read",   "View aggregated herd financials"),

    # ── Exports
    ("export_data",              "exports",         "export", "Download data as CSV/JSON"),

    # ── Users
    ("manage_farm_users",        "users",           "manage", "Create/deactivate users within own farm"),
    ("manage_all_users",         "users",           "admin",  "Manage all platform users"),

    # ── Audit + Compliance
    ("view_audit_log",           "audit_log",       "read",   "View audit trail entries"),
    ("request_audit_reports",    "audit_log",       "export", "Request full audit reports"),
    ("run_compliance_checks",    "compliance",      "admin",  "Run chain integrity + RBAC audits"),
    ("manage_data_deletion",     "data_deletion",   "admin",  "Process right-to-be-forgotten requests"),
]

# Role → list of permission names
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "farm_manager": [
        "view_own_animals",
        "submit_health_records",
        "view_own_health_records",
        "view_farm_dashboard",
        "view_aggregated_data",
        "view_disease_map",
    ],
    "farm_admin": [
        "view_own_animals",
        "register_animals",
        "submit_health_records",
        "view_own_health_records",
        "view_farm_dashboard",
        "view_aggregated_data",
        "view_disease_map",
        "manage_farm_users",
    ],
    "processor_analyst": [
        "view_own_intakes",
        "view_aggregated_intakes",
        "view_processor_dashboard",
        "view_aggregated_data",
        "view_disease_map",
        "view_regional_stats",
    ],
    "processor_commercial": [
        "submit_intakes",
        "view_own_intakes",
        "view_aggregated_intakes",
        "view_processor_dashboard",
        "view_aggregated_data",
        "view_disease_map",
        "view_regional_stats",
        "export_data",
    ],
    "govt_analyst": [
        "view_aggregated_data",
        "view_disease_map",
        "view_regional_stats",
    ],
    "govt_admin": [
        "view_aggregated_data",
        "view_disease_map",
        "view_regional_stats",
        "export_data",
        "view_audit_log",
        "request_audit_reports",
    ],
    "lender_analyst": [
        "view_own_assessments",
        "submit_lender_assessments",
        "view_aggregated_herd_data",
        "view_aggregated_data",
    ],
    "arpexas_admin": [
        "view_own_animals",
        "register_animals",
        "view_all_animals",
        "submit_health_records",
        "view_own_health_records",
        "view_all_health_records",
        "view_farm_dashboard",
        "view_processor_dashboard",
        "submit_intakes",
        "view_own_intakes",
        "view_aggregated_intakes",
        "view_aggregated_data",
        "view_disease_map",
        "view_regional_stats",
        "submit_lender_assessments",
        "view_own_assessments",
        "view_aggregated_herd_data",
        "export_data",
        "manage_farm_users",
        "manage_all_users",
        "view_audit_log",
        "request_audit_reports",
        "run_compliance_checks",
        "manage_data_deletion",
    ],
}

# Default data classification for each resource type
DATA_CLASSIFICATIONS: list[dict] = [
    {"resource_type": "animals",               "data_class": "confidential_farm"},
    {"resource_type": "health_records",        "data_class": "confidential_farm"},
    {"resource_type": "farm_dashboard",        "data_class": "confidential_farm"},
    {"resource_type": "farm_financials",       "data_class": "confidential_farm"},
    {"resource_type": "processor_intakes",     "data_class": "confidential_processor"},
    {"resource_type": "processor_dashboard",   "data_class": "confidential_processor"},
    {"resource_type": "lender_assessments",    "data_class": "confidential_lender"},
    {"resource_type": "disease_alerts",        "data_class": "aggregated"},
    {"resource_type": "regional_stats",        "data_class": "aggregated"},
    {"resource_type": "disease_map",           "data_class": "aggregated"},
    {"resource_type": "aggregated_production", "data_class": "aggregated"},
    {"resource_type": "audit_log",             "data_class": "confidential_farm"},
]


# ===========================================================================
# Seed logic
# ===========================================================================

async def seed(dry_run: bool = False) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.models.rbac_models import (
        Role, Permission, RolePermission, DataClassification,
    )
    from config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        print("=" * 60)
        print("  NDIC RBAC Seed")
        print("=" * 60)

        # ── Permissions ───────────────────────────────────────────────────
        perm_map: dict[str, Permission] = {}
        for name, resource, action, description in PERMISSIONS:
            result = await session.execute(
                select(Permission).where(Permission.name == name)
            )
            existing = result.scalar_one_or_none()
            if existing:
                perm_map[name] = existing
                if not dry_run:
                    print(f"  [skip] Permission already exists: {name}")
            else:
                perm = Permission(
                    id=uuid.uuid4(),
                    name=name,
                    resource=resource,
                    action=action,
                    description=description,
                )
                perm_map[name] = perm
                if not dry_run:
                    session.add(perm)
                print(f"  [+] Permission: {name}  ({resource}:{action})")

        # ── Roles + RolePermissions ───────────────────────────────────────
        role_map: dict[str, Role] = {}
        for role_def in ROLES:
            rname = role_def["name"]
            result = await session.execute(
                select(Role).where(Role.name == rname)
            )
            existing_role = result.scalar_one_or_none()
            if existing_role:
                role_map[rname] = existing_role
                if not dry_run:
                    print(f"  [skip] Role already exists: {rname}")
            else:
                role = Role(
                    id=uuid.uuid4(),
                    name=rname,
                    description=role_def["description"],
                )
                role_map[rname] = role
                if not dry_run:
                    session.add(role)
                print(f"  [+] Role: {rname}")

        if not dry_run:
            await session.flush()   # get IDs before linking

        # ── RolePermission links ──────────────────────────────────────────
        for rname, perm_names in ROLE_PERMISSIONS.items():
            role = role_map.get(rname)
            if role is None:
                continue
            for pname in perm_names:
                perm = perm_map.get(pname)
                if perm is None:
                    print(f"  [WARN] Permission '{pname}' not found for role '{rname}'")
                    continue
                if not dry_run:
                    # Check if link already exists
                    rp_exists = await session.execute(
                        select(RolePermission).where(
                            RolePermission.role_id       == role.id,
                            RolePermission.permission_id == perm.id,
                        )
                    )
                    if rp_exists.scalar_one_or_none() is None:
                        session.add(RolePermission(
                            role_id=role.id, permission_id=perm.id
                        ))

        # ── DataClassification defaults ───────────────────────────────────
        for dc in DATA_CLASSIFICATIONS:
            dc_exists = await session.execute(
                select(DataClassification).where(
                    DataClassification.resource_type == dc["resource_type"],
                    DataClassification.resource_id   == "__default__",
                )
            )
            if dc_exists.scalar_one_or_none() is None:
                if not dry_run:
                    session.add(DataClassification(
                        id=uuid.uuid4(),
                        resource_id="__default__",
                        resource_type=dc["resource_type"],
                        data_class=dc["data_class"],
                        owner_org_id=None,
                    ))
                print(f"  [+] DataClass default: {dc['resource_type']} → {dc['data_class']}")

        if not dry_run:
            await session.commit()
            print("\n  ✓ RBAC seed complete")
        else:
            print("\n  [dry-run] No changes written to DB")

    await engine.dispose()


async def assign_role(
    user_id_str: str,
    role_name: str,
    org_id_str: Optional[str] = None,
) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.models.rbac_models import Role, UserRoleAssignment
    from config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    user_uuid = uuid.UUID(user_id_str)
    org_uuid  = uuid.UUID(org_id_str) if org_id_str else None

    async with factory() as session:
        role_result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role_result.scalar_one_or_none()
        if role is None:
            print(f"ERROR: Role '{role_name}' not found — run seed first")
            return

        assignment = UserRoleAssignment(
            id=uuid.uuid4(),
            user_id=user_uuid,
            role_id=role.id,
            organization_id=org_uuid,
        )
        session.add(assignment)
        await session.commit()
        print(
            f"  ✓ Assigned role '{role_name}' to user {user_id_str}"
            f"{f' in org {org_id_str}' if org_id_str else ' (global)'}"
        )

    await engine.dispose()


from typing import Optional   # noqa: E402


# ===========================================================================
# CLI
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Seed NDIC RBAC roles, permissions, and data classifications")
    p.add_argument("--dry-run", action="store_true",  help="Print plan without writing to DB")
    p.add_argument("--assign-role", action="store_true", help="Assign a role to a user")
    p.add_argument("--user-id",  default=None, help="User UUID (for --assign-role)")
    p.add_argument("--role",     default=None, help="Role name (for --assign-role)")
    p.add_argument("--org-id",   default=None, help="Organisation UUID (omit for global scope)")
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()

    if args.assign_role:
        if not args.user_id or not args.role:
            print("ERROR: --assign-role requires --user-id and --role")
            sys.exit(1)
        asyncio.run(assign_role(args.user_id, args.role, args.org_id))
    else:
        asyncio.run(seed(dry_run=args.dry_run))
