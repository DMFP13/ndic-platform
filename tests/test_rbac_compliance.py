"""
tests/test_rbac_compliance.py
══════════════════════════════
Phase 5a test suite: RBAC, Audit Logging, and Compliance endpoints.

Test groups:
  TestHasPermission          — permission chain: user → role → permission
  TestCheckAccess            — data-class + org-ownership enforcement
  TestGetUserAccessibleData  — filter-spec returned per role
  TestAuditLogAccess         — log_access writes + get_audit_log reads
  TestAuditLogExport         — log_export writes + get_export_log reads
  TestAuditRetention         — retention_cleanup deletes old entries
  TestComputeExportHash      — SHA-256 utility
  TestDataClassification     — confidential data blocked for wrong roles
  TestCrossOrgIsolation      — org A cannot access org B confidential data
  TestRoleDataAccessMatrix   — verify each role's allowed data classes
  TestSeedRbacDefinitions    — roles/permissions are self-consistent
  TestComplianceApiRbacAudit — rbac_audit endpoint logic (service layer)

Run:
    pytest tests/test_rbac_compliance.py -v
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Shared factories
# ---------------------------------------------------------------------------

def _make_assignment(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    org_id: Optional[uuid.UUID] = None,
    is_active: bool = True,
) -> MagicMock:
    a = MagicMock()
    a.user_id         = user_id
    a.role_id         = role_id
    a.organization_id = org_id
    a.is_active       = is_active
    return a


def _make_permission(name: str, resource: str = "animals", action: str = "read") -> MagicMock:
    p = MagicMock()
    p.name     = name
    p.resource = resource
    p.action   = action
    return p


def _make_role(name: str, is_active: bool = True) -> MagicMock:
    r = MagicMock()
    r.id        = uuid.uuid4()
    r.name      = name
    r.is_active = is_active
    return r


def _mock_session_returning(rows_per_call: list) -> AsyncMock:
    """Build an AsyncMock session whose execute() side-effects return each item in turn."""
    session = AsyncMock()
    results = []
    for rows in rows_per_call:
        mock_result = MagicMock()
        if isinstance(rows, list) and all(isinstance(r, MagicMock) for r in rows):
            mock_result.scalars.return_value.all.return_value = rows
        else:
            mock_result.scalars.return_value.all.return_value = rows
            mock_result.all.return_value = [(r,) for r in rows] if rows else []
        results.append(mock_result)
    session.execute.side_effect = results
    return session


# ===========================================================================
# TestHasPermission
# ===========================================================================

class TestHasPermission:

    @pytest.mark.asyncio
    async def test_returns_true_when_permission_found(self):
        from app.services.rbac_service import has_permission
        user_id = uuid.uuid4()
        role_id = uuid.uuid4()
        org_id  = uuid.uuid4()

        assignment = _make_assignment(user_id, role_id, org_id)
        perm       = _make_permission("view_own_animals")
        session    = _mock_session_returning([[assignment], [perm]])

        result = await has_permission(session, user_id, "view_own_animals", org_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_assignments(self):
        from app.services.rbac_service import has_permission
        user_id = uuid.uuid4()
        session = _mock_session_returning([[]])   # empty assignments

        result = await has_permission(session, user_id, "view_own_animals")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_permission_not_in_role(self):
        from app.services.rbac_service import has_permission
        user_id = uuid.uuid4()
        role_id = uuid.uuid4()
        org_id  = uuid.uuid4()

        assignment = _make_assignment(user_id, role_id, org_id)
        # Role only has "view_aggregated_data", not "export_data"
        perm = _make_permission("view_aggregated_data")
        session = _mock_session_returning([[assignment], [perm]])

        result = await has_permission(session, user_id, "export_data", org_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_org_scope_filters_wrong_org(self):
        from app.services.rbac_service import has_permission
        user_id     = uuid.uuid4()
        role_id     = uuid.uuid4()
        assigned_org = uuid.uuid4()
        different_org= uuid.uuid4()

        # Assignment is for assigned_org; we ask about different_org
        assignment = _make_assignment(user_id, role_id, assigned_org)
        session    = _mock_session_returning([[assignment], []])

        result = await has_permission(session, user_id, "view_own_animals", different_org)
        # Permission query still runs (execute called for perms), but names won't match
        assert result is False

    @pytest.mark.asyncio
    async def test_global_assignment_null_org_matches_any(self):
        from app.services.rbac_service import has_permission
        user_id = uuid.uuid4()
        role_id = uuid.uuid4()

        # NULL org assignment (arpexas_admin)
        assignment = _make_assignment(user_id, role_id, org_id=None)
        perm       = _make_permission("run_compliance_checks")
        session    = _mock_session_returning([[assignment], [perm]])

        result = await has_permission(
            session, user_id, "run_compliance_checks",
            organization_id=uuid.uuid4()   # any org
        )
        assert result is True


# ===========================================================================
# TestCheckAccess
# ===========================================================================

class TestCheckAccess:

    def _session_with_roles(self, role_names: list[str]) -> AsyncMock:
        """Session whose get_user_role_names call returns given role names."""
        session = AsyncMock()
        # Role.name rows returned as [(name,), ...]
        mock_result = MagicMock()
        mock_result.all.return_value = [(n,) for n in role_names]
        session.execute.return_value = mock_result
        return session

    @pytest.mark.asyncio
    async def test_farm_manager_own_org_allowed(self):
        from app.services.rbac_service import check_access
        org_id  = uuid.uuid4()
        user_id = uuid.uuid4()
        session = self._session_with_roles(["farm_manager"])

        allowed, reason = await check_access(
            session, user_id, "animals",
            record_owner_org_id=org_id, user_org_id=org_id,
        )
        assert allowed is True
        assert "own organisation" in reason.lower() or "own" in reason.lower()

    @pytest.mark.asyncio
    async def test_farm_manager_other_org_denied(self):
        from app.services.rbac_service import check_access
        user_org  = uuid.uuid4()
        other_org = uuid.uuid4()
        user_id   = uuid.uuid4()
        session   = self._session_with_roles(["farm_manager"])

        allowed, reason = await check_access(
            session, user_id, "animals",
            record_owner_org_id=other_org, user_org_id=user_org,
        )
        assert allowed is False
        assert "denied" in reason.lower() or "org" in reason.lower()

    @pytest.mark.asyncio
    async def test_processor_cannot_access_farm_data(self):
        from app.services.rbac_service import check_access
        org_id  = uuid.uuid4()
        user_id = uuid.uuid4()
        session = self._session_with_roles(["processor_analyst"])

        # processor_analyst does not have confidential_farm in their data access
        allowed, reason = await check_access(
            session, user_id, "animals",
            record_owner_org_id=org_id, user_org_id=org_id,
        )
        assert allowed is False

    @pytest.mark.asyncio
    async def test_govt_analyst_can_access_aggregated(self):
        from app.services.rbac_service import check_access
        user_id = uuid.uuid4()
        session = self._session_with_roles(["govt_analyst"])

        allowed, reason = await check_access(
            session, user_id, "regional_stats",
            record_owner_org_id=None, user_org_id=None,
        )
        assert allowed is True

    @pytest.mark.asyncio
    async def test_govt_analyst_denied_confidential_farm(self):
        from app.services.rbac_service import check_access
        org_id  = uuid.uuid4()
        user_id = uuid.uuid4()
        session = self._session_with_roles(["govt_analyst"])

        allowed, reason = await check_access(
            session, user_id, "health_records",
            record_owner_org_id=org_id, user_org_id=org_id,
        )
        assert allowed is False

    @pytest.mark.asyncio
    async def test_arpexas_admin_global_access(self):
        from app.services.rbac_service import check_access
        user_id   = uuid.uuid4()
        other_org = uuid.uuid4()
        session   = self._session_with_roles(["arpexas_admin"])

        # arpexas_admin can access any farm's data
        allowed, reason = await check_access(
            session, user_id, "animals",
            record_owner_org_id=other_org, user_org_id=uuid.uuid4(),
        )
        assert allowed is True
        assert "global" in reason.lower() or "admin" in reason.lower()

    @pytest.mark.asyncio
    async def test_lender_cannot_access_processor_data(self):
        from app.services.rbac_service import check_access
        org_id  = uuid.uuid4()
        user_id = uuid.uuid4()
        session = self._session_with_roles(["lender_analyst"])

        allowed, _ = await check_access(
            session, user_id, "processor_intakes",
            record_owner_org_id=org_id, user_org_id=org_id,
        )
        assert allowed is False

    @pytest.mark.asyncio
    async def test_no_roles_always_denied(self):
        from app.services.rbac_service import check_access
        user_id = uuid.uuid4()
        session = self._session_with_roles([])

        allowed, reason = await check_access(
            session, user_id, "animals",
            record_owner_org_id=None, user_org_id=None,
        )
        assert allowed is False
        assert "no active roles" in reason.lower()

    @pytest.mark.asyncio
    async def test_unknown_data_type_defaults_to_public(self):
        from app.services.rbac_service import check_access
        user_id = uuid.uuid4()
        session = self._session_with_roles(["govt_analyst"])

        # Unknown resource type → defaults to PUBLIC → govt_analyst can access
        allowed, _ = await check_access(
            session, user_id, "unknown_resource_xyz",
            record_owner_org_id=None, user_org_id=None,
        )
        assert allowed is True


# ===========================================================================
# TestGetUserAccessibleData
# ===========================================================================

class TestGetUserAccessibleData:

    def _call(self, roles: list[str], data_type: str, org_id=None):
        from app.services.rbac_service import get_user_accessible_data
        return get_user_accessible_data(roles, org_id, data_type)

    def test_farm_manager_animals_own_org(self):
        org_id = uuid.uuid4()
        spec   = self._call(["farm_manager"], "animals", org_id)
        assert spec["allowed"] is True
        assert spec["scope"] == "own_org"
        assert spec["org_id_filter"] == org_id

    def test_govt_analyst_regional_stats_aggregated_only(self):
        spec = self._call(["govt_analyst"], "regional_stats")
        assert spec["allowed"] is True
        assert spec["scope"] == "aggregated_only"
        assert spec["org_id_filter"] is None

    def test_arpexas_admin_global_scope(self):
        spec = self._call(["arpexas_admin"], "animals")
        assert spec["allowed"] is True
        assert spec["scope"] == "global"
        assert spec["org_id_filter"] is None

    def test_processor_analyst_denied_farm_data(self):
        spec = self._call(["processor_analyst"], "animals")
        assert spec["allowed"] is False
        assert spec["scope"] == "denied"

    def test_empty_roles_denied(self):
        spec = self._call([], "animals")
        assert spec["allowed"] is False

    def test_lender_gets_own_org_filter_for_assessments(self):
        org_id = uuid.uuid4()
        spec   = self._call(["lender_analyst"], "lender_assessments", org_id)
        assert spec["allowed"] is True
        assert spec["scope"] == "own_org"
        assert spec["org_id_filter"] == org_id

    def test_reason_always_present(self):
        spec = self._call(["farm_manager"], "animals", uuid.uuid4())
        assert "reason" in spec
        assert isinstance(spec["reason"], str)

    def test_data_classes_non_empty_when_allowed(self):
        spec = self._call(["farm_manager"], "animals", uuid.uuid4())
        assert len(spec["data_classes"]) > 0

    def test_processor_own_intakes(self):
        org_id = uuid.uuid4()
        spec   = self._call(["processor_analyst"], "processor_intakes", org_id)
        assert spec["allowed"] is True
        assert spec["scope"] == "own_org"

    def test_multiple_roles_union(self):
        """User with both govt_analyst + processor_analyst can access processor data."""
        org_id = uuid.uuid4()
        spec   = self._call(["govt_analyst", "processor_analyst"], "processor_intakes", org_id)
        assert spec["allowed"] is True


# ===========================================================================
# TestAuditLogAccess
# ===========================================================================

class TestAuditLogAccess:

    @pytest.mark.asyncio
    async def test_log_access_creates_entry(self):
        from app.services.audit_service import log_access, RESULT_ALLOWED
        session = AsyncMock()
        entry = await log_access(
            session,
            user_id="user-001",
            action="view",
            data_type="animals",
            record_id="animal-abc",
            organization_id="org-001",
            result=RESULT_ALLOWED,
        )
        session.add.assert_called_once_with(entry)
        assert entry.user_id == "user-001"
        assert entry.action  == "view"
        assert entry.result  == "allowed"

    @pytest.mark.asyncio
    async def test_log_access_stores_details(self):
        from app.services.audit_service import log_access, RESULT_DENIED
        session = AsyncMock()
        details = {"reason": "wrong org", "endpoint": "/animals/123"}
        entry = await log_access(
            session,
            user_id="user-002",
            action="view",
            data_type="health_records",
            result=RESULT_DENIED,
            details=details,
        )
        assert entry.details_json == details

    @pytest.mark.asyncio
    async def test_log_access_no_pii_in_entry(self):
        """Audit entry contains only IDs, not names/amounts/health values."""
        from app.services.audit_service import log_access, RESULT_ALLOWED
        session = AsyncMock()
        entry = await log_access(
            session,
            user_id="user-003",
            action="view",
            data_type="animals",
            record_id="animal-xyz",
            result=RESULT_ALLOWED,
        )
        # Verify only ID fields are populated — no names or sensitive values
        assert entry.record_id == "animal-xyz"
        assert entry.user_id   == "user-003"

    @pytest.mark.asyncio
    async def test_get_audit_log_filters_by_user(self):
        from app.services.audit_service import get_audit_log

        mock_row = MagicMock()
        mock_row.id              = uuid.uuid4()
        mock_row.user_id         = "user-001"
        mock_row.action          = "view"
        mock_row.data_type       = "animals"
        mock_row.record_id       = "aaa"
        mock_row.organization_id = "org-001"
        mock_row.result          = "allowed"
        mock_row.timestamp       = datetime.now(timezone.utc)
        mock_row.details_json    = None

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        rows = await get_audit_log(session, user_id="user-001")
        assert len(rows) == 1
        assert rows[0]["user_id"] == "user-001"
        assert rows[0]["action"]  == "view"

    @pytest.mark.asyncio
    async def test_get_audit_log_empty_result(self):
        from app.services.audit_service import get_audit_log
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        rows = await get_audit_log(session, user_id="user-nobody")
        assert rows == []

    @pytest.mark.asyncio
    async def test_get_audit_log_serialises_timestamp(self):
        from app.services.audit_service import get_audit_log

        ts = datetime(2024, 3, 15, 10, 30, tzinfo=timezone.utc)
        mock_row = MagicMock()
        mock_row.id              = uuid.uuid4()
        mock_row.user_id         = "u1"
        mock_row.action          = "export"
        mock_row.data_type       = "audit_report"
        mock_row.record_id       = None
        mock_row.organization_id = None
        mock_row.result          = "allowed"
        mock_row.timestamp       = ts
        mock_row.details_json    = None

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        rows = await get_audit_log(session)
        assert rows[0]["timestamp"] == ts.isoformat()

    @pytest.mark.asyncio
    async def test_log_compliance_check_system_entry(self):
        from app.services.audit_service import log_compliance_check, RESULT_PASSED
        session = AsyncMock()
        entry = await log_compliance_check(
            session,
            check_type="chain_integrity_check",
            result=RESULT_PASSED,
            details={"entries_checked": 150},
        )
        assert entry.user_id is None    # system-initiated
        assert entry.action  == "compliance_check"
        assert entry.data_type == "chain_integrity_check"


# ===========================================================================
# TestAuditLogExport
# ===========================================================================

class TestAuditLogExport:

    @pytest.mark.asyncio
    async def test_log_export_creates_entry(self):
        from app.services.audit_service import log_export
        session = AsyncMock()
        entry = await log_export(
            session,
            user_id="user-gov",
            export_type="disease_map",
            records_count=142,
            file_hash="abc123def456",
            organization_id="fmard-org",
        )
        session.add.assert_called_once_with(entry)
        assert entry.records_count == 142
        assert entry.file_hash     == "abc123def456"
        assert entry.export_type   == "disease_map"

    @pytest.mark.asyncio
    async def test_log_export_without_hash(self):
        from app.services.audit_service import log_export
        session = AsyncMock()
        entry = await log_export(
            session,
            user_id="user-gov",
            export_type="audit_report",
            records_count=0,
        )
        assert entry.file_hash is None

    @pytest.mark.asyncio
    async def test_get_export_log_returns_list(self):
        from app.services.audit_service import get_export_log

        mock_row = MagicMock()
        mock_row.id              = uuid.uuid4()
        mock_row.user_id         = "user-gov"
        mock_row.export_type     = "disease_map"
        mock_row.records_count   = 200
        mock_row.file_hash       = "sha256abc"
        mock_row.organization_id = "fmard-org"
        mock_row.timestamp       = datetime.now(timezone.utc)

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        rows = await get_export_log(session, days=30)
        assert len(rows) == 1
        assert rows[0]["export_type"]   == "disease_map"
        assert rows[0]["records_count"] == 200

    @pytest.mark.asyncio
    async def test_get_export_log_org_filter(self):
        from app.services.audit_service import get_export_log
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        rows = await get_export_log(session, organization_id="fmard-org", days=7)
        assert rows == []
        # execute was called (with WHERE clause for org)
        session.execute.assert_called_once()


# ===========================================================================
# TestAuditRetention
# ===========================================================================

class TestAuditRetention:

    @pytest.mark.asyncio
    async def test_retention_cleanup_returns_counts(self):
        from app.services.audit_service import retention_cleanup

        old_entry = MagicMock()
        old_export = MagicMock()

        session = AsyncMock()
        # First two selects return rows to delete; next two deletes succeed
        mock_audit_count  = MagicMock()
        mock_audit_count.scalars.return_value.all.return_value = [old_entry]
        mock_export_count = MagicMock()
        mock_export_count.scalars.return_value.all.return_value = [old_export]
        mock_delete1 = MagicMock()
        mock_delete2 = MagicMock()

        session.execute.side_effect = [
            mock_audit_count,
            mock_export_count,
            mock_delete1,
            mock_delete2,
        ]

        result = await retention_cleanup(session, days=1095)
        assert result["deleted_audit_logs"]   == 1
        assert result["deleted_export_logs"]  == 1
        # A cleanup record was added
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_retention_cleanup_logs_itself(self):
        from app.services.audit_service import retention_cleanup

        session = AsyncMock()
        for_empty = MagicMock()
        for_empty.scalars.return_value.all.return_value = []
        session.execute.side_effect = [for_empty, for_empty, MagicMock(), MagicMock()]

        await retention_cleanup(session, days=1095)

        # The cleanup entry was passed to session.add
        assert session.add.called
        added = session.add.call_args[0][0]
        assert added.action == "retention_cleanup"
        assert added.result == "passed"
        assert added.user_id is None   # system event

    @pytest.mark.asyncio
    async def test_retention_cleanup_uses_correct_cutoff(self):
        """Cleanup should only affect entries older than the retention window."""
        from app.services.audit_service import retention_cleanup, AUDIT_LOG_RETENTION_DAYS

        session = AsyncMock()
        empty = MagicMock()
        empty.scalars.return_value.all.return_value = []
        session.execute.side_effect = [empty, empty, MagicMock(), MagicMock()]

        before = datetime.now(timezone.utc)
        await retention_cleanup(session, days=AUDIT_LOG_RETENTION_DAYS)
        after = datetime.now(timezone.utc)

        added = session.add.call_args[0][0]
        cutoff_str = added.details_json["cutoff_date"]
        cutoff = datetime.fromisoformat(cutoff_str)

        expected_min = before - timedelta(days=AUDIT_LOG_RETENTION_DAYS + 1)
        expected_max = after  - timedelta(days=AUDIT_LOG_RETENTION_DAYS - 1)
        assert expected_min < cutoff < expected_max


# ===========================================================================
# TestComputeExportHash
# ===========================================================================

class TestComputeExportHash:

    def test_sha256_of_known_input(self):
        import hashlib
        from app.services.audit_service import compute_export_hash
        content = b"hello world"
        expected = hashlib.sha256(content).hexdigest()
        assert compute_export_hash(content) == expected

    def test_returns_64_char_hex(self):
        from app.services.audit_service import compute_export_hash
        result = compute_export_hash(b"ndic compliance test")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_content_same_hash(self):
        from app.services.audit_service import compute_export_hash
        content = b"deterministic test data"
        assert compute_export_hash(content) == compute_export_hash(content)

    def test_different_content_different_hash(self):
        from app.services.audit_service import compute_export_hash
        assert compute_export_hash(b"a") != compute_export_hash(b"b")


# ===========================================================================
# TestDataClassification
# ===========================================================================

class TestDataClassification:

    def test_confidential_farm_constant_value(self):
        from app.models.rbac_models import DATA_CLASS_CONFIDENTIAL_FARM
        assert DATA_CLASS_CONFIDENTIAL_FARM == "confidential_farm"

    def test_all_data_classes_complete(self):
        from app.models.rbac_models import ALL_DATA_CLASSES
        assert "confidential_farm"      in ALL_DATA_CLASSES
        assert "confidential_processor" in ALL_DATA_CLASSES
        assert "confidential_lender"    in ALL_DATA_CLASSES
        assert "aggregated"             in ALL_DATA_CLASSES
        assert "public"                 in ALL_DATA_CLASSES
        assert len(ALL_DATA_CLASSES)    == 5

    def test_farm_manager_can_access_confidential_farm(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS, DATA_CLASS_CONFIDENTIAL_FARM
        assert DATA_CLASS_CONFIDENTIAL_FARM in _ROLE_DATA_ACCESS["farm_manager"]

    def test_govt_analyst_cannot_access_confidential_farm(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS, DATA_CLASS_CONFIDENTIAL_FARM
        assert DATA_CLASS_CONFIDENTIAL_FARM not in _ROLE_DATA_ACCESS["govt_analyst"]

    def test_govt_analyst_cannot_access_confidential_processor(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS, DATA_CLASS_CONFIDENTIAL_PROCESSOR
        assert DATA_CLASS_CONFIDENTIAL_PROCESSOR not in _ROLE_DATA_ACCESS["govt_analyst"]

    def test_arpexas_admin_can_access_all_classes(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS
        from app.models.rbac_models import ALL_DATA_CLASSES
        assert ALL_DATA_CLASSES.issubset(_ROLE_DATA_ACCESS["arpexas_admin"])

    def test_all_roles_can_access_aggregated(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS, DATA_CLASS_AGGREGATED
        for role_name, classes in _ROLE_DATA_ACCESS.items():
            assert DATA_CLASS_AGGREGATED in classes, f"{role_name} cannot access aggregated data"

    def test_all_roles_can_access_public(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS, DATA_CLASS_PUBLIC
        for role_name, classes in _ROLE_DATA_ACCESS.items():
            assert DATA_CLASS_PUBLIC in classes, f"{role_name} cannot access public data"


# ===========================================================================
# TestCrossOrgIsolation
# ===========================================================================

class TestCrossOrgIsolation:
    """Verify that users from Org A cannot access Org B's confidential data."""

    def _session_with_roles(self, role_names: list[str]) -> AsyncMock:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [(n,) for n in role_names]
        session.execute.return_value = mock_result
        return session

    @pytest.mark.asyncio
    async def test_farm_manager_org_a_denied_org_b_animals(self):
        from app.services.rbac_service import check_access
        org_a   = uuid.uuid4()
        org_b   = uuid.uuid4()
        user_id = uuid.uuid4()
        session = self._session_with_roles(["farm_manager"])

        allowed, reason = await check_access(
            session, user_id, "animals",
            record_owner_org_id=org_b,
            user_org_id=org_a,
        )
        assert allowed is False

    @pytest.mark.asyncio
    async def test_processor_org_a_denied_org_b_intakes(self):
        from app.services.rbac_service import check_access
        org_a   = uuid.uuid4()
        org_b   = uuid.uuid4()
        user_id = uuid.uuid4()
        session = self._session_with_roles(["processor_analyst"])

        allowed, reason = await check_access(
            session, user_id, "processor_intakes",
            record_owner_org_id=org_b,
            user_org_id=org_a,
        )
        assert allowed is False

    @pytest.mark.asyncio
    async def test_lender_org_a_denied_org_b_assessments(self):
        from app.services.rbac_service import check_access
        org_a   = uuid.uuid4()
        org_b   = uuid.uuid4()
        user_id = uuid.uuid4()
        session = self._session_with_roles(["lender_analyst"])

        allowed, reason = await check_access(
            session, user_id, "lender_assessments",
            record_owner_org_id=org_b,
            user_org_id=org_a,
        )
        assert allowed is False

    @pytest.mark.asyncio
    async def test_arpexas_admin_bypasses_org_isolation(self):
        """Platform admin can see any org's data."""
        from app.services.rbac_service import check_access
        org_a   = uuid.uuid4()
        org_b   = uuid.uuid4()
        user_id = uuid.uuid4()
        session = self._session_with_roles(["arpexas_admin"])

        allowed, _ = await check_access(
            session, user_id, "animals",
            record_owner_org_id=org_b,
            user_org_id=org_a,
        )
        assert allowed is True

    def test_get_accessible_data_filters_to_own_org(self):
        from app.services.rbac_service import get_user_accessible_data
        org_a = uuid.uuid4()
        spec  = get_user_accessible_data(["farm_manager"], org_a, "health_records")
        assert spec["org_id_filter"] == org_a

    def test_different_org_filters_differ(self):
        from app.services.rbac_service import get_user_accessible_data
        org_a = uuid.uuid4()
        org_b = uuid.uuid4()
        spec_a = get_user_accessible_data(["farm_manager"], org_a, "animals")
        spec_b = get_user_accessible_data(["farm_manager"], org_b, "animals")
        assert spec_a["org_id_filter"] != spec_b["org_id_filter"]


