"""Prometheus metrics middleware."""

import time
from collections import Counter

from flask import g, request

# In-memory counters (per-process)
REQUEST_COUNTER = Counter()
REQUEST_DURATION = Counter()  # sum of durations, count gives avg
HIGHLIGHTLY_USAGE = {"calls": 0, "limit": 7500, "remaining": 7500}


def init_metrics(app):
    @app.before_request
    def _metrics_before():
        g.metrics_start = time.perf_counter()

    @app.after_request
    def _metrics_after(response):
        try:
            route = request.path
            # Normalize dynamic paths: /api/liga/data?j=1 -> /api/liga/data
            if route.startswith("/static/"):
                route = "/static/*"
            REQUEST_COUNTER[(request.method, route, str(response.status_code))] += 1
            if hasattr(g, "metrics_start"):
                dur = time.perf_counter() - g.metrics_start
                REQUEST_DURATION[(request.method, route)] += dur
        except Exception:
            pass
        return response

    @app.route("/metrics")
    def metrics():
        from flask import Response

        lines = ["# HELP http_requests_total Total HTTP requests", "# TYPE http_requests_total counter"]
        for (method, path, code), count in REQUEST_COUNTER.items():
            lines.append(f'http_requests_total{{method="{method}",path="{path}",code="{code}"}} {count}')
        lines.append("# HELP http_request_duration_seconds_sum Sum of request durations")
        lines.append("# TYPE http_request_duration_seconds_sum counter")
        for (method, path), total in REQUEST_DURATION.items():
            lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total:.6f}')
        # Highlightly budget
        try:
            from ..services.highlightly import get_highlightly_usage

            usage = get_highlightly_usage()
            lines.append("# HELP highlightly_calls_used Highlightly API calls used today")
            lines.append("# TYPE highlightly_calls_used gauge")
            lines.append(f"highlightly_calls_used {int(usage.get('calls', 0))}")
            lines.append(f"highlightly_calls_limit {int(usage.get('limit', 7500))}")
            lines.append(f"highlightly_calls_remaining {int(usage.get('usable_remaining', usage.get('limit', 7500)))}")
        except Exception:
            pass
        return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")
