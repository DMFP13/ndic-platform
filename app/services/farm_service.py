"""
NDIC Farm Service — Phase 3
────────────────────────────
Business logic for farm data submissions, animal profile aggregation,
and farm dashboard metrics.

All DB-touching functions are async. Pure analysis functions
(calculate_health_status, generate_risk_flags) are sync so they
can be tested without a DB and called from background workers.

Health-status rules (per spec):
  healthy  → avg_temp 37.5–39°C  AND  stable yield  AND  normal behaviour
  at_risk  → avg_temp > 39°C  OR  yield drop > 20%  OR  depressed 2+ obs
  alert    → temp > 39.5°C for 2+ obs  OR  yield drop > 40%  OR  lethargic 3+ obs

Risk flags generated:
  fever_alert        — temp > 39.5°C for ≥2 consecutive observations
  production_decline — yield drop > 30% from window baseline
  behavioral_change  — lethargic/distressed score ≥3 for ≥3 observations
  estrus_window      — temp dip + behavior change heuristic
  treatment_needed   — alert-level symptoms, no recent treatment recorded
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ledger_service import record_submission
from app.utils.validators import BEHAVIOR_LABEL_MAP, BEHAVIOR_SCORE_MAP, validate_health_record
from models.database import Animal, Farm, HealthRecord, Organization
from models.enums import AnimalBreed, AnimalSex, AnimalStatus, LedgerEventType

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class FarmNotFoundError(ValueError):
    """farm_id does not exist in the database."""


class AnimalNotOwnedError(PermissionError):
    """animal_id exists but does not belong to the requested farm."""


class HealthRecordValidationError(ValueError):
    """One or more fields in a health record submission are invalid."""


# ---------------------------------------------------------------------------
# Health record batch submission
# ---------------------------------------------------------------------------

async def submit_health_records(
    *,
    session: AsyncSession,
    farm_id: uuid.UUID,
    submission_date: datetime,
    animal_records: list[dict[str, Any]],
    data_dict: dict[str, Any],          # canonical payload that was signed
    signature_b64: str,
    actor_user_id: uuid.UUID,
    public_key_pem: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """
    Verify the batch signature, insert HealthRecord rows, append one ledger entry.

    The ledger entry covers the whole batch (one signature per submission).
    Each inserted HealthRecord stores that batch signature in its signature column
    so the chain of custody is traceable per-record.

    Returns::

        {
          "processed_count": int,
          "failed_records": [{"animal_id": str, "error": str}],
          "ledger_entry_id": UUID,
          "verification_status": "valid",
        }

    Raises:
        FarmNotFoundError:           farm_id not found.
        SignatureVerificationError:  signature does not match farm's public key
                                     (propagated from ledger_service).
    """
    # Fail fast — no DB calls if the actor hasn't registered a public key
    if not public_key_pem:
        raise ValueError(
            f"Actor {actor_user_id} has no registered public key. "
            "Register a public key via POST /auth/register-public-key before submitting records."
        )

    farm = await _get_farm(session, farm_id)

    # Generate a stable batch_id so the ledger entry has a meaningful target_record_id
    batch_id = uuid.uuid4()

    # One ledger entry for the whole submission — verifies signature internally
    ledger_entry = await record_submission(
        session=session,
        actor_user_id=actor_user_id,
        actor_org_id=farm.organization_id,
        event_type=LedgerEventType.HEALTH_RECORD_SUBMITTED,
        target_table="health_records",
        target_record_id=batch_id,
        record_dict=data_dict,
        signature_b64=signature_b64,
        public_key_pem=public_key_pem,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    processed = 0
    failed: list[dict[str, Any]] = []

    for rec in animal_records:
        animal_id_raw = str(rec.get("animal_id", ""))

        # Resolve: try UUID first, then fall back to tag_number lookup
        animal_id = _try_parse_uuid(animal_id_raw)
        if animal_id is None:
            animal_id = await _resolve_animal_by_tag(session, farm_id, animal_id_raw)
        if animal_id is None:
            failed.append({
                "animal_id": animal_id_raw,
                "error": f"Animal '{animal_id_raw}' not found in farm {farm_id}",
            })
            continue

        # Ownership check
        animal = await _get_animal_for_farm(session, animal_id, farm_id)
        if animal is None:
            failed.append({
                "animal_id": str(animal_id),
                "error": "Animal not found or does not belong to this farm",
            })
            continue

        # Domain validation
        errors = validate_health_record(rec)
        if errors:
            failed.append({"animal_id": str(animal_id), "error": "; ".join(errors)})
            continue

        # Map behavior label → integer score
        behavior_score: int | None = None
        behavior_label = (rec.get("behavior") or "").lower().strip()
        if behavior_label:
            behavior_score = BEHAVIOR_SCORE_MAP.get(behavior_label)

        temp_val = rec.get("temperature_c") if "temperature_c" in rec else rec.get("temperature_celsius")

        hr = HealthRecord(
            id=uuid.uuid4(),
            animal_id=animal_id,
            farm_id=farm_id,
            record_date=submission_date,
            temperature_celsius=float(temp_val) if temp_val is not None else None,
            behavior_score=behavior_score,
            milk_yield_liters=float(rec["milk_yield_liters"]) if rec.get("milk_yield_liters") is not None else None,
            treatments=rec.get("treatments"),
            notes=rec.get("notes"),
            created_by=actor_user_id,
            signature=signature_b64,   # batch signature — traceable to ledger entry
        )
        session.add(hr)
        processed += 1

    log.info(
        "Health submission: farm=%s processed=%d failed=%d ledger=%s",
        farm_id, processed, len(failed), ledger_entry.id,
    )
    return {
        "processed_count": processed,
        "failed_records": failed,
        "ledger_entry_id": ledger_entry.id,
        "verification_status": "valid",
    }


# ---------------------------------------------------------------------------
# Animal profile
# ---------------------------------------------------------------------------

async def get_animal_profile(
    *,
    session: AsyncSession,
    animal_id: uuid.UUID,
    farm_id: uuid.UUID,
    history_days: int = 90,
) -> dict[str, Any]:
    """
    Return a complete health profile for one animal.

    Includes:
      - Identity fields (breed, sex, age)
      - Full health history (last *history_days* days)
      - Computed metrics (avg temp, yield trend)
      - Current health status (derived, not stored)
      - Risk flags

    Raises:
        AnimalNotOwnedError: animal not found or not owned by farm.
    """
    animal = await _get_animal_for_farm(session, animal_id, farm_id)
    if animal is None:
        raise AnimalNotOwnedError(
            f"Animal {animal_id} not found or does not belong to farm {farm_id}"
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=history_days)
    result = await session.execute(
        select(HealthRecord)
        .where(HealthRecord.animal_id == animal_id, HealthRecord.record_date >= cutoff)
        .order_by(HealthRecord.record_date.asc())
    )
    records = list(result.scalars().all())
    record_dicts = [_hr_to_dict(r) for r in records]

    metrics = _compute_metrics(record_dicts)
    health_status = calculate_health_status(record_dicts, window_days=7)
    risk_flags = generate_risk_flags(animal.id, animal.tag_number, record_dicts)

    age_days: int | None = None
    if animal.date_of_birth:
        dob = animal.date_of_birth
        if dob.tzinfo is None:
            dob = dob.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - dob).days

    return {
        "id": str(animal.id),
        "tag_number": animal.tag_number,
        "breed": animal.breed,
        "sex": animal.sex,
        "age_days": age_days,
        "farm_id": str(animal.farm_id),
        "ownership_status": animal.status,
        "acquired_at": animal.acquired_at.isoformat() if animal.acquired_at else None,
        "current_health_status": health_status,
        "avg_temperature_celsius": metrics.get("avg_temp"),
        "avg_milk_yield_liters": metrics.get("avg_yield"),
        "yield_trend_pct": metrics.get("yield_trend_pct"),
        "avg_behavior_score": metrics.get("avg_behavior"),
        "avg_behavior_label": BEHAVIOR_LABEL_MAP.get(round(metrics["avg_behavior"])) if metrics.get("avg_behavior") else None,
        "health_history": record_dicts,
        "risk_flags": risk_flags,
        "history_days": history_days,
        "record_count": len(records),
    }


# ---------------------------------------------------------------------------
# Farm dashboard
# ---------------------------------------------------------------------------

async def get_farm_dashboard_data(
    *,
    session: AsyncSession,
    farm_id: uuid.UUID,
    window_days: int = 30,
) -> dict[str, Any]:
    """
    Aggregate herd health metrics and generate intervention alerts for the dashboard.

    Queries all active animals + their health records within *window_days*.
    Health status and risk flags are computed per-animal then rolled up.

    Returns::

        {
          "farm_id": str,
          "window_days": int,
          "herd_summary": { total_animals, healthy, at_risk, alert, unknown, treated_last_N_days },
          "metrics": { avg_milk_yield, yield_trend_pct, avg_temperature, avg_behavior, disease_prevalence_pct, records_in_window },
          "intervention_alerts": [ { flag_type, animal_id, tag_number, message, severity } ],
        }

    Raises:
        FarmNotFoundError: farm_id not found.
    """
    await _get_farm(session, farm_id)

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    animals_result = await session.execute(
        select(Animal).where(Animal.farm_id == farm_id, Animal.status == AnimalStatus.ACTIVE)
    )
    animals = list(animals_result.scalars().all())

    if not animals:
        return {
            "farm_id": str(farm_id),
            "window_days": window_days,
            "herd_summary": {"total_animals": 0, "healthy": 0, "at_risk": 0, "alert": 0, "unknown": 0, "treated_last_30_days": 0},
            "metrics": {"avg_milk_yield_liters": None, "yield_trend_pct": None, "avg_temperature_celsius": None, "avg_behavior_score": None, "disease_prevalence_pct": 0.0, "records_in_window": 0},
            "intervention_alerts": [],
        }

    records_result = await session.execute(
        select(HealthRecord)
        .where(HealthRecord.farm_id == farm_id, HealthRecord.record_date >= cutoff)
        .order_by(HealthRecord.record_date.asc())
    )
    all_records = list(records_result.scalars().all())

    # Group records by animal
    by_animal: dict[uuid.UUID, list[dict]] = {a.id: [] for a in animals}
    for r in all_records:
        if r.animal_id in by_animal:
            by_animal[r.animal_id].append(_hr_to_dict(r))

    # Per-animal health status + risk flags
    status_counts: dict[str, int] = {"healthy": 0, "at_risk": 0, "alert": 0, "unknown": 0}
    all_flags: list[dict] = []
    for animal in animals:
        recs = by_animal[animal.id]
        status = calculate_health_status(recs, window_days=7)
        status_counts[status] = status_counts.get(status, 0) + 1
        all_flags.extend(generate_risk_flags(animal.id, animal.tag_number, recs))

    treated_count = sum(
        1 for r in all_records
        if r.treatments and len(r.treatments) > 0
    )

    all_record_dicts = [_hr_to_dict(r) for r in all_records]
    metrics = _compute_metrics(all_record_dicts)
    at_risk_total = status_counts.get("at_risk", 0) + status_counts.get("alert", 0)
    disease_prevalence_pct = round((at_risk_total / len(animals)) * 100, 1) if animals else 0.0

    return {
        "farm_id": str(farm_id),
        "window_days": window_days,
        "herd_summary": {
            "total_animals": len(animals),
            "healthy": status_counts.get("healthy", 0),
            "at_risk": status_counts.get("at_risk", 0),
            "alert": status_counts.get("alert", 0),
            "unknown": status_counts.get("unknown", 0),
            f"treated_last_{window_days}_days": treated_count,
        },
        "metrics": {
            "avg_milk_yield_liters": metrics.get("avg_yield"),
            "yield_trend_pct": metrics.get("yield_trend_pct"),
            "avg_temperature_celsius": metrics.get("avg_temp"),
            "avg_behavior_score": metrics.get("avg_behavior"),
            "disease_prevalence_pct": disease_prevalence_pct,
            "records_in_window": len(all_records),
        },
        "intervention_alerts": all_flags,
    }


# ---------------------------------------------------------------------------
# Health status calculation  (pure — no DB)
# ---------------------------------------------------------------------------

def calculate_health_status(records: list[dict[str, Any]], window_days: int = 7) -> str:
    """
    Derive a health status string from a list of health record dicts.

    Rules (evaluated in priority order: alert > at_risk > healthy):
      alert    — temp > 39.5°C in ≥2 observations  OR  yield drop > 40%  OR  lethargic ≥3 obs
      at_risk  — avg_temp > 39°C  OR  yield drop > 20%  OR  depressed ≥2 obs
      healthy  — avg_temp 37.5–39°C  AND  no major behaviour issue

    Args:
        records:     List of _hr_to_dict() dicts, sorted oldest-first.
        window_days: Only records within this many days from now are used.

    Returns:
        "healthy" | "at_risk" | "alert" | "unknown"
    """
    if not records:
        return "unknown"

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    recent = [r for r in records if _record_date(r) >= cutoff]
    if not recent:
        recent = records[-3:]   # use last 3 if window is empty

    temps = [r["temperature_celsius"] for r in recent if r.get("temperature_celsius") is not None]
    yields = [r["milk_yield_liters"] for r in recent if r.get("milk_yield_liters") is not None]
    behaviors = [r["behavior_score"] for r in recent if r.get("behavior_score") is not None]

    # ── Alert conditions ──────────────────────────────────────────────────────
    if sum(1 for t in temps if t > 39.5) >= 2:
        return "alert"

    if len(yields) >= 4:
        half = max(len(yields) // 2, 1)
        early_avg = sum(yields[:half]) / half
        late_avg = sum(yields[-half:]) / half
        if early_avg > 0 and (early_avg - late_avg) / early_avg > 0.40:
            return "alert"

    if sum(1 for b in behaviors if b >= 3) >= 3:
        return "alert"

    # ── At-risk conditions ────────────────────────────────────────────────────
    avg_temp = sum(temps) / len(temps) if temps else None
    if avg_temp is not None and avg_temp > 39.0:
        return "at_risk"

    if len(yields) >= 4:
        half = max(len(yields) // 2, 1)
        early_avg = sum(yields[:half]) / half
        late_avg = sum(yields[-half:]) / half
        if early_avg > 0 and (early_avg - late_avg) / early_avg > 0.20:
            return "at_risk"

    if sum(1 for b in behaviors if b >= 2) >= 2:
        return "at_risk"

    # ── Healthy ───────────────────────────────────────────────────────────────
    if avg_temp is not None and not (37.5 <= avg_temp <= 39.0):
        return "at_risk"   # temp outside normal range but not fever

    return "healthy"


# ---------------------------------------------------------------------------
# Risk flag generation  (pure — no DB)
# ---------------------------------------------------------------------------

def generate_risk_flags(
    animal_id: uuid.UUID,
    tag_number: str,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Scan recent health observations and produce actionable alert dicts.

    Each flag dict contains:
        flag_type, animal_id, tag_number, message, severity

    Severity levels: "low" | "medium" | "high"
    """
    if not records:
        return []

    flags: list[dict[str, Any]] = []
    recent = sorted(records, key=lambda r: str(r.get("record_date") or ""))[-14:]

    temps    = [r["temperature_celsius"] for r in recent if r.get("temperature_celsius") is not None]
    yields   = [r["milk_yield_liters"]   for r in recent if r.get("milk_yield_liters")   is not None]
    behaviors= [r["behavior_score"]      for r in recent if r.get("behavior_score")      is not None]

    aid = str(animal_id)

    # ── 1. Fever alert: temp > 39.5°C in ≥2 consecutive observations ─────────
    max_run = _max_consecutive(temps, threshold=39.5, above=True)
    if max_run >= 2:
        flags.append({
            "flag_type": "fever_alert",
            "animal_id": aid,
            "tag_number": tag_number,
            "message": f"Temperature exceeded 39.5°C in {max_run} consecutive observations",
            "severity": "high",
        })

    # ── 2. Production decline: yield drop > 30% from baseline ────────────────
    if len(yields) >= 4:
        half = max(len(yields) // 2, 1)
        baseline = sum(yields[:half]) / half
        current  = sum(yields[-half:]) / half
        if baseline > 0:
            drop_pct = ((baseline - current) / baseline) * 100
            if drop_pct > 30:
                flags.append({
                    "flag_type": "production_decline",
                    "animal_id": aid,
                    "tag_number": tag_number,
                    "message": (
                        f"Milk yield declined {drop_pct:.1f}% from baseline "
                        f"({baseline:.1f} L → {current:.1f} L)"
                    ),
                    "severity": "high" if drop_pct > 50 else "medium",
                })

    # ── 3. Behavioral change: lethargic/distressed for ≥3 observations ───────
    severe_behavior_count = sum(1 for b in behaviors if b >= 3)
    if severe_behavior_count >= 3:
        flags.append({
            "flag_type": "behavioral_change",
            "animal_id": aid,
            "tag_number": tag_number,
            "message": (
                f"Lethargic or worse behaviour recorded in "
                f"{severe_behavior_count} of the last {len(behaviors)} observations"
            ),
            "severity": "medium",
        })

    # ── 4. Estrus window heuristic: temp dip + behavior + yield pattern ───────
    if len(temps) >= 3 and len(behaviors) >= 2:
        baseline_temp = sum(temps[:-1]) / len(temps[:-1])
        temp_dip = temps[-1] < (baseline_temp - 0.3)
        restless = behaviors[-1] in (2, 3)     # depressed / lethargic (may indicate estrus)
        if temp_dip and restless:
            flags.append({
                "flag_type": "estrus_window",
                "animal_id": aid,
                "tag_number": tag_number,
                "message": "Possible estrus: temperature dip and behavioural change detected",
                "severity": "low",
            })

    # ── 5. Treatment needed: alert symptoms + no recent treatment ─────────────
    has_fever_or_distress = max_run >= 2 or (behaviors and behaviors[-1] >= 4)
    recent_treatments = [r for r in recent[-3:] if r.get("treatments")]
    if has_fever_or_distress and not recent_treatments:
        flags.append({
            "flag_type": "treatment_needed",
            "animal_id": aid,
            "tag_number": tag_number,
            "message": "Alert-level symptoms detected but no treatment recorded in last 3 observations",
            "severity": "high",
        })

    return flags


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

async def _get_farm(session: AsyncSession, farm_id: uuid.UUID) -> Farm:
    result = await session.execute(select(Farm).where(Farm.id == farm_id))
    farm = result.scalar_one_or_none()
    if farm is None:
        raise FarmNotFoundError(f"Farm {farm_id} not found")
    return farm


async def _get_animal_for_farm(
    session: AsyncSession,
    animal_id: uuid.UUID,
    farm_id: uuid.UUID,
) -> Animal | None:
    result = await session.execute(
        select(Animal).where(Animal.id == animal_id, Animal.farm_id == farm_id)
    )
    return result.scalar_one_or_none()


async def _resolve_animal_by_tag(
    session: AsyncSession,
    farm_id: uuid.UUID,
    tag_number: str,
) -> uuid.UUID | None:
    """Look up an animal by tag_number within a farm. Returns its UUID or None."""
    result = await session.execute(
        select(Animal.id).where(
            Animal.farm_id == farm_id,
            Animal.tag_number == tag_number,
        )
    )
    row = result.scalar_one_or_none()
    return row


def _hr_to_dict(r: HealthRecord) -> dict[str, Any]:
    """Convert a HealthRecord ORM object to a plain dict for analysis."""
    return {
        "id": str(r.id),
        "animal_id": str(r.animal_id),
        "farm_id": str(r.farm_id),
        "record_date": r.record_date.isoformat() if r.record_date else None,
        "temperature_celsius": r.temperature_celsius,
        "behavior_score": r.behavior_score,
        "behavior_label": BEHAVIOR_LABEL_MAP.get(r.behavior_score) if r.behavior_score else None,
        "milk_yield_liters": r.milk_yield_liters,
        "body_condition_score": r.body_condition_score,
        "treatments": r.treatments,
        "vaccinations": r.vaccinations,
        "notes": r.notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _compute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute aggregate metrics from a list of health record dicts.
    Uses pandas if available; falls back to pure Python.
    """
    if not records:
        return {}

    temps    = [r["temperature_celsius"] for r in records if r.get("temperature_celsius") is not None]
    yields   = [r["milk_yield_liters"]   for r in records if r.get("milk_yield_liters")   is not None]
    behaviors= [r["behavior_score"]      for r in records if r.get("behavior_score")      is not None]

    result: dict[str, Any] = {}

    try:
        import pandas as pd
        if temps:
            result["avg_temp"] = round(pd.Series(temps).mean(), 2)
        if yields:
            s = pd.Series(yields)
            result["avg_yield"] = round(float(s.mean()), 2)
            if len(s) >= 4:
                half = max(len(s) // 2, 1)
                early = float(s.iloc[:half].mean())
                late  = float(s.iloc[-half:].mean())
                result["yield_trend_pct"] = round(((late - early) / early) * 100, 1) if early else None
        if behaviors:
            result["avg_behavior"] = round(pd.Series(behaviors).mean(), 2)

    except ImportError:
        if temps:
            result["avg_temp"] = round(sum(temps) / len(temps), 2)
        if yields:
            result["avg_yield"] = round(sum(yields) / len(yields), 2)
            if len(yields) >= 4:
                half = max(len(yields) // 2, 1)
                early = sum(yields[:half]) / half
                late  = sum(yields[-half:]) / half
                result["yield_trend_pct"] = round(((late - early) / early) * 100, 1) if early else None
        if behaviors:
            result["avg_behavior"] = round(sum(behaviors) / len(behaviors), 2)

    return result


def _try_parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


def _record_date(r: dict[str, Any]) -> datetime:
    """Parse record_date from a health record dict, returning UTC-aware datetime."""
    raw = r.get("record_date")
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=timezone.utc) if raw.tzinfo is None else raw
    if isinstance(raw, str):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def _max_consecutive(values: list[float], threshold: float, above: bool = True) -> int:
    """Return the length of the longest consecutive run where value > threshold (if above=True)."""
    max_run = 0
    current = 0
    for v in values:
        hit = (v > threshold) if above else (v < threshold)
        if hit:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run
