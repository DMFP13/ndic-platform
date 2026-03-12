"""
NDIC Supply + Cost Forecasting Service
────────────────────────────────────────
Provides three forecasting functions:

  forecast_milk_supply()      — 30-day volume forecast for processors
                                 (ExponentialSmoothing with seasonal component)
  forecast_production_cost()  — 3-month cost-per-litre forecast for farms
                                 (Nigerian dairy cost structure + inflation)
  assess_climate_risk()       — Drought / flood risk for a farm location
                                 (agro-ecological zone model; calls climate_risk.get_climate_forecast())

Phase 4: ARIMA/ExponentialSmoothing requires statsmodels.
         Falls back to naive mean forecast if not installed or if data is sparse.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Animal, Farm, HealthRecord, ProcessorIntake
from models.enums import AnimalStatus

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional statsmodels dependency
# ---------------------------------------------------------------------------
try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    _STATSMODELS = True
except ImportError:
    _STATSMODELS = False
    log.warning("statsmodels not installed — milk supply forecast will use naive method")

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False


# ===========================================================================
# Milk supply forecast
# ===========================================================================

async def forecast_milk_supply(
    session: AsyncSession,
    processor_org_id: Any,          # uuid.UUID
    days_ahead: int = 30,
) -> dict[str, Any]:
    """
    Forecast daily milk intake volume for a processor over the next *days_ahead* days.

    Method:
      - Queries the last 90 days of ProcessorIntake records, grouped by day.
      - If ≥14 daily observations: Holt-Winters ExponentialSmoothing
        (additive trend + weekly seasonality if ≥14 days).
      - Fewer than 14 observations: naive rolling-mean forecast.

    Returns::

        {
          "processor_org_id": str,
          "days_ahead": int,
          "daily_forecast": [float, ...],   # litres per day
          "lower_bound":    [float, ...],   # 90% CI lower
          "upper_bound":    [float, ...],   # 90% CI upper
          "confidence":     float,
          "model":          str,
          "historical_days": int,
        }
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    # Daily aggregated intakes
    result = await session.execute(
        select(
            func.date_trunc("day", ProcessorIntake.intake_date).label("day"),
            func.sum(ProcessorIntake.volume_liters).label("volume"),
        )
        .where(
            ProcessorIntake.processor_org_id == processor_org_id,
            ProcessorIntake.intake_date >= cutoff,
        )
        .group_by(func.date_trunc("day", ProcessorIntake.intake_date))
        .order_by(func.date_trunc("day", ProcessorIntake.intake_date))
    )
    rows = result.all()
    volumes = [float(r.volume) for r in rows]

    if not volumes:
        return {
            "processor_org_id": str(processor_org_id),
            "days_ahead": days_ahead,
            "daily_forecast": [0.0] * days_ahead,
            "lower_bound": [0.0] * days_ahead,
            "upper_bound": [0.0] * days_ahead,
            "confidence": 0.0,
            "model": "no_data",
            "historical_days": 0,
        }

    if len(volumes) >= 14 and _STATSMODELS:
        try:
            model_kwargs: dict[str, Any] = {"trend": "add"}
            if len(volumes) >= 14:
                model_kwargs["seasonal"]         = "add"
                model_kwargs["seasonal_periods"] = 7
            fit = ExponentialSmoothing(volumes, **model_kwargs).fit(optimized=True)
            forecast = [max(0.0, float(v)) for v in fit.forecast(days_ahead)]
            residual_std = float(
                (sum((a - b) ** 2 for a, b in zip(fit.fittedvalues, volumes)) / len(volumes)) ** 0.5
            ) if _NUMPY else _std_dev(volumes)
            z90 = 1.645
            lower = [round(max(0.0, f - z90 * residual_std), 1) for f in forecast]
            upper = [round(f + z90 * residual_std, 1) for f in forecast]
            model_name = "ExponentialSmoothing"
            confidence = 0.9
        except Exception as exc:
            log.warning("ExponentialSmoothing failed (%s) — using naive forecast", exc)
            forecast, lower, upper, model_name, confidence = _naive_forecast(volumes, days_ahead)
    else:
        forecast, lower, upper, model_name, confidence = _naive_forecast(volumes, days_ahead)

    return {
        "processor_org_id": str(processor_org_id),
        "days_ahead": days_ahead,
        "daily_forecast": [round(v, 1) for v in forecast],
        "lower_bound":    lower,
        "upper_bound":    upper,
        "confidence":     confidence,
        "model":          model_name,
        "historical_days": len(volumes),
    }


