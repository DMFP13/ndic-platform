"""
Phase 3 test suite — Farm Data Submission API.

Test strategy:
  - Validators and pure analysis functions: no mocking (fast, deterministic)
  - Service functions: mocked AsyncSession (no DB required)
  - Cross-farm isolation: verified at service layer

Run:
    pip install pytest pytest-asyncio
    pytest tests/test_farm_submissions.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Pure function imports (no DB needed)
# ---------------------------------------------------------------------------
from app.utils.validators import (
    BEHAVIOR_SCORE_MAP,
    validate_animal_creation,
    validate_farm_registration,
    validate_health_record,
)
from app.services.farm_service import (
    AnimalNotOwnedError,
    FarmNotFoundError,
    calculate_health_status,
    generate_risk_flags,
    _compute_metrics,
    _hr_to_dict,
    _max_consecutive,
    _try_parse_uuid,
)
from app.security import generate_keypair, sign_data


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(scope="module")
def keypair():
    return generate_keypair(key_size=2048)


def make_record(
    temp: float | None = 38.5,
    behavior: int | None = 1,
    yield_l: float | None = 12.0,
    days_ago: int = 0,
    treatments: list | None = None,
) -> dict:
    """Build a synthetic health-record dict."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "animal_id": str(uuid.uuid4()),
        "farm_id": str(uuid.uuid4()),
        "record_date": ts,
        "temperature_celsius": temp,
        "behavior_score": behavior,
        "milk_yield_liters": yield_l,
        "body_condition_score": None,
        "treatments": treatments,
        "vaccinations": None,
        "notes": None,
        "created_at": ts,
    }


# ===========================================================================
# Validator tests
# ===========================================================================

