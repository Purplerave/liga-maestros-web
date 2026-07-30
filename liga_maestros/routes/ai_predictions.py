"""AI predictions route: ML motor predictions as an AI Maestro."""

from flask import Blueprint, jsonify, request, session

from ..db.connection import get_db
from ..services.ai import get_cached_predictions, get_prediction_stats, refresh_predictions_for_active_jornada
from ..services.highlightly import Q15_EXPECTED_MATCHES

bp = Blueprint("ai_predictions", __name__)


@bp.route("/api/ai/predictions")
def get_ai_predictions():
    """Return ML motor predictions for the active jornada."""
    jornada = request.args.get("j", "")
    if not jornada.isdigit():
        return jsonify({"status": "error", "message": "Jornada invalida"}), 400

    force = request.args.get("force", "0").strip().lower() in ("1", "true", "yes", "on")
    predictions = get_cached_predictions(int(jornada), force_refresh=force)

    return jsonify(
        {
            "status": "ok",
            "jornada": int(jornada),
            "predictions": predictions,
            "count": len(predictions),
            "source": "motor_v3",
        }
    )


@bp.route("/api/ai/predictions/refresh", methods=["POST"])
def refresh_ai_predictions():
    """Force refresh AI predictions for the active jornada."""
    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "Debes iniciar sesion"}), 401

    jornada = request.args.get("j", "")
    if not jornada.isdigit():
        return jsonify({"status": "error", "message": "Jornada invalida"}), 400

    predictions = refresh_predictions_for_active_jornada(int(jornada))

    return jsonify(
        {
            "status": "ok",
            "jornada": int(jornada),
            "predictions": predictions,
            "count": len(predictions),
            "source": "motor_v3",
        }
    )


@bp.route("/api/ai/status")
def ai_status():
    """Return the AI prediction engine status."""
    stats = get_prediction_stats()
    return jsonify({"status": "ok", "ai": stats})