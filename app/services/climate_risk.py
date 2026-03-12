"""
NDIC Climate Risk & Herd Resilience Service
─────────────────────────────────────────────
herd_resilience_score()  — Composite score based on breed genetics, age distribution,
                            and herd diversity.  Zebu (indigenous) breeds score highest
                            on Nigerian climate resilience.
get_climate_forecast()   — Mock weather forecast by agro-ecological zone.
                            Phase 5 will replace with OpenWeatherMap / NOAA calls.

Breed resilience scores are based on published West African livestock research:
  - Bunaji (White Fulani) and Rahaji show excellent heat tolerance and disease resistance
  - Holstein Friesian has poor heat tolerance in tropical climates (Schlecht et al., 2006)
  - Crossbreeds offer intermediate resilience
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Animal
from models.enums import AnimalStatus

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Breed resilience lookup  (0-100; higher = more resilient to Nigerian climate)
# ---------------------------------------------------------------------------
BREED_RESILIENCE_SCORES: dict[str, int] = {
    "bunaji":               90,   # White Fulani — dominant Nigerian dairy breed; excellent tolerance
    "rahaji":               88,   # Red Fulani — close to Bunaji in resilience
    "azawak":               85,   # Sahelian zebu; extreme drought tolerance
    "shuwa_arab":           84,   # North-east Nigeria; high heat & tick resistance
    "muturu":               80,   # West African Dwarf; trypanotolerant — forest zones
    "keteku":               74,   # Yoruba crossbreed; moderate resilience
    "friesian_bunaji_cross":65,   # Improved fertility, better than pure Friesian
    "crossbreed":           62,   # Generic cross — depends on parentage
    "brown_swiss":          55,   # Moderate heat tolerance
    "jersey":               50,   # Heat-sensitive but better than Holstein
    "friesian":             30,   # Holstein Friesian — poor heat tolerance in tropics
    "other":                65,   # Conservative default
}

# Prime productive age range (months)
_PRIME_AGE_MIN_MO = 24
_PRIME_AGE_MAX_MO = 84


# ===========================================================================
# Herd resilience scoring
# ===========================================================================

async def herd_resilience_score(
    session: AsyncSession,
    farm_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Compute a composite climate resilience score (0-100) for a farm's active herd.

    Component weights:
      Breed resilience   50%  — weighted by breed distribution
      Age resilience     30%  — prime-age animals score highest
      Herd diversity     20%  — mixed breeds buffer against uniform susceptibility

    Returns::

        {
          "farm_id": str,
          "resilience_score": int,
          "breed_resilience_score": int,
          "age_resilience_score": int,
          "herd_diversity_score": int,
          "total_active_animals": int,
          "breed_distribution": { breed: count },
          "fragility_factors": [str],
          "adaptation_potential": [str],
        }
    """
    # ── Breed distribution ────────────────────────────────────────────────────
    breed_result = await session.execute(
        select(Animal.breed, func.count(Animal.id).label("cnt"))
        .where(Animal.farm_id == farm_id, Animal.status == AnimalStatus.ACTIVE)
        .group_by(Animal.breed)
    )
    breed_counts = breed_result.all()

    if not breed_counts:
        return {
            "farm_id": str(farm_id),
            "resilience_score": None,
            "error": "No active animals found for this farm",
        }

    total_animals = int(sum(r.cnt for r in breed_counts))
    breed_distribution = {str(r.breed): int(r.cnt) for r in breed_counts}

    weighted_breed = sum(
        BREED_RESILIENCE_SCORES.get(str(r.breed), 65) * r.cnt
        for r in breed_counts
    ) / total_animals

    # ── Age distribution ──────────────────────────────────────────────────────
    dob_result = await session.execute(
        select(Animal.date_of_birth)
        .where(
            Animal.farm_id == farm_id,
            Animal.status == AnimalStatus.ACTIVE,
            Animal.date_of_birth.isnot(None),
        )
    )
    dobs = [row[0] for row in dob_result.all()]

    now = datetime.now(timezone.utc)
    age_months: list[float] = []
    for dob in dobs:
        if dob is None:
            continue
        if dob.tzinfo is None:
            dob = dob.replace(tzinfo=timezone.utc)
        age_months.append((now - dob).days / 30.44)

    age_score = _age_resilience(age_months)

    # ── Herd diversity ────────────────────────────────────────────────────────
    # More breed varieties = more robust to novel disease / climate events
    n_breeds = len(breed_counts)
    diversity_score = min(100, n_breeds * 14)   # maxes at ~7 breeds

    # ── Composite score ───────────────────────────────────────────────────────
    overall = round(
        weighted_breed * 0.50 +
        age_score      * 0.30 +
        diversity_score* 0.20
    )

    fragility    = _fragility_factors(weighted_breed, age_months, total_animals)
    adaptation   = _adaptation_potential(breed_counts, diversity_score, weighted_breed)

    return {
        "farm_id":               str(farm_id),
        "resilience_score":      overall,
        "breed_resilience_score":round(weighted_breed),
        "age_resilience_score":  round(age_score),
        "herd_diversity_score":  diversity_score,
        "total_active_animals":  total_animals,
        "breed_distribution":    breed_distribution,
        "fragility_factors":     fragility,
        "adaptation_potential":  adaptation,
    }