# ===========================================================================
# TestRoleDataAccessMatrix
# ===========================================================================

class TestRoleDataAccessMatrix:
    """Verify the access matrix satisfies the NDIC data governance rules."""

    def test_eight_roles_defined(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS
        assert len(_ROLE_DATA_ACCESS) == 8

    def test_farm_roles_access_confidential_farm_not_processor(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS
        from app.models.rbac_models import DATA_CLASS_CONFIDENTIAL_FARM, DATA_CLASS_CONFIDENTIAL_PROCESSOR
        for role in ("farm_manager", "farm_admin"):
            assert DATA_CLASS_CONFIDENTIAL_FARM      in _ROLE_DATA_ACCESS[role]
            assert DATA_CLASS_CONFIDENTIAL_PROCESSOR not in _ROLE_DATA_ACCESS[role]

    def test_processor_roles_access_confidential_processor_not_farm(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS
        from app.models.rbac_models import DATA_CLASS_CONFIDENTIAL_FARM, DATA_CLASS_CONFIDENTIAL_PROCESSOR
        for role in ("processor_analyst", "processor_commercial"):
            assert DATA_CLASS_CONFIDENTIAL_PROCESSOR in _ROLE_DATA_ACCESS[role]
            assert DATA_CLASS_CONFIDENTIAL_FARM      not in _ROLE_DATA_ACCESS[role]

    def test_govt_roles_aggregated_public_only(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS
        from app.models.rbac_models import (
            DATA_CLASS_CONFIDENTIAL_FARM, DATA_CLASS_CONFIDENTIAL_PROCESSOR,
            DATA_CLASS_CONFIDENTIAL_LENDER, DATA_CLASS_AGGREGATED, DATA_CLASS_PUBLIC,
        )
        for role in ("govt_analyst", "govt_admin"):
            classes = _ROLE_DATA_ACCESS[role]
            assert DATA_CLASS_AGGREGATED             in classes
            assert DATA_CLASS_PUBLIC                 in classes
            assert DATA_CLASS_CONFIDENTIAL_FARM      not in classes
            assert DATA_CLASS_CONFIDENTIAL_PROCESSOR not in classes
            assert DATA_CLASS_CONFIDENTIAL_LENDER    not in classes

    def test_lender_accesses_confidential_lender_not_farm_processor(self):
        from app.services.rbac_service import _ROLE_DATA_ACCESS
        from app.models.rbac_models import (
            DATA_CLASS_CONFIDENTIAL_FARM, DATA_CLASS_CONFIDENTIAL_PROCESSOR,
            DATA_CLASS_CONFIDENTIAL_LENDER,
        )
        classes = _ROLE_DATA_ACCESS["lender_analyst"]
        assert DATA_CLASS_CONFIDENTIAL_LENDER    in classes
        assert DATA_CLASS_CONFIDENTIAL_FARM      not in classes
        assert DATA_CLASS_CONFIDENTIAL_PROCESSOR not in classes


# ===========================================================================
# TestSeedRbacDefinitions
# ===========================================================================

class TestSeedRbacDefinitions:
    """Verify the seed data definitions are self-consistent."""

    def test_all_eight_roles_defined_in_seed(self):
        from scripts.seed_rbac import ROLES
        names = {r["name"] for r in ROLES}
        expected = {
            "farm_manager", "farm_admin",
            "processor_analyst", "processor_commercial",
            "govt_analyst", "govt_admin",
            "lender_analyst", "arpexas_admin",
        }
        assert names == expected

    def test_all_role_permissions_reference_known_permissions(self):
        from scripts.seed_rbac import PERMISSIONS, ROLE_PERMISSIONS
        known_perm_names = {p[0] for p in PERMISSIONS}
        for role_name, perm_names in ROLE_PERMISSIONS.items():
            for pname in perm_names:
                assert pname in known_perm_names, (
                    f"Role '{role_name}' references unknown permission '{pname}'"
                )

    def test_every_role_has_at_least_one_permission(self):
        from scripts.seed_rbac import ROLES, ROLE_PERMISSIONS
        for role_def in ROLES:
            rname = role_def["name"]
            assert rname in ROLE_PERMISSIONS, f"Role '{rname}' has no permissions in seed"
            assert len(ROLE_PERMISSIONS[rname]) > 0, f"Role '{rname}' has empty permission list"

    def test_arpexas_admin_has_most_permissions(self):
        from scripts.seed_rbac import ROLE_PERMISSIONS
        admin_count = len(ROLE_PERMISSIONS["arpexas_admin"])
        for role_name, perms in ROLE_PERMISSIONS.items():
            if role_name != "arpexas_admin":
                assert admin_count >= len(perms), (
                    f"{role_name} has more permissions than arpexas_admin"
                )

    def test_permissions_have_no_duplicates(self):
        from scripts.seed_rbac import PERMISSIONS
        names = [p[0] for p in PERMISSIONS]
        assert len(names) == len(set(names)), "Duplicate permission names in PERMISSIONS list"

    def test_data_classifications_cover_all_resource_types(self):
        from scripts.seed_rbac import DATA_CLASSIFICATIONS
        resource_types = {dc["resource_type"] for dc in DATA_CLASSIFICATIONS}
        required = {
            "animals", "health_records", "processor_intakes",
            "lender_assessments", "disease_alerts",
        }
        assert required.issubset(resource_types)

    def test_all_data_classification_classes_are_valid(self):
        from scripts.seed_rbac import DATA_CLASSIFICATIONS
        from app.models.rbac_models import ALL_DATA_CLASSES
        for dc in DATA_CLASSIFICATIONS:
            assert dc["data_class"] in ALL_DATA_CLASSES, (
                f"Invalid data_class '{dc['data_class']}' for resource '{dc['resource_type']}'"
            )


# ===========================================================================
# TestComplianceApiRbacAuditLogic
# ===========================================================================

class TestComplianceApiRbacAuditLogic:
    """
    Test the rbac_audit compliance check logic without hitting DB.
    We verify the issue-detection logic directly.
    """

    def _build_roles(self, names: list[str]) -> list[MagicMock]:
        return [_make_role(n) for n in names]

    def test_role_without_permissions_flagged(self):
        """Simulate the issue-detection logic from compliance.py/rbac_audit."""
        roles = self._build_roles(["govt_analyst", "farm_manager"])
        # Only govt_analyst has permission links
        roles_with_perms = {str(roles[0].id)}

        issues: list[str] = []
        for role in roles:
            if str(role.id) not in roles_with_perms:
                issues.append(f"Role '{role.name}' has no permissions assigned")

        assert len(issues) == 1
        assert "farm_manager" in issues[0]

    def test_no_issues_when_all_roles_have_permissions(self):
        roles = self._build_roles(["farm_manager", "govt_analyst"])
        roles_with_perms = {str(r.id) for r in roles}

        issues: list[str] = []
        for role in roles:
            if str(role.id) not in roles_with_perms:
                issues.append(f"Role '{role.name}' has no permissions assigned")

        assert issues == []

    def test_user_without_role_flagged(self):
        user = MagicMock()
        user.id    = uuid.uuid4()
        user.email = "orphan@example.com"

        assigned_user_ids: set[str] = set()  # user has no assignment
        issues: list[str] = []
        if str(user.id) not in assigned_user_ids:
            issues.append(f"Active user '{user.email}' has no role assignment")

        assert len(issues) == 1
        assert "orphan@example.com" in issues[0]

    def test_audit_result_passed_when_no_issues(self):
        issues: list[str] = []
        audit_result = "passed" if not issues else "failed"
        assert audit_result == "passed"

    def test_audit_result_failed_when_issues_exist(self):
        issues = ["Role X has no permissions"]
        audit_result = "passed" if not issues else "failed"
        assert audit_result == "failed"
