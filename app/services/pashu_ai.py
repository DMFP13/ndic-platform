"""
Pashu AI — Cattle Health Classification Engine
────────────────────────────────────────────────
Classifies five conditions from time-windowed health records:
  estrus      — breeding window (12-24 h), detected via temp dip + behaviour + yield pattern
  fever       — infection / disease onset, high temperature + behaviour change
  lameness    — mobility issue, lethargic behaviour without fever signal
  mastitis    — udder inflammation, yield drop + slight temperature elevation
  health_score — composite 0-100 score (regression)

Training: Random Forest (estrus, fever, lameness) + Logistic Regression (mastitis)
          + Linear Regression (health_score), all with class_weight='balanced'.
Inference: loads saved joblib models; returns probabilities + confidence score.

Phase 4 does NOT wire classify_animal_health into every submission endpoint.
That integration is Phase 5. This module is callable standalone and from
the training script.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional ML dependencies
# ---------------------------------------------------------------------------
try:
    import numpy as np
    import pandas as pd
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression, LinearRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        precision_score, recall_score, f1_score,
        r2_score, mean_absolute_error,
    )
    _ML_AVAILABLE = True
except ImportError as _e:
    _ML_AVAILABLE = False
    _ML_IMPORT_ERR = str(_e)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_DIR = Path(__file__).parent.parent / "models" / "ml_models"

# Feature vector order — MUST be consistent between training and inference
FEATURE_COLUMNS: list[str] = [
    "temp_mean", "temp_std", "temp_min", "temp_max", "temp_delta",
    "yield_mean", "yield_std", "yield_slope",
    "behav_normal_pct", "behav_depressed_pct", "behav_lethargic_pct",
    "temp_yield_corr", "behavior_change_flag", "days_in_window",
]

LABEL_COLUMNS: dict[str, str] = {
    "estrus":       "label_estrus",
    "fever":        "label_fever",
    "lameness":     "label_lameness",
    "mastitis":     "label_mastitis",
    "health_score": "label_health_score",
}

_BEHAVIOR_SCORE: dict[str, int] = {
    "normal": 1, "depressed": 2, "aggressive": 2,
    "slightly_lethargic": 2, "lethargic": 3, "distressed": 4, "critical": 5,
}


# ===========================================================================
# Feature engineering  (pure — no DB)
# ===========================================================================

def extract_features(
    records: list[dict[str, Any]],
    window_days: int = 7,
) -> dict[str, float]:
    """
    Compute a fixed-length feature vector from a window of health record dicts.

    Each dict should match the output of farm_service._hr_to_dict(), i.e.:
        {"temperature_celsius": float|None, "behavior_score": int|None,
         "milk_yield_liters": float|None, "record_date": str|None, ...}

    Returns a dict keyed by FEATURE_COLUMNS.  Missing sensor readings are
    imputed with population-normal values so inference degrades gracefully.
    """
    if not records:
        return _zero_features()

    # Sort oldest-first and take the window tail
    records = sorted(records, key=lambda r: str(r.get("record_date") or ""))
    recent = records[-window_days:]
    n = len(recent)

    temps     = [r["temperature_celsius"] for r in recent if r.get("temperature_celsius") is not None]
    yields    = [r["milk_yield_liters"]   for r in recent if r.get("milk_yield_liters")   is not None]
    behaviors = [r["behavior_score"]      for r in recent if r.get("behavior_score")      is not None]

    # ── Temperature features ─────────────────────────────────────────────────
    if temps:
        temp_mean  = float(sum(temps) / len(temps))
        temp_std   = float(_std(temps))
        temp_min   = float(min(temps))
        temp_max   = float(max(temps))
        temp_delta = float(temps[-1] - temps[0]) if len(temps) > 1 else 0.0
    else:
        # Impute with normal bovine baseline
        temp_mean = temp_min = temp_max = 38.5
        temp_std = temp_delta = 0.0

    # ── Yield features ───────────────────────────────────────────────────────
    if yields:
        yield_mean = float(sum(yields) / len(yields))
        yield_std  = float(_std(yields))
        yield_slope = _linear_slope(yields)
    else:
        yield_mean = yield_std = yield_slope = 0.0

    # ── Behaviour features ───────────────────────────────────────────────────
    n_obs = max(len(behaviors), 1)
    behav_normal_pct     = sum(1 for b in behaviors if b == 1) / n_obs
    behav_depressed_pct  = sum(1 for b in behaviors if b == 2) / n_obs
    behav_lethargic_pct  = sum(1 for b in behaviors if b >= 3) / n_obs

    # ── Cross features ───────────────────────────────────────────────────────
    min_len = min(len(temps), len(yields))
    temp_yield_corr = _pearson(temps[:min_len], yields[:min_len]) if min_len > 2 else 0.0

    behavior_change_flag = 0.0
    if len(behaviors) >= 2:
        behavior_change_flag = 1.0 if behaviors[-1] > behaviors[-2] else 0.0

    # ── Feature completeness (diagnostic) ────────────────────────────────────
    total_expected = n * 3
    feature_completeness = (len(temps) + len(yields) + len(behaviors)) / max(total_expected, 1)

    return {
        "temp_mean":            temp_mean,
        "temp_std":             temp_std,
        "temp_min":             temp_min,
        "temp_max":             temp_max,
        "temp_delta":           temp_delta,
        "yield_mean":           yield_mean,
        "yield_std":            yield_std,
        "yield_slope":          yield_slope,
        "behav_normal_pct":     behav_normal_pct,
        "behav_depressed_pct":  behav_depressed_pct,
        "behav_lethargic_pct":  behav_lethargic_pct,
        "temp_yield_corr":      temp_yield_corr,
        "behavior_change_flag": behavior_change_flag,
        "days_in_window":       float(n),
        # Not in FEATURE_COLUMNS — used for confidence only
        "feature_completeness": feature_completeness,
    }


# ===========================================================================
# Training data loading & preparation
# ===========================================================================

def load_training_data(
    csv_path: str | Path,
) -> tuple["pd.DataFrame", "pd.DataFrame"]:
    """
    Read a raw training CSV and return (df_raw, df_features).

    Expected CSV columns:
        animal_id, date, temperature_c, behavior, milk_yield_liters,
        observed_estrus, observed_fever, treatment_given
    Optional columns (derived if absent):
        observed_lameness, observed_mastitis

    Returns:
        df_raw:      Raw per-row DataFrame.
        df_features: Windowed feature matrix with label columns — pass to train_models().
    """
    _require_ml()
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["animal_id", "date"]).reset_index(drop=True)

    # Normalise boolean-ish observed columns
    for col in ("observed_estrus", "observed_fever"):
        if col in df.columns:
            df[col] = df[col].map(
                lambda x: bool(str(x).strip().lower() in ("true", "1", "yes", "1.0"))
            )

    # Derive lameness: lethargic behaviour without high fever
    if "observed_lameness" not in df.columns:
        df["observed_lameness"] = (
            (df["behavior"].str.lower() == "lethargic") &
            (df["temperature_c"] < 39.2)
        )

    # Derive mastitis: yield drop >20% from 7-day rolling baseline + slight fever
    if "observed_mastitis" not in df.columns:
        df["_yield_baseline"] = (
            df.groupby("animal_id")["milk_yield_liters"]
            .transform(lambda x: x.rolling(7, min_periods=2).mean().shift(1))
        )
        df["_yield_drop_pct"] = (
            (df["_yield_baseline"] - df["milk_yield_liters"])
            / df["_yield_baseline"].clip(lower=0.1)
        ) * 100
        df["observed_mastitis"] = (
            (df["_yield_drop_pct"] > 20) &
            (df["temperature_c"].between(38.5, 39.5))
        )
        df.drop(columns=["_yield_baseline", "_yield_drop_pct"], inplace=True)

    df_features = prepare_features(df)
    return df, df_features


def prepare_features(
    df: "pd.DataFrame",
    window_days: int = 7,
) -> "pd.DataFrame":
    """
    Apply sliding-window feature extraction to a raw training DataFrame.
    Public alias for _feature_engineer_dataframe — usable without CSV I/O.
    """
    _require_ml()
    return _feature_engineer_dataframe(df, window_days=window_days)


# ===========================================================================
# Model training
# ===========================================================================

def train_models(
    df_features: "pd.DataFrame",
    test_size: float = 0.3,
    model_dir: Path = MODEL_DIR,
) -> dict[str, dict[str, float]]:
    """
    Train all five models on the feature-engineered DataFrame.

    Args:
        df_features: Output of load_training_data()[1] or prepare_features().
        test_size:   Fraction of samples held out for evaluation (default 0.3).
        model_dir:   Directory where model pickles are saved.

    Returns:
        Dict of model_name → metric_dict, e.g.::

            {
              "estrus":       {"precision": 0.81, "recall": 0.74, "f1": 0.77, ...},
              "health_score": {"r2": 0.72, "mae": 4.1},
            }
    """
    _require_ml()
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    X, labels = _prepare_training_data(df_features)
    log.info("Training on %d samples, %d features", len(X), X.shape[1])

    configs: dict[str, Any] = {
        "estrus":       RandomForestClassifier(n_estimators=80, class_weight="balanced", random_state=42),
        "fever":        RandomForestClassifier(n_estimators=80, class_weight="balanced", random_state=42),
        "lameness":     RandomForestClassifier(n_estimators=80, class_weight="balanced", random_state=42),
        "mastitis":     LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42),
        "health_score": LinearRegression(),
    }

    results: dict[str, dict[str, float]] = {}

    for name, model in configs.items():
        y = labels.get(name)
        if y is None:
            log.warning("No label column for '%s' — skipping", name)
            continue
        if len(y) < 10:
            log.warning("Too few samples for '%s' — skipping", name)
            continue

        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        try:
            model.fit(X_tr, y_tr)
        except Exception as exc:
            log.error("Training '%s' failed: %s", name, exc)
            continue

        joblib.dump(model, model_dir / f"{name}_model.pkl")
        y_pred = model.predict(X_te)

        if name == "health_score":
            results[name] = {
                "r2":  round(float(r2_score(y_te, y_pred)), 3),
                "mae": round(float(mean_absolute_error(y_te, y_pred)), 2),
            }
        else:
            results[name] = {
                "precision":        round(float(precision_score(y_te, y_pred, zero_division=0)), 3),
                "recall":           round(float(recall_score(y_te, y_pred, zero_division=0)), 3),
                "f1":               round(float(f1_score(y_te, y_pred, zero_division=0)), 3),
                "support_positive": int(np.sum(y_te)),
                "support_total":    int(len(y_te)),
            }
        log.info("Trained %s: %s", name, results[name])

    # Persist the feature column order so inference loads with the same layout
    joblib.dump(FEATURE_COLUMNS, model_dir / "feature_columns.pkl")
    return results


# ===========================================================================
# Inference  (async — requires DB session)
# ===========================================================================

async def classify_animal_health(
    session: Any,           # AsyncSession — typed as Any to avoid circular import
    animal_id: uuid.UUID,
    window_days: int = 7,
) -> dict[str, Any]:
    """
    Query recent HealthRecords, extract features, run all trained models.

    Returns::

        {
          "animal_id": str,
          "estrus_prob": float,
          "fever_prob": float,
          "lameness_prob": float,
          "mastitis_risk": float,
          "health_score": int,
          "confidence": float,
          "confidence_factors": { model_agreement, feature_completeness, history_days },
          "classified_at": ISO-8601 str,
        }

    If models are not trained yet, returns {"error": "Models not trained..."}.
    """
    from sqlalchemy import select
    from models.database import HealthRecord

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    result = await session.execute(
        select(HealthRecord)
        .where(HealthRecord.animal_id == animal_id, HealthRecord.record_date >= cutoff)
        .order_by(HealthRecord.record_date.asc())
    )
    records = list(result.scalars().all())

    record_dicts = [
        {
            "temperature_celsius": r.temperature_celsius,
            "behavior_score":      r.behavior_score,
            "milk_yield_liters":   r.milk_yield_liters,
            "record_date":         r.record_date.isoformat() if r.record_date else None,
        }
        for r in records
    ]

    features = extract_features(record_dicts, window_days=window_days)
    models = _load_models()

    if not models:
        return {
            "animal_id": str(animal_id),
            "error": "Models not trained. Run: python scripts/train_pashu_ai.py --data-path=<csv>",
        }

    X = [features.get(col, 0.0) for col in FEATURE_COLUMNS]
    preds: dict[str, Any] = {}

    for name in ("estrus", "fever", "lameness", "mastitis"):
        m = models.get(name)
        if m is not None:
            try:
                proba = m.predict_proba([X])[0]
                preds[f"{name}_prob"] = round(float(proba[1]) if len(proba) > 1 else float(proba[0]), 3)
            except Exception:
                preds[f"{name}_prob"] = 0.0
        else:
            preds[f"{name}_prob"] = 0.0

    hs_model = models.get("health_score")
    if hs_model is not None:
        try:
            raw = float(hs_model.predict([X])[0])
            preds["health_score"] = int(max(0, min(100, round(raw))))
        except Exception:
            preds["health_score"] = 50
    else:
        preds["health_score"] = 50

    # Rename mastitis key to match spec
    preds["mastitis_risk"] = preds.pop("mastitis_prob", 0.0)

    conf = _compute_confidence(features, preds)
    return {
        "animal_id": str(animal_id),
        "window_days": window_days,
        "record_count": len(records),
        **preds,
        **conf,
        "classified_at": datetime.now(timezone.utc).isoformat(),
    }


def get_recommendation(animal_id: str | uuid.UUID, classification: dict[str, Any]) -> str:
    """
    Convert a classification result into a plain-English action for the farm dashboard.
    Returns the single highest-priority recommendation.
    """
    estrus_prob  = classification.get("estrus_prob",  0.0)
    fever_prob   = classification.get("fever_prob",   0.0)
    lameness_prob= classification.get("lameness_prob",0.0)
    mastitis_risk= classification.get("mastitis_risk",0.0)
    health_score = classification.get("health_score", 100)
    n_records    = classification.get("record_count", 0)

    # Priority order: fever → mastitis → health_score → lameness → estrus
    if fever_prob > 0.7:
        days = "2+ days" if n_records >= 2 else "recent observation"
        return f"⚠ Vet visit recommended — fever trend detected ({days}). Check temperature and isolate if above 39.5°C."

    if health_score < 40:
        return f"🔴 Animal at risk (health score {health_score}/100) — immediate monitoring and vet consultation advised."

    if mastitis_risk > 0.65:
        return "⚠ Mastitis risk elevated — inspect udder, check for swelling/heat, consider milk culture test."

    if lameness_prob > 0.65:
        return "⚠ Lameness suspected — observe gait, inspect hooves, consider foot bath treatment."

    if estrus_prob > 0.75:
        return "🐄 Breeding window open — estrus detected. Optimal insemination window: next 12–24 hours."

    if health_score >= 75:
        return "✓ Animal health normal — continue routine monitoring."

    return f"ℹ Monitor animal — health score {health_score}/100. No immediate intervention required."


# ===========================================================================
# Synthetic data generator  (used by tests + training script)
# ===========================================================================

def generate_synthetic_training_data(
    n_animals: int = 20,
    n_days: int = 56,
    random_seed: int = 42,
) -> "pd.DataFrame":
    """
    Generate a synthetic training dataset mimicking Fanmilk Danone farm data.

    Each animal has:
      - Individual baseline temperature (38.0–38.8°C) and yield (8–16 L)
      - Estrus cycle every 21 days (2-day window): temp dip + yield drop + restlessness
      - Random fever events (~7% daily probability), lasting 2-4 days
      - Lameness events (~3% daily probability), behaviour lethargic without high fever

    Returns a DataFrame with columns matching the expected CSV format.
    """
    _require_ml()
    import random
    rng = random.Random(random_seed)

    rows = []
    base_date = datetime(2024, 1, 15)

    for i in range(n_animals):
        animal_id    = f"cow-{i + 1:03d}"
        base_temp    = rng.uniform(38.0, 38.8)
        base_yield   = rng.uniform(8.0, 16.0)
        fever_active = 0     # remaining fever days
        lameness_active = 0  # remaining lameness days

        for day in range(n_days):
            date = base_date + timedelta(days=day)

            # Estrus: 2-day window every 21 days
            cycle_day = day % 21
            is_estrus = cycle_day in (0, 1)

            # Fever onset
            if fever_active <= 0:
                fever_active = rng.randint(2, 4) if rng.random() < 0.07 else 0
            if fever_active > 0:
                fever_active -= 1
            is_fever = fever_active > 0

            # Lameness onset (independent of fever)
            if lameness_active <= 0:
                lameness_active = rng.randint(2, 5) if rng.random() < 0.03 else 0
            if lameness_active > 0:
                lameness_active -= 1
            is_lame = lameness_active > 0 and not is_fever  # distinguish from fever

            # Temperature
            temp = base_temp + rng.gauss(0, 0.18)
            if is_fever:
                temp += rng.uniform(0.9, 2.1)
            if is_estrus:
                temp -= rng.uniform(0.15, 0.45)  # slight dip
            temp = round(max(37.0, min(42.5, temp)), 1)

            # Milk yield
            yield_l = max(0.5, base_yield + rng.gauss(0, 0.8))
            if is_fever:
                yield_l *= rng.uniform(0.55, 0.75)
            if is_estrus:
                yield_l *= rng.uniform(0.82, 0.92)
            if is_lame:
                yield_l *= rng.uniform(0.88, 0.97)
            yield_l = round(yield_l, 1)

            # Behaviour
            if is_fever and temp > 39.5:
                behavior = "lethargic"
            elif is_fever or is_estrus:
                behavior = "depressed"
            elif is_lame:
                behavior = rng.choice(["lethargic", "depressed"])
            else:
                behavior = "normal"

            treatment = "antibiotic_injection" if is_fever and temp > 39.5 else "none"

            rows.append({
                "animal_id":          animal_id,
                "date":               date.strftime("%Y-%m-%d"),
                "temperature_c":      temp,
                "behavior":           behavior,
                "milk_yield_liters":  yield_l,
                "observed_estrus":    is_estrus,
                "observed_fever":     is_fever,
                "observed_lameness":  is_lame,
                "treatment_given":    treatment,
            })

    return pd.DataFrame(rows)


# ===========================================================================
# Private helpers
# ===========================================================================

def _feature_engineer_dataframe(
    df: "pd.DataFrame",
    window_days: int = 7,
) -> "pd.DataFrame":
    """Slide a window over each animal's timeline to produce labelled training samples."""
    samples: list[dict] = []

    for animal_id, group in df.groupby("animal_id"):
        group = group.sort_values("date").reset_index(drop=True)

        for i in range(window_days, len(group)):
            window_rows = group.iloc[max(0, i - window_days):i]
            current_row = group.iloc[i]

            window_records = [
                {
                    "temperature_celsius": row.get("temperature_c"),
                    "behavior_score": _BEHAVIOR_SCORE.get(
                        str(row.get("behavior", "")).lower(), None
                    ),
                    "milk_yield_liters": row.get("milk_yield_liters"),
                    "record_date": row["date"].isoformat()
                        if hasattr(row["date"], "isoformat") else str(row["date"]),
                }
                for _, row in window_rows.iterrows()
            ]

            feats = extract_features(window_records, window_days=window_days)

            # Labels from current (next) day
            feats["label_estrus"]   = int(bool(current_row.get("observed_estrus",  False)))
            feats["label_fever"]    = int(bool(current_row.get("observed_fever",   False)))
            feats["label_lameness"] = int(bool(current_row.get("observed_lameness", False)))

            # Mastitis: derived if not explicitly labelled
            if "observed_mastitis" in current_row:
                feats["label_mastitis"] = int(bool(current_row["observed_mastitis"]))
            else:
                feats["label_mastitis"] = int(
                    feats["yield_slope"] < -0.5 and feats["temp_mean"] > 38.5
                )

            # Composite health score (0-100): temp + yield + behaviour
            t = current_row.get("temperature_c", 38.5)
            y = current_row.get("milk_yield_liters", 10.0)
            bscore = _BEHAVIOR_SCORE.get(str(current_row.get("behavior", "")).lower(), 1)
            temp_s  = max(0.0, 100.0 - abs(t - 38.5) * 28.0)
            yield_s = min(100.0, max(0.0, (float(y) / 15.0) * 100.0))
            beh_s   = {1: 100, 2: 60, 3: 30, 4: 10, 5: 0}.get(bscore, 50)
            feats["label_health_score"] = round(temp_s * 0.4 + yield_s * 0.4 + beh_s * 0.2, 1)

            feats["animal_id"] = animal_id
            samples.append(feats)

    return pd.DataFrame(samples) if samples else pd.DataFrame()


