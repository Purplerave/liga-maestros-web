"""Prometheus metrics middleware — bounded cardinality, protected endpoint."""

import time
from collections import Counter, defaultdict, deque

from flask import g, request

# In-memory counters (per-process) — bounded cardinality
REQUEST_COUNTER: Counter[tuple[str, str, str]] = Counter()
REQUEST_DURATION: Counter[tuple[str, str]] = Counter()  # sum of durations
REQUEST_DURATION_COUNT: Counter[tuple[str, str]] = Counter()
REQUEST_LATENCIES: dict[tuple[str, str], deque[float]] = defaultdict(lambda: deque(maxlen=100))
HIGHLIGHTLY_USAGE = {"calls": 0, "limit": 7500, "remaining": 7500}

_MAX_CARDINALITY = 500  # prevent unbounded growth from arbitrary paths


def _percentile(samples: list[float], p: float) -> float:
    """Calcula el percentil p (0..1) sobre una lista de muestras de latencia."""
    if not samples:
        return 0.0
    sorted_s = sorted(samples)
    idx = int(len(sorted_s) * p)
    idx = min(idx, len(sorted_s) - 1)
    return sorted_s[idx]


def _route_label() -> str:
    """Return a low-cardinality route label.

    Uses the Flask URL rule when available (e.g. "/api/liga/data") instead of
    the raw path (which an attacker could enumerate infinitely). Unmatched
    routes collapse to "__unmatched__" and static files to "/static/*".
    """
    # Flask sets url_rule only after routing succeeds
    rule = getattr(request, "url_rule", None)
    if rule is not None:
        return str(rule.rule)
    path = request.path or "__unmatched__"
    if path.startswith("/static/"):
        return "/static/*"
    # Collapse any path that didn't match a rule to a single bucket
    return "__unmatched__"


def init_metrics(app):
    @app.before_request
    def _metrics_before():
        g.metrics_start = time.perf_counter()

    @app.after_request
    def _metrics_after(response):
        try:
            route = _route_label()
            # Bounded cardinality guard
            if (
                len(REQUEST_COUNTER) < _MAX_CARDINALITY
                or (request.method, route, str(response.status_code)) in REQUEST_COUNTER
            ):
                REQUEST_COUNTER[(request.method, route, str(response.status_code))] += 1
            if hasattr(g, "metrics_start"):
                dur = time.perf_counter() - g.metrics_start
                key = (request.method, route)
                if len(REQUEST_DURATION) < _MAX_CARDINALITY or key in REQUEST_DURATION:
                    REQUEST_DURATION[key] += dur
                    REQUEST_DURATION_COUNT[key] += 1
                    REQUEST_LATENCIES[key].append(dur)
        except Exception:
            pass
        return response

    @app.route("/metrics")
    def metrics():
        from flask import Response

        # Protect metrics: only admin or service token may read it.
        # This prevents enumeration / cardinality probing and budget disclosure.
        from ..middleware.authz import is_admin_or_service_request

        if not is_admin_or_service_request():
            return Response("forbidden\n", status=403, mimetype="text/plain")

        lines = ["# HELP http_requests_total Total HTTP requests", "# TYPE http_requests_total counter"]
        for (method, path, code), count in REQUEST_COUNTER.items():
            # Escape label values minimally
            safe_path = path.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'http_requests_total{{method="{method}",path="{safe_path}",code="{code}"}} {count}')
        lines.append("# HELP http_request_duration_seconds_sum Sum of request durations")
        lines.append("# TYPE http_request_duration_seconds_sum counter")
        for (method, path), total in REQUEST_DURATION.items():
            safe_path = path.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{safe_path}"}} {total:.6f}')
        lines.append("# HELP http_request_duration_seconds_count Number of requests")
        lines.append("# TYPE http_request_duration_seconds_count counter")
        for (method, path), cnt in REQUEST_DURATION_COUNT.items():
            safe_path = path.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'http_request_duration_seconds_count{{method="{method}",path="{safe_path}"}} {cnt}')
        lines.append("# HELP http_request_duration_seconds_percentiles Latency percentiles in seconds")
        lines.append("# TYPE http_request_duration_seconds_percentiles gauge")
        for (method, path), samples in REQUEST_LATENCIES.items():
            if not samples:
                continue
            safe_path = path.replace("\\", "\\\\").replace('"', '\\"')
            sample_list = list(samples)
            p50 = _percentile(sample_list, 0.50)
            p90 = _percentile(sample_list, 0.90)
            p95 = _percentile(sample_list, 0.95)
            lines.append(f'http_request_duration_seconds_p50{{method="{method}",path="{safe_path}"}} {p50:.6f}')
            lines.append(f'http_request_duration_seconds_p90{{method="{method}",path="{safe_path}"}} {p90:.6f}')
            lines.append(f'http_request_duration_seconds_p95{{method="{method}",path="{safe_path}"}} {p95:.6f}')
        # Highlightly budget & circuit breaker — only exposed via authenticated metrics
        try:
            from ..services.highlightly import get_highlightly_circuit, get_highlightly_usage

            usage = get_highlightly_usage()
            circuit = get_highlightly_circuit()
            lines.append("# HELP highlightly_calls_used Highlightly API calls used today")
            lines.append("# TYPE highlightly_calls_used gauge")
            lines.append(f"highlightly_calls_used {int(usage.get('calls', 0))}")
            lines.append(f"highlightly_calls_limit {int(usage.get('limit', 7500))}")
            usable = int(usage.get("usable_remaining", usage.get("limit", 7500)))
            lines.append(f"highlightly_calls_remaining {usable}")
            lines.append(f"highlightly_quota_warning {1 if usable < 500 else 0}")

            lines.append("# HELP highlightly_circuit_open Highlightly circuit breaker status (1 open, 0 closed)")
            lines.append("# TYPE highlightly_circuit_open gauge")
            lines.append(f"highlightly_circuit_open {1 if circuit.get('open') else 0}")
            lines.append(f"highlightly_circuit_failures {int(circuit.get('failures', 0))}")
        except Exception:
            pass
        return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")