class TestValidateHealthRecord:
    def test_valid_record_returns_no_errors(self):
        rec = {
            "temperature_c": 38.5,
            "milk_yield_liters": 12.0,
            "behavior": "normal",
            "record_date": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        assert validate_health_record(rec) == []

    def test_temperature_below_range(self):
        errors = validate_health_record({"temperature_c": 34.0})
        assert any("temperature" in e for e in errors)

    def test_temperature_above_range(self):
        errors = validate_health_record({"temperature_c": 43.0})
        assert any("temperature" in e for e in errors)

    def test_temperature_accepts_db_field_name(self):
        errors = validate_health_record({"temperature_celsius": 38.0})
        assert errors == []

    def test_negative_milk_yield(self):
        errors = validate_health_record({"milk_yield_liters": -1.0})
        assert any("milk_yield" in e for e in errors)

    def test_milk_yield_above_50(self):
        errors = validate_health_record({"milk_yield_liters": 51.0})
        assert any("milk_yield" in e for e in errors)

    def test_milk_yield_exactly_50_is_valid(self):
        assert validate_health_record({"milk_yield_liters": 50.0}) == []

    def test_invalid_behavior_label(self):
        errors = validate_health_record({"behavior": "hyperactive"})
        assert any("behavior" in e for e in errors)

    def test_valid_behavior_labels_pass(self):
        for label in ["normal", "depressed", "lethargic", "distressed"]:
            assert validate_health_record({"behavior": label}) == [], f"Label '{label}' should be valid"

    def test_future_date_fails(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        errors = validate_health_record({"record_date": future})
        assert any("future" in e for e in errors)

    def test_past_date_passes(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        assert validate_health_record({"record_date": past}) == []

    def test_empty_record_is_valid(self):
        """All fields are optional; an empty record is valid structurally."""
        assert validate_health_record({}) == []


class TestValidateFarmRegistration:
    def test_valid_payload_passes(self):
        assert validate_farm_registration({
            "organization_name": "Danone Farm",
            "state": "Kaduna",
            "admin_email": "admin@farm.ng",
            "admin_password": "Securepass123!",
        }) == []

    def test_missing_organization_name(self):
        errors = validate_farm_registration({"state": "Kano"})
        assert any("organization_name" in e for e in errors)

    def test_missing_state(self):
        errors = validate_farm_registration({"organization_name": "X"})
        assert any("state" in e for e in errors)

    def test_negative_herd_size(self):
        errors = validate_farm_registration({
            "organization_name": "X", "state": "Lagos", "herd_size": -1
        })
        assert any("herd_size" in e for e in errors)

    def test_invalid_email_format(self):
        errors = validate_farm_registration({
            "organization_name": "X", "state": "Lagos",
            "contact_email": "notanemail",
        })
        assert any("email" in e for e in errors)

    def test_short_password(self):
        errors = validate_farm_registration({
            "organization_name": "X", "state": "Lagos",
            "admin_email": "a@b.com", "admin_password": "short",
        })
        assert any("password" in e for e in errors)


class TestValidateAnimalCreation:
    def test_valid_payload_passes(self):
        assert validate_animal_creation({
            "tag_number": "COW-001",
            "breed": "bunaji",
            "sex": "female",
            "date_of_birth": "2022-01-15T00:00:00+00:00",
        }) == []

    def test_accepts_identification_number_alias(self):
        assert validate_animal_creation({"identification_number": "TAG-42", "sex": "male"}) == []

    def test_missing_tag_number(self):
        errors = validate_animal_creation({"breed": "bunaji"})
        assert any("tag_number" in e for e in errors)

    def test_invalid_breed(self):
        errors = validate_animal_creation({"tag_number": "X", "breed": "unicorn"})
        assert any("breed" in e for e in errors)

    def test_invalid_sex(self):
        errors = validate_animal_creation({"tag_number": "X", "sex": "unknown"})
        assert any("sex" in e for e in errors)

    def test_accepts_gender_alias(self):
        assert validate_animal_creation({"tag_number": "X", "gender": "female"}) == []

    def test_future_dob_fails(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        errors = validate_animal_creation({"tag_number": "X", "date_of_birth": future})
        assert any("future" in e for e in errors)

    def test_zero_weight_fails(self):
        errors = validate_animal_creation({"tag_number": "X", "weight_kg": 0})
        assert any("weight" in e for e in errors)


# ===========================================================================
# Behavior score mapping
# ===========================================================================

class TestBehaviorScoreMap:
    def test_normal_maps_to_1(self):
        assert BEHAVIOR_SCORE_MAP["normal"] == 1

    def test_lethargic_maps_to_3(self):
        assert BEHAVIOR_SCORE_MAP["lethargic"] == 3

    def test_distressed_maps_to_4(self):
        assert BEHAVIOR_SCORE_MAP["distressed"] == 4

    def test_critical_maps_to_5(self):
        assert BEHAVIOR_SCORE_MAP["critical"] == 5


# ===========================================================================
# Health status calculation
# ===========================================================================

class TestCalculateHealthStatus:
    def test_healthy_normal_records(self):
        records = [make_record(temp=38.5, behavior=1, yield_l=12.0, days_ago=i) for i in range(5)]
        assert calculate_health_status(records) == "healthy"

    def test_alert_on_consecutive_fever(self):
        """Two records above 39.5°C in the window → alert."""
        records = [
            make_record(temp=39.8, behavior=2, yield_l=8.0, days_ago=2),
            make_record(temp=40.1, behavior=3, yield_l=7.0, days_ago=1),
            make_record(temp=38.0, behavior=1, yield_l=12.0, days_ago=5),
        ]
        assert calculate_health_status(records) == "alert"

    def test_alert_on_yield_drop_over_40pct(self):
        # First 4 records: 14L, last 4: 8L → ~43% drop
        records = [make_record(temp=38.5, yield_l=14.0, days_ago=7 - i) for i in range(4)]
        records += [make_record(temp=38.5, yield_l=8.0,  days_ago=3 - i) for i in range(4)]
        assert calculate_health_status(records) == "alert"

    def test_alert_on_lethargic_3_plus_observations(self):
        records = [make_record(behavior=3, days_ago=i) for i in range(4)]  # all lethargic
        assert calculate_health_status(records) == "alert"

    def test_at_risk_on_high_avg_temp(self):
        records = [make_record(temp=39.2, days_ago=i) for i in range(4)]  # above 39 but < 39.5
        assert calculate_health_status(records) == "at_risk"

    def test_at_risk_on_yield_drop_over_20pct(self):
        records = [make_record(yield_l=12.0, days_ago=6 - i) for i in range(4)]
        records += [make_record(yield_l=9.0,  days_ago=2 - i) for i in range(4)]
        assert calculate_health_status(records) == "at_risk"

    def test_at_risk_on_depressed_2_plus_observations(self):
        records = [make_record(behavior=2, days_ago=i) for i in range(3)]  # all depressed
        assert calculate_health_status(records) in ("at_risk", "alert")

    def test_unknown_when_empty(self):
        assert calculate_health_status([]) == "unknown"

    def test_uses_window_correctly(self):
        """Records older than window_days should not affect status."""
        old_fever = [make_record(temp=40.5, days_ago=20) for _ in range(3)]  # outside 7-day window
        recent_ok  = [make_record(temp=38.5, days_ago=i) for i in range(3)]
        # With window_days=7, old fever records are excluded
        status = calculate_health_status(old_fever + recent_ok, window_days=7)
        assert status == "healthy"


# ===========================================================================
# Risk flag generation
# ===========================================================================

class TestGenerateRiskFlags:
    def setup_method(self):
        self.animal_id = uuid.uuid4()
        self.tag = "COW-007"

    def _flags_of_type(self, flags: list, flag_type: str) -> list:
        return [f for f in flags if f["flag_type"] == flag_type]

    def test_no_flags_for_healthy_animal(self):
        records = [make_record(temp=38.5, behavior=1, yield_l=12.0, days_ago=i) for i in range(5)]
        flags = generate_risk_flags(self.animal_id, self.tag, records)
        assert flags == []

    def test_fever_alert_raised_for_two_consecutive_high_temps(self):
        records = [
            make_record(temp=38.0, days_ago=4),
            make_record(temp=39.8, days_ago=3),
            make_record(temp=40.2, days_ago=2),   # ← 2 consecutive fever
            make_record(temp=38.5, days_ago=1),
        ]
        flags = generate_risk_flags(self.animal_id, self.tag, records)
        fever_flags = self._flags_of_type(flags, "fever_alert")
        assert len(fever_flags) == 1
        assert fever_flags[0]["severity"] == "high"

    def test_no_fever_alert_for_single_high_temp(self):
        """One fever observation is not enough for a fever_alert."""
        records = [make_record(temp=38.0, days_ago=2), make_record(temp=40.1, days_ago=1)]
        flags = generate_risk_flags(self.animal_id, self.tag, records)
        assert not self._flags_of_type(flags, "fever_alert")

    def test_production_decline_raised_above_30pct(self):
        # Baseline ~14L, current ~9L → ~35% drop
        records = [make_record(yield_l=14.0, days_ago=6 - i) for i in range(4)]
        records += [make_record(yield_l=9.0,  days_ago=2 - i) for i in range(4)]
        flags = generate_risk_flags(self.animal_id, self.tag, records)
        assert self._flags_of_type(flags, "production_decline")

    def test_no_production_decline_for_stable_yield(self):
        records = [make_record(yield_l=12.0, days_ago=i) for i in range(8)]
        flags = generate_risk_flags(self.animal_id, self.tag, records)
        assert not self._flags_of_type(flags, "production_decline")

    def test_behavioral_change_raised_for_3_lethargic(self):
        records = [make_record(behavior=3, days_ago=i) for i in range(4)]  # all lethargic
        flags = generate_risk_flags(self.animal_id, self.tag, records)
        assert self._flags_of_type(flags, "behavioral_change")

    def test_treatment_needed_when_fever_and_no_recent_treatment(self):
        records = [
            make_record(temp=40.0, behavior=4, days_ago=2, treatments=None),
            make_record(temp=40.3, behavior=4, days_ago=1, treatments=None),
        ]
        flags = generate_risk_flags(self.animal_id, self.tag, records)
        assert self._flags_of_type(flags, "treatment_needed")

    def test_no_treatment_needed_when_treatment_recorded(self):
        records = [
            make_record(temp=40.0, behavior=4, days_ago=2, treatments=["antibiotic"]),
            make_record(temp=40.3, behavior=4, days_ago=1, treatments=["antibiotic"]),
        ]
        flags = generate_risk_flags(self.animal_id, self.tag, records)
        assert not self._flags_of_type(flags, "treatment_needed")

    def test_empty_records_returns_empty_flags(self):
        assert generate_risk_flags(self.animal_id, self.tag, []) == []

    def test_flag_contains_required_keys(self):
        records = [make_record(temp=40.0, days_ago=1), make_record(temp=40.5, days_ago=0)]
        flags = generate_risk_flags(self.animal_id, self.tag, records)
        for flag in flags:
            assert "flag_type" in flag
            assert "animal_id" in flag
            assert "tag_number" in flag
            assert "message" in flag
            assert "severity" in flag


# ===========================================================================
# Metrics computation
# ===========================================================================

class TestComputeMetrics:
    def test_avg_temperature(self):
        records = [make_record(temp=38.0), make_record(temp=39.0), make_record(temp=38.5)]
        m = _compute_metrics(records)
        assert m["avg_temp"] == pytest.approx(38.5, abs=0.1)

    def test_avg_yield(self):
        records = [make_record(yield_l=10.0), make_record(yield_l=12.0), make_record(yield_l=14.0)]
        m = _compute_metrics(records)
        assert m["avg_yield"] == pytest.approx(12.0, abs=0.1)

    def test_yield_trend_positive(self):
        # First half: 8L, second half: 12L → positive trend
        records = [make_record(yield_l=8.0) for _ in range(4)]
        records += [make_record(yield_l=12.0) for _ in range(4)]
        m = _compute_metrics(records)
        assert m["yield_trend_pct"] > 0

    def test_yield_trend_negative(self):
        # First half: 14L, second half: 9L → negative trend
        records = [make_record(yield_l=14.0) for _ in range(4)]
        records += [make_record(yield_l=9.0) for _ in range(4)]
        m = _compute_metrics(records)
        assert m["yield_trend_pct"] < 0

    def test_empty_records_returns_empty_dict(self):
        assert _compute_metrics([]) == {}

    def test_none_values_are_ignored(self):
        records = [
            make_record(temp=None, yield_l=10.0),
            make_record(temp=39.0, yield_l=None),
        ]
        m = _compute_metrics(records)
        # avg_temp uses only the one non-None value
        assert "avg_temp" in m
        assert m["avg_temp"] == pytest.approx(39.0)


# ===========================================================================
# Helper utilities
# ===========================================================================

class TestHelpers:
    def test_try_parse_uuid_valid(self):
        uid = uuid.uuid4()
        assert _try_parse_uuid(str(uid)) == uid

    def test_try_parse_uuid_invalid(self):
        assert _try_parse_uuid("COW-001") is None
        assert _try_parse_uuid("") is None

    def test_max_consecutive_above(self):
        values = [38.0, 40.0, 40.1, 40.3, 38.5, 39.8]
        assert _max_consecutive(values, threshold=39.5, above=True) == 3

    def test_max_consecutive_no_run(self):
        values = [38.0, 38.5, 39.0]
        assert _max_consecutive(values, threshold=39.5, above=True) == 0

    def test_max_consecutive_all_above(self):
        values = [40.0, 40.1, 40.2]
        assert _max_consecutive(values, threshold=39.5, above=True) == 3


# ===========================================================================
# Service layer — mocked DB session
# ===========================================================================

class TestSubmitHealthRecords:
    """Test farm_service.submit_health_records with mocked AsyncSession."""

    @pytest.fixture
    def farm_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def user_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def org_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def mock_farm(self, farm_id, org_id):
        farm = MagicMock()
        farm.id = farm_id
        farm.organization_id = org_id
        return farm

    @pytest.fixture
    def mock_animal(self, farm_id):
        animal = MagicMock()
        animal.id = uuid.uuid4()
        animal.farm_id = farm_id
        animal.tag_number = "COW-001"
        return animal

    def _make_session(self, farm, animal):
        session = AsyncMock()
        session.add = MagicMock()

        call_count = [0]

        async def execute_side_effect(stmt):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # _get_farm lookup
                result.scalar_one_or_none.return_value = farm
            elif call_count[0] == 2:
                # ledger previous_hash lookup
                result.scalar_one_or_none.return_value = None
            elif call_count[0] == 3:
                # _get_animal_for_farm lookup
                result.scalar_one_or_none.return_value = animal
            else:
                result.scalar_one_or_none.return_value = None
            return result

        session.execute = execute_side_effect
        return session

    @pytest.mark.asyncio
    async def test_valid_submission_returns_processed_count(self, keypair, farm_id, user_id, mock_farm, mock_animal):
        from app.services.farm_service import submit_health_records

        pub_pem, priv_pem = keypair
        animal_id = mock_animal.id

        data = {
            "submission_date": datetime.now(timezone.utc).isoformat(),
            "animals": [{"animal_id": str(animal_id), "temperature_c": 38.5, "milk_yield_liters": 12.0, "behavior": "normal"}],
        }
        sig = sign_data(data, priv_pem)
        session = self._make_session(mock_farm, mock_animal)

        result = await submit_health_records(
            session=session,
            farm_id=farm_id,
            submission_date=datetime.now(timezone.utc),
            animal_records=[{"animal_id": str(animal_id), "temperature_c": 38.5, "milk_yield_liters": 12.0, "behavior": "normal"}],
            data_dict=data,
            signature_b64=sig,
            actor_user_id=user_id,
            public_key_pem=pub_pem,
        )

        assert result["processed_count"] == 1
        assert result["failed_records"] == []
        assert result["verification_status"] == "valid"
        assert result["ledger_entry_id"] is not None
        session.add.assert_called()  # HealthRecord + LedgerLog both added

    @pytest.mark.asyncio
    async def test_bad_signature_raises(self, keypair, farm_id, user_id, mock_farm, mock_animal):
        from app.services.farm_service import submit_health_records
        from app.security import SignatureVerificationError

        pub_pem, _ = keypair
        data = {"submission_date": datetime.now(timezone.utc).isoformat(), "animals": []}
        session = self._make_session(mock_farm, mock_animal)

        with pytest.raises(SignatureVerificationError):
            await submit_health_records(
                session=session,
                farm_id=farm_id,
                submission_date=datetime.now(timezone.utc),
                animal_records=[],
                data_dict=data,
                signature_b64="invalidsignature",
                actor_user_id=user_id,
                public_key_pem=pub_pem,
            )

    @pytest.mark.asyncio
    async def test_farm_not_found_raises(self, keypair, user_id):
        from app.services.farm_service import submit_health_records

        pub_pem, priv_pem = keypair
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        data = {"submission_date": datetime.now(timezone.utc).isoformat(), "animals": []}
        sig = sign_data(data, priv_pem)

        with pytest.raises(FarmNotFoundError):
            await submit_health_records(
                session=session,
                farm_id=uuid.uuid4(),
                submission_date=datetime.now(timezone.utc),
                animal_records=[],
                data_dict=data,
                signature_b64=sig,
                actor_user_id=user_id,
                public_key_pem=pub_pem,
            )

    @pytest.mark.asyncio
    async def test_missing_public_key_raises(self, farm_id, user_id):
        from app.services.farm_service import submit_health_records

        session = AsyncMock()
        data = {"submission_date": datetime.now(timezone.utc).isoformat(), "animals": []}

        with pytest.raises(ValueError, match="no registered public key"):
            await submit_health_records(
                session=session,
                farm_id=farm_id,
                submission_date=datetime.now(timezone.utc),
                animal_records=[],
                data_dict=data,
                signature_b64="sig",
                actor_user_id=user_id,
                public_key_pem="",   # empty → should raise
            )


class TestGetAnimalProfile:
    """Test farm_service.get_animal_profile with mocked session."""

    @pytest.fixture
    def mock_animal(self):
        a = MagicMock()
        a.id = uuid.uuid4()
        a.farm_id = uuid.uuid4()
        a.tag_number = "COW-001"
        a.breed = "bunaji"
        a.sex = "female"
        a.date_of_birth = datetime.now(timezone.utc) - timedelta(days=365 * 2)
        a.weight_kg = 350.0
        a.status = "active"
        a.acquired_at = datetime.now(timezone.utc) - timedelta(days=180)
        return a

    def _make_hr_orm(self, animal_id, farm_id, temp, behavior, yield_l, days_ago=0):
        r = MagicMock()
        r.id = uuid.uuid4()
        r.animal_id = animal_id
        r.farm_id = farm_id
        r.record_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        r.temperature_celsius = temp
        r.behavior_score = behavior
        r.milk_yield_liters = yield_l
        r.body_condition_score = None
        r.treatments = None
        r.vaccinations = None
        r.notes = None
        r.created_at = r.record_date
        return r

    @pytest.mark.asyncio
    async def test_profile_returns_expected_keys(self, mock_animal):
        from app.services.farm_service import get_animal_profile

        session = AsyncMock()
        call_count = [0]

        async def execute_side_effect(stmt):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = mock_animal
            else:
                hrs = [self._make_hr_orm(mock_animal.id, mock_animal.farm_id, 38.5, 1, 12.0, i) for i in range(5)]
                result.scalars.return_value.all.return_value = hrs
            return result

        session.execute = execute_side_effect

        profile = await get_animal_profile(
            session=session,
            animal_id=mock_animal.id,
            farm_id=mock_animal.farm_id,
        )

        for key in ["id", "tag_number", "breed", "current_health_status", "health_history", "risk_flags", "record_count"]:
            assert key in profile, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_profile_raises_for_wrong_farm(self, mock_animal):
        from app.services.farm_service import get_animal_profile

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None   # animal not in this farm
        session.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(AnimalNotOwnedError):
            await get_animal_profile(
                session=session,
                animal_id=mock_animal.id,
                farm_id=uuid.uuid4(),   # wrong farm
            )

    @pytest.mark.asyncio
    async def test_age_days_calculated_correctly(self, mock_animal):
        from app.services.farm_service import get_animal_profile

        session = AsyncMock()
        call_count = [0]

        async def execute_side_effect(stmt):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = mock_animal
            else:
                result.scalars.return_value.all.return_value = []
            return result

        session.execute = execute_side_effect
        profile = await get_animal_profile(session=session, animal_id=mock_animal.id, farm_id=mock_animal.farm_id)

        # Animal DOB is 2 years ago
        assert profile["age_days"] is not None
        assert 700 <= profile["age_days"] <= 740


# ===========================================================================
# Cross-farm isolation
# ===========================================================================

class TestCrossFarmIsolation:
    """
    Verify that Farm A's animals cannot be accessed via Farm B's endpoints.
    """

    @pytest.mark.asyncio
    async def test_animal_from_farm_a_not_accessible_via_farm_b(self):
        from app.services.farm_service import get_animal_profile

        farm_a_id = uuid.uuid4()
        farm_b_id = uuid.uuid4()
        animal_in_farm_a = MagicMock()
        animal_in_farm_a.id = uuid.uuid4()
        animal_in_farm_a.farm_id = farm_a_id

        session = AsyncMock()
        result_mock = MagicMock()
        # Query for (animal_id, farm_b_id) returns None — isolation enforced
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(AnimalNotOwnedError):
            await get_animal_profile(
                session=session,
                animal_id=animal_in_farm_a.id,
                farm_id=farm_b_id,   # wrong farm
            )

    @pytest.mark.asyncio
    async def test_health_records_scoped_to_farm(self, keypair):
        """
        submit_health_records for farm_b with an animal owned by farm_a
        → animal not found in farm_b → goes to failed_records, not processed.
        """
        from app.services.farm_service import submit_health_records

        pub_pem, priv_pem = keypair
        farm_a_id = uuid.uuid4()
        farm_b_id = uuid.uuid4()
        org_b_id = uuid.uuid4()
        user_id = uuid.uuid4()
        animal_farm_a_id = uuid.uuid4()

        farm_b = MagicMock()
        farm_b.id = farm_b_id
        farm_b.organization_id = org_b_id

        session = AsyncMock()
        call_count = [0]

        async def execute_side_effect(stmt):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = farm_b   # farm lookup OK
            elif call_count[0] == 2:
                result.scalar_one_or_none.return_value = None      # ledger previous_hash
            else:
                result.scalar_one_or_none.return_value = None      # animal not in farm_b
            return result

        session.execute = execute_side_effect
        session.add = MagicMock()

        data = {
            "submission_date": datetime.now(timezone.utc).isoformat(),
            "animals": [{"animal_id": str(animal_farm_a_id), "temperature_c": 38.5}],
        }
        sig = sign_data(data, priv_pem)

        result = await submit_health_records(
            session=session,
            farm_id=farm_b_id,
            submission_date=datetime.now(timezone.utc),
            animal_records=[{"animal_id": str(animal_farm_a_id), "temperature_c": 38.5}],
            data_dict=data,
            signature_b64=sig,
            actor_user_id=user_id,
            public_key_pem=pub_pem,
        )

        # The animal from Farm A is not processed — it ends up in failed_records
        assert result["processed_count"] == 0
        assert len(result["failed_records"]) == 1
        assert "not found" in result["failed_records"][0]["error"]