def _prepare_training_data(
    df: "pd.DataFrame",
) -> tuple["np.ndarray", dict[str, "np.ndarray"]]:
    """Extract X matrix and label arrays from the feature DataFrame."""
    available = [c for c in FEATURE_COLUMNS if c in df.columns]
    df_clean = df.dropna(subset=available)

    if df_clean.empty:
        raise ValueError("No valid training samples after dropping NaN rows")

    X = df_clean[available].values.astype(float)
    labels = {}
    for name, col in LABEL_COLUMNS.items():
        if col in df_clean.columns:
            labels[name] = df_clean[col].values

    return X, labels


def _load_models(model_dir: Path = MODEL_DIR) -> dict[str, Any]:
    """Load all available trained models from disk. Returns {} if none found."""
    if not _ML_AVAILABLE:
        return {}
    models: dict[str, Any] = {}
    for name in ("estrus", "fever", "lameness", "mastitis", "health_score"):
        path = model_dir / f"{name}_model.pkl"
        if path.exists():
            try:
                models[name] = joblib.load(path)
            except Exception as exc:
                log.warning("Could not load model %s: %s", name, exc)
    return models


def _compute_confidence(
    features: dict[str, float],
    preds: dict[str, Any],
) -> dict[str, Any]:
    completeness = features.get("feature_completeness", 0.5)
    n = features.get("days_in_window", 0.0)
    data_conf = min(1.0, completeness * (float(n) / 7.0))

    probs = [v for k, v in preds.items() if k.endswith("_prob") or k == "mastitis_risk"]
    decisiveness = sum(abs(p - 0.5) for p in probs) / max(len(probs), 1) if probs else 0.0
    model_agreement = decisiveness > 0.2

    overall = round(0.6 * data_conf + 0.4 * min(decisiveness * 2.0, 1.0), 3)
    return {
        "confidence": overall,
        "confidence_factors": {
            "model_agreement":       model_agreement,
            "feature_completeness":  round(completeness, 3),
            "history_days":          int(n),
        },
    }


def _zero_features() -> dict[str, float]:
    return {col: 0.0 for col in FEATURE_COLUMNS} | {"feature_completeness": 0.0}


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5


def _linear_slope(values: list[float]) -> float:
    """Return OLS slope of a sequence (no pandas/numpy required)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return round(num / den, 4) if den else 0.0


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx  = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy  = sum((y - my) ** 2 for y in ys) ** 0.5
    return round(num / (dx * dy), 4) if (dx * dy) else 0.0


def _require_ml() -> None:
    if not _ML_AVAILABLE:
        raise ImportError(
            f"ML dependencies not installed ({_ML_IMPORT_ERR}). "
            "Run: pip install scikit-learn pandas numpy joblib"
        )