# ===========================================================================
# Production cost forecast
# ===========================================================================

async def forecast_production_cost(
    session: AsyncSession,
    farm_id: Any,       # uuid.UUID
    months_ahead: int = 3,
) -> dict[str, Any]:
    """
    Project monthly production costs for a farm over the next *months_ahead* months.

    Cost model (Nigerian dairy sector, NGN, 2024 estimates):
      Feed:    ₦1,500 / animal / day (+2% monthly inflation)
      Labour:  ₦500   / animal / day (fixed)
      Vet:     ₦3,000 / animal / month (fixed)
      Overhead:₦300   / animal / day (fixed)

    Yield is estimated from recent HealthRecord averages.

    Returns::

        {
          "farm_id": str,
          "months_ahead": int,
          "monthly_forecast": [ { month, active_animals, feed_cost_ngn,
                                   labour_cost_ngn, vet_cost_ngn,
                                   overhead_ngn, total_cost_ngn,
                                   estimated_yield_liters, cost_per_liter_ngn }, ... ],
        }
    """
    # Active herd count
    count_result = await session.execute(
        select(func.count(Animal.id)).where(
            Animal.farm_id == farm_id,
            Animal.status == AnimalStatus.ACTIVE,
        )
    )
    active_count = int(count_result.scalar() or 0)

    # Average daily milk yield from last 30 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    yield_result = await session.execute(
        select(func.avg(HealthRecord.milk_yield_liters)).where(
            HealthRecord.farm_id == farm_id,
            HealthRecord.record_date >= cutoff,
            HealthRecord.milk_yield_liters > 0,
        )
    )
    avg_daily_yield = float(yield_result.scalar() or 10.0)  # default 10 L/cow/day

    # Nigerian dairy cost constants
    FEED_PER_COW_DAY    = 1_500   # NGN
    LABOUR_PER_COW_DAY  = 500     # NGN
    VET_PER_COW_MONTH   = 3_000   # NGN
    OVERHEAD_PER_COW_DAY= 300     # NGN
    FEED_INFLATION_MO   = 0.02    # 2% per month

    monthly: list[dict[str, Any]] = []
    for m in range(1, months_ahead + 1):
        feed      = active_count * FEED_PER_COW_DAY * 30 * ((1 + FEED_INFLATION_MO) ** m)
        labour    = active_count * LABOUR_PER_COW_DAY * 30
        vet       = active_count * VET_PER_COW_MONTH
        overhead  = active_count * OVERHEAD_PER_COW_DAY * 30
        total     = feed + labour + vet + overhead
        yield_l   = active_count * avg_daily_yield * 30
        cpl       = total / max(yield_l, 1.0)

        monthly.append({
            "month":                  m,
            "active_animals":         active_count,
            "feed_cost_ngn":          round(feed),
            "labour_cost_ngn":        round(labour),
            "vet_cost_ngn":           round(vet),
            "overhead_ngn":           round(overhead),
            "total_cost_ngn":         round(total),
            "estimated_yield_liters": round(yield_l),
            "cost_per_liter_ngn":     round(cpl, 2),
        })

    return {
        "farm_id":                str(farm_id),
        "months_ahead":           months_ahead,
        "active_animals":         active_count,
        "avg_daily_yield_liters": round(avg_daily_yield, 2),
        "monthly_forecast":       monthly,
        "assumptions": {
            "feed_ngn_per_cow_day":    FEED_PER_COW_DAY,
            "labour_ngn_per_cow_day":  LABOUR_PER_COW_DAY,
            "vet_ngn_per_cow_month":   VET_PER_COW_MONTH,
            "overhead_ngn_per_cow_day":OVERHEAD_PER_COW_DAY,
            "feed_monthly_inflation":  f"{FEED_INFLATION_MO * 100:.0f}%",
        },
    }


# ===========================================================================
# Climate risk assessment
# ===========================================================================

