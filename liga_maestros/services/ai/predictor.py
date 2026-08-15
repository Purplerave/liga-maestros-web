"""AI prediction motor service.

Wraps the quiniela ML motor (MOTOR_QUINIELA_MAESTRO) to generate
AI predictions that compete with human users in the Liga de Maestros.

The motor runs as a background task and caches results in memory.
Predictions are refreshed when new jornada data arrives.
"""

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MOTOR_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent / "QUINIELA_MOTOR"
if str(MOTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTOR_ROOT))

PREDICTION_CACHE_TTL = 3600

_cache_lock = threading.Lock()
_prediction_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_last_prediction_time: dict[str, float] = {}


def motor_enabled():
    return os.getenv("MOTOR_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")


def motor_available():
    """True si el paquete del motor existe y se puede importar.

    `MOTOR_QUINIELA_MAESTRO` vive en el repositorio hermano `QUINIELA_MOTOR`,
    que no se despliega con la web. Cuando falta, cada petición a
    /api/ai/predictions lanzaba un ImportError capturado por el `except`
    genérico y escribía un WARNING, mientras /api/ai/status seguía diciendo
    `enabled: true`. Comprobarlo antes evita el ruido y permite informar del
    estado real.
    """
    if not motor_enabled():
        return False
    from importlib.util import find_spec

    try:
        return find_spec("MOTOR_QUINIELA_MAESTRO") is not None
    except (ImportError, ValueError):
        return False


def _load_history():
    from MOTOR_QUINIELA_MAESTRO import load_raw_history

    sanitized = MOTOR_ROOT / "salida" / "datos_limpios" / "historico_saneado.csv"
    if sanitized.is_file():
        return load_raw_history("saneado")
    raw_base = MOTOR_ROOT / "DATOS" / "historico_raw"
    if raw_base.is_dir():
        return load_raw_history("original")
    return None


def _load_jornada_data(jornada):
    for candidate in [
        MOTOR_ROOT / "DATOS" / f"QUINIELA15_J{jornada}.json",
        MOTOR_ROOT / "salida" / f"QUINIELA15_J{jornada}.json",
    ]:
        if candidate.is_file():
            with open(candidate, encoding="utf-8") as fh:
                return json.load(fh)
    return None


def _compute_predictions(jornada, partidos, history):
    from MOTOR_QUINIELA_MAESTRO import (
        build_hgb_model,
        build_logit_model,
        compute_features_for_upcoming,
    )

    features = compute_features_for_upcoming(partidos, history, datetime.now().date())
    if features.empty:
        return []

    logit = build_logit_model()
    hgb = build_hgb_model()

    feature_cols = [
        c
        for c in features.columns
        if c not in ("date", "home", "away", "division", "division_code", "season", "source_file", "result")
    ]
    X = features[feature_cols].fillna(0).values

    logit_probs = logit.predict_proba(X)
    hgb_probs = hgb.predict_proba(X)

    results = []
    for i, row in features.iterrows():
        blended = 0.4 * logit_probs[i] + 0.6 * hgb_probs[i]
        sign = "1" if blended[0] > blended[2] else ("2" if blended[2] > blended[0] else "X")
        confidence = float(max(blended))

        results.append(
            {
                "partido_id": int(row.get("partido_id", i + 1)),
                "signo": sign,
                "confidence": round(confidence, 4),
                "prob_1": round(float(blended[0]), 4),
                "prob_x": round(float(blended[1]), 4),
                "prob_2": round(float(blended[2]), 4),
                "source": "motor_v3",
            }
        )

    return results


def generate_predictions(jornada):
    """Generate AI predictions for a jornada using the ML motor.

    Returns a list of prediction dicts or an empty list on failure.
    Never raises.
    """
    if not motor_enabled():
        return []
    if not motor_available():
        logger.debug(
            "AI predictor: MOTOR_QUINIELA_MAESTRO no disponible en %s; se omite la generacion.",
            MOTOR_ROOT,
        )
        return []

    try:
        history = _load_history()
        if history is None or history.empty:
            logger.warning("AI predictor: no historical data available")
            return []

        jornada_data = _load_jornada_data(jornada)
        if not jornada_data:
            logger.warning("AI predictor: no jornada data for %s", jornada)
            return []

        partidos = jornada_data.get("partidos", [])
        if not partidos:
            return []

        predictions = _compute_predictions(jornada, partidos, history)
        logger.info(
            "AI predictor: generated %d predictions for jornada %s",
            len(predictions),
            jornada,
        )
        return predictions
    except Exception as exc:
        logger.warning("AI predictor: failed for jornada %s (%s)", jornada, exc)
        return []


def get_cached_predictions(jornada, force_refresh=False):
    """Get cached predictions or generate new ones."""
    key = str(jornada)
    now = time.time()

    with _cache_lock:
        if not force_refresh and key in _prediction_cache:
            cached_time, cached_data = _prediction_cache[key]
            if now - cached_time < PREDICTION_CACHE_TTL:
                return cached_data

    predictions = generate_predictions(jornada)

    with _cache_lock:
        _prediction_cache[key] = (now, predictions)
        _last_prediction_time[key] = now

    return predictions


def refresh_predictions_for_active_jornada(jornada):
    """Force refresh predictions for the active jornada."""
    return get_cached_predictions(jornada, force_refresh=True)


def get_prediction_stats():
    """Return prediction engine status and stats."""
    with _cache_lock:
        cached_keys = list(_prediction_cache.keys())
        last_refresh = {k: _last_prediction_time.get(k, 0) for k in cached_keys}

    available = motor_available()
    return {
        "enabled": motor_enabled(),
        "available": available,
        "reason": None if available else "motor_no_instalado",
        "motor_path": str(MOTOR_ROOT),
        "cached_jornadas": cached_keys,
        "last_refresh": last_refresh,
        "cache_ttl_seconds": PREDICTION_CACHE_TTL,
    }
