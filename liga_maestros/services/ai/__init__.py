"""Capa de IA opcional (tier gratuito).

Todo lo de este paquete es best-effort: si no hay API key, si se agota la cuota
o si el proveedor falla, las funciones devuelven un valor vacio y la web sigue
funcionando exactamente igual. Nunca lanzan excepciones hacia arriba.

El «consejo IA» (``predictor`` + ``GET /api/ai/predictions``) se retiro con la
pagina unica: la quiniela no muestra pronosticos consejeros, solo las columnas
reales de los participantes.
"""