def assess_climate_risk(
    coordinates: dict[str, float],
    months_ahead: int = 3,
) -> dict[str, Any]:
    """
    Estimate drought and flood risk for a farm location.

    Uses Nigeria's agro-ecological zone model (no external API in Phase 4).
    OpenWeatherMap / NOAA integration is Phase 5.

    Args:
        coordinates:  {"lat": float, "lng": float}
        months_ahead: Forward-looking horizon (affects seasonal adjustment).

    Returns::

        {
          "coordinates": dict,
          "agro_ecological_zone": str,
          "drought_risk_percent": int (0-100),
          "flood_risk_percent": int (0-100),
          "expected_productivity_impact": str ("low"|"medium"|"high"),
          "forecast_rainfall_mm": float,
          "forecast_temp_avg_c": float,
          "mitigation_actions": [str],
          "data_source": str,
        }
    """
    from app.services.climate_risk import get_climate_forecast

    lat = float(coordinates.get("lat", 9.0))

    # Agro-ecological zones by latitude
    if lat > 13.0:
        zone = "sahel"
        base_drought = 80
        base_flood   = 5
        impact       = "high"
    elif lat > 10.0:
        zone = "sudan_savanna"
        base_drought = 55
        base_flood   = 20
        impact       = "high"
    elif lat > 7.0:
        zone = "guinea_savanna"
        base_drought = 35
        base_flood   = 35
        impact       = "medium"
    elif lat > 5.0:
        zone = "derived_savanna"
        base_drought = 20
        base_flood   = 50
        impact       = "medium"
    else:
        zone = "rainforest_coastal"
        base_drought = 10
        base_flood   = 70
        impact       = "medium"

    # Seasonal adjustment: Nigeria's dry season (Nov–Mar)
    forecast_month = (datetime.now(timezone.utc).month + months_ahead - 1) % 12 + 1
    is_dry_season = forecast_month in (11, 12, 1, 2, 3)
    if is_dry_season:
        base_drought = min(100, base_drought + 15)
        base_flood   = max(0,   base_flood   - 15)
    else:
        base_drought = max(0,   base_drought - 10)
        base_flood   = min(100, base_flood   + 10)

    weather = get_climate_forecast(coordinates)
    mitigation = _mitigation_actions(zone, base_drought, base_flood)

    return {
        "coordinates":                    coordinates,
        "agro_ecological_zone":           zone,
        "assessment_months_ahead":        months_ahead,
        "drought_risk_percent":           base_drought,
        "flood_risk_percent":             base_flood,
        "expected_productivity_impact":   impact,
        "forecast_rainfall_mm_30_days":   weather.get("rainfall_mm_next_30_days"),
        "forecast_temp_avg_c":            weather.get("temp_avg"),
        "forecast_humidity_pct":          weather.get("humidity_pct"),
        "mitigation_actions":             mitigation,
        "data_source":                    "ndic_agro_ecological_model_v1",
    }


# ===========================================================================
# Private helpers
# ===========================================================================

def _naive_forecast(
    volumes: list[float],
    days_ahead: int,
) -> tuple[list[float], list[float], list[float], str, float]:
    """Rolling-mean naive forecast with ±1 std deviation bounds."""
    window = volumes[-7:] if len(volumes) >= 7 else volumes
    mean_v = sum(window) / len(window)
    std_v  = _std_dev(window)

    forecast = [round(max(0.0, mean_v), 1)] * days_ahead
    lower    = [round(max(0.0, mean_v - std_v), 1)] * days_ahead
    upper    = [round(mean_v + std_v, 1)] * days_ahead
    return forecast, lower, upper, "naive_rolling_mean", 0.6


def _std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5


def _mitigation_actions(
    zone: str,
    drought_risk: int,
    flood_risk: int,
) -> list[str]:
    actions: list[str] = []
    if drought_risk > 60:
        actions += [
            "Secure supplemental feed reserves for at least 60 days",
            "Increase water storage capacity (drought season approaching)",
            "Consider early weaning to reduce lactation demands",
        ]
    elif drought_risk > 30:
        actions += [
            "Monitor rangeland condition weekly",
            "Ensure water sources are maintained",
        ]
    if flood_risk > 50:
        actions += [
            "Prepare elevated shelter areas for the herd",
            "Review farm drainage plan before wet season",
            "Stock emergency feed in case of access disruption",
        ]
    if not actions:
        actions.append("No immediate climate interventions required — continue routine monitoring")
    return actions
