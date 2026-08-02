"""Capa de IA opcional (tier gratuito).

Todo lo de este paquete es best-effort: si no hay API key, si se agota la cuota
o si el proveedor falla, las funciones devuelven un valor vacio y la web sigue
funcionando exactamente igual. Nunca lanzan excepciones hacia arriba.
"""

from .predictor import (
    get_cached_predictions as get_cached_predictions,
)
from .predictor import (
    get_prediction_stats as get_prediction_stats,
)
from .predictor import (
    motor_enabled as motor_enabled,
)
from .predictor import (
    refresh_predictions_for_active_jornada as refresh_predictions_for_active_jornada,
)