# ===========================================================================
# Weather / climate data (mock in Phase 4)
# ===========================================================================

def get_climate_forecast(
    coordinates: dict[str, float],
) -> dict[str, Any]:
    """
    Return a 30-day weather forecast for *coordinates*.

    Phase 4 implementation: deterministic mock based on Nigeria's agro-ecological
    zones and current calendar month.  Values are seeded from lat/lng/month so the
    same location always returns the same values within a month.

    Phase 5: replace with OpenWeatherMap API or NOAA CFSv2 product.

    Args:
        coordinates: {"lat": float, "lng": float}

    Returns::

        {
          "rainfall_mm_next_30_days": float,
          "temp_avg": float (°C),
          "temp_variance": float,
          "humidity_pct": int,
          "data_source": str,
          "coordinates": dict,
        }
    """
    import random

    lat   = float(coordinates.get("lat", 9.0))
    lng   = float(coordinates.get("lng", 7.5))
    month = datetime.now(timezone.utc).month

    # Deterministic seed: same location + month → same mock values
    rng = random.Random(int(abs(lat) * 1000 + abs(lng) * 100 + month))

    is_dry      = month in (11, 12, 1, 2, 3)
    is_peak_wet = month in (7, 8, 9)

    # Baseline by latitude zone
    if lat > 13:
        base_rain, base_temp, base_humid = (10, 36, 30) if is_dry else (60, 33, 55)
    elif lat > 10:
        base_rain, base_temp, base_humid = (20, 34, 35) if is_dry else (120, 31, 65)
    elif lat > 7:
        base_rain, base_temp, base_humid = (40, 32, 45) if is_dry else (200, 28, 80)
    else:
        base_rain, base_temp, base_humid = (80, 30, 70) if is_dry else (300, 27, 90)

    if is_peak_wet and lat <= 10:
        base_rain = int(base_rain * 1.5)

    return {
        "rainfall_mm_next_30_days": round(base_rain  + rng.uniform(-10, 10), 1),
        "temp_avg":                 round(base_temp  + rng.uniform(-1,   1), 1),
        "temp_variance":            round(rng.uniform(3, 8), 1),
        "humidity_pct":             base_humid,
        "data_source":              "ndic_agro_ecological_mock_v1",
        "note":                     "Phase 4 mock data — OpenWeatherMap integration in Phase 5",
        "coordinates":              coordinates,
    }


# ===========================================================================
# Private helpers
# ===========================================================================

def _age_resilience(age_months: list[float]) -> float:
    """Score 0-100 based on age distribution.  Prime-age (24-84 mo) scores best."""
    if not age_months:
        return 70.0   # neutral default when DOBs not recorded

    prime  = sum(1 for a in age_months if _PRIME_AGE_MIN_MO <= a <= _PRIME_AGE_MAX_MO)
    young  = sum(1 for a in age_months if a < _PRIME_AGE_MIN_MO)
    old    = sum(1 for a in age_months if a > _PRIME_AGE_MAX_MO)
    n      = len(age_months)

    return (prime * 85 + young * 60 + old * 45) / n


def _fragility_factors(
    breed_score: float,
    age_months: list[float],
    total: int,
) -> list[str]:
    factors: list[str] = []
    if breed_score < 50:
        factors.append("High proportion of exotic breeds with poor heat tolerance")
    if age_months and max(age_months) > 96:
        factors.append("Some animals are past prime productive age (>8 years)")
    if age_months and min(age_months) < 12:
        factors.append("Young animals (<12 months) increase disease vulnerability")
    if total < 5:
        factors.append("Small herd size (<5 animals) — disease outbreak has outsized impact")
    if total > 200:
        factors.append("Large herd density — biosecurity and disease spread risk elevated")
    return factors


def _adaptation_potential(
    breed_counts: list[Any],
    diversity_score: int,
    breed_score: float,
) -> list[str]:
    actions: list[str] = []
    native_breeds = {"bunaji", "rahaji", "azawak", "shuwa_arab", "muturu", "keteku"}
    has_native = any(str(r.breed) in native_breeds for r in breed_counts)

    if has_native:
        actions.append("Indigenous zebu genetics provide strong heat and tick resistance")
    if diversity_score >= 28:
        actions.append("Mixed-breed herd provides a natural buffer against disease outbreaks")
    if breed_score >= 75:
        actions.append("Breed composition is well-suited to Nigerian climate conditions")
    if breed_score < 50:
        actions.append("Consider crossbreeding with indigenous zebu to improve heat tolerance")
        actions.append("Supplemental shade structures recommended for exotic breed welfare")
    return actions
