"""Benchmark continuo IA vs humanos — precisión, coste, latencia por jornada."""


def compute_benchmark(ranking, predictions, costs=None, latencies=None):
    """ranking: {id: {jornada, total}}, predictions: {id: signos}, costs/latencies opcionales."""
    costs = costs or {}
    latencies = latencies or {}
    rows = []
    for uid, vals in ranking.items():
        pts = int(vals.get("jornada_live", vals.get("jornada", 0)) or 0)
        rows.append(
            {
                "id": uid,
                "aciertos": pts,
                "precision": round(pts / 15 * 100, 1) if pts else 0,
                "cost_usd": round(float(costs.get(uid, 0.002)), 4),
                "latency_ms": int(latencies.get(uid, 350)),
            }
        )
    rows.sort(key=lambda r: (r["aciertos"], -r["cost_usd"]), reverse=True)
    return rows
