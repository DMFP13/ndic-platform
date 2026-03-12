"""
Domain-level validators for NDIC data submissions.

These run AFTER Pydantic structural validation and enforce business rules:
  - value ranges (temperature, yield)
  - enumeration membership (breed, sex, behavior)
  - temporal constraints (no future dates)

All functions return a list[str] of error messages.
An empty list means the record is valid.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Behavior constants
# Behavior labels → DB integer score (behavior_score column, range 1-5)
# ---------------------------------------------------------------------------

BEHAVIOR_LABELS: frozenset[str] = frozenset({
    "normal",
    "depressed",
    "aggressive",
    "slightly_lethargic",
    "lethargic",
    "distressed",
    "critical",
})

BEHAVIOR_SCORE_MAP: dict[str, int] = {
    "normal":             1,
    "depressed":          2,
    "aggressive":         2,
    "slightly_lethargic": 2,
    "lethargic":          3,
    "distressed":         4,
    "critical":           5,
}

BEHAVIOR_LABEL_MAP: dict[int, str] = {
    1: "normal",
    2: "depressed",
    3: "lethargic",
    4: "distressed",
    5: "critical",
}

# Valid breed and sex values (mirrors AnimalBreed / AnimalSex enums)
VALID_BREEDS: frozenset[str] = frozenset({
    "bunaji", "rahaji", "azawak", "shuwa_arab", "muturu", "keteku",
    "friesian", "jersey", "brown_swiss", "friesian_bunaji_cross",
    "crossbreed", "other",
})

VALID_SEXES: frozenset[str] = frozenset({"male", "female"})


# ---------------------------------------------------------------------------
# Health record validator
# ---------------------------------------------------------------------------

def validate_health_record(record: dict[str, Any]) -> list[str]:
    """
    Validate a single animal health observation.

    Accepts both API field names (temperature_c) and DB field names
    (temperature_celsius) so the same function works at both layers.

    Args:
        record: dict with any subset of:
                  temperature_c / temperature_celsius, milk_yield_liters,
                  behavior, record_date / submission_date

    Returns:
        List of error message strings; empty list = valid.
    """
    errors: list[str] = []

    # ── Temperature ──────────────────────────────────────────────────────────
    temp = record.get("temperature_c") if "temperature_c" in record else record.get("temperature_celsius")
    if temp is not None:
        if not isinstance(temp, (int, float)):
            errors.append("temperature must be numeric")
        elif not (35.0 <= float(temp) <= 42.0):
            errors.append(
                f"temperature {temp}°C is outside valid range (35–42°C); "
                "normal bovine range is 38.0–39.5°C"
            )

    # ── Milk yield ───────────────────────────────────────────────────────────
    yield_val = record.get("milk_yield_liters")
    if yield_val is not None:
        if not isinstance(yield_val, (int, float)):
            errors.append("milk_yield_liters must be numeric")
        elif not (0.0 <= float(yield_val) <= 50.0):
            errors.append(
                f"milk_yield_liters {yield_val} is outside valid range (0–50 L)"
            )

    # ── Behavior ─────────────────────────────────────────────────────────────
    behavior = record.get("behavior")
    if behavior is not None:
        if behavior.lower() not in BEHAVIOR_LABELS:
            errors.append(
                f"behavior '{behavior}' is not valid. "
                f"Accepted: {sorted(BEHAVIOR_LABELS)}"
            )

    # ── Record date not in future ────────────────────────────────────────────
    ts_raw = record.get("record_date") or record.get("submission_date")
    if ts_raw is not None:
        ts = _parse_datetime(ts_raw)
        if ts is None:
            errors.append("record_date must be a valid ISO-8601 datetime string")
        elif ts > datetime.now(timezone.utc):
            errors.append("record_date cannot be in the future")

    return errors


# ---------------------------------------------------------------------------
# Farm registration validator
# ---------------------------------------------------------------------------

def validate_farm_registration(farm: dict[str, Any]) -> list[str]:
    """
    Validate a farm registration payload.

    Args:
        farm: dict with keys: organization_name, state, [lga, herd_size, contact_email]

    Returns:
        List of error messages; empty = valid.
    """
    errors: list[str] = []

    if not str(farm.get("organization_name", "")).strip():
        errors.append("organization_name is required and cannot be blank")

    if not str(farm.get("state", "")).strip():
        errors.append("state is required")

    herd_size = farm.get("herd_size")
    if herd_size is not None:
        if not isinstance(herd_size, int) or herd_size < 0:
            errors.append("herd_size must be a non-negative integer")

    email = str(farm.get("contact_email", "") or "")
    if email and "@" not in email:
        errors.append("contact_email is not a valid email address")

    admin_email = str(farm.get("admin_email", "") or "")
    if admin_email and "@" not in admin_email:
        errors.append("admin_email is not a valid email address")

    password = str(farm.get("admin_password", "") or "")
    if password and len(password) < 12:
        errors.append("admin_password must be at least 12 characters")

    return errors


# ---------------------------------------------------------------------------
# Animal creation validator
# ---------------------------------------------------------------------------

def validate_animal_creation(animal: dict[str, Any]) -> list[str]:
    """
    Validate an animal registration payload.

    Accepts both API aliases (identification_number, gender, dob) and
    canonical field names (tag_number, sex, date_of_birth).

    Returns:
        List of error messages; empty = valid.
    """
    errors: list[str] = []

    # tag_number / identification_number
    tag = str(
        animal.get("tag_number") or animal.get("identification_number") or ""
    ).strip()
    if not tag:
        errors.append("tag_number (identification_number) is required")

    # breed
    breed = str(animal.get("breed", "") or "").lower().strip()
    if breed and breed not in VALID_BREEDS:
        errors.append(
            f"breed '{breed}' is not recognised. "
            f"Valid breeds: {sorted(VALID_BREEDS)}"
        )

    # sex / gender
    sex = str(animal.get("sex") or animal.get("gender", "") or "").lower().strip()
    if sex and sex not in VALID_SEXES:
        errors.append(f"sex/gender must be one of {sorted(VALID_SEXES)}")

    # date_of_birth / dob
    dob_raw = animal.get("date_of_birth") or animal.get("dob")
    if dob_raw is not None:
        dob = _parse_datetime(dob_raw)
        if dob is None:
            errors.append("date_of_birth must be a valid ISO-8601 date or datetime")
        elif dob > datetime.now(timezone.utc):
            errors.append("date_of_birth cannot be in the future")

    # weight_kg
    weight = animal.get("weight_kg")
    if weight is not None:
        if not isinstance(weight, (int, float)) or float(weight) <= 0:
            errors.append("weight_kg must be a positive number")

    return errors


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_datetime(value: Any) -> datetime | None:
    """Coerce a string or datetime to UTC-aware datetime; return None on failure."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            return None
    return None
