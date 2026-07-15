"""Optional in-process live collector for single-service deployments.

Render persistent disks are attached to one service. For the beta deploy we run
the collector inside the web service so live updates and the web app use the
same SQLite database and JSON cache.
"""
import os
import threading
import time


_collector_started = False
_collector_lock = threading.Lock()


def _truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def start_web_collector(app):
    """Start the background collector when WEB_COLLECTOR_ENABLED=1."""
    global _collector_started
    if not _truthy(os.getenv("WEB_COLLECTOR_ENABLED", "0")):
        return

    with _collector_lock:
        if _collector_started:
            return
        _collector_started = True

    interval = int(os.getenv("WEB_COLLECTOR_INTERVAL_SECONDS", "60"))
    highlightly_interval = int(os.getenv("WEB_COLLECTOR_HIGHLIGHTLY_INTERVAL_SECONDS", "60"))
    q15_enabled = not _truthy(os.getenv("WEB_COLLECTOR_DISABLE_Q15", "0"))

    def _loop():
        from LIVE_COLLECTOR import log_line, next_sleep_seconds, run_once, write_health

        log_line("web_collector=start")
        while True:
            try:
                _, window = run_once(
                    force=False,
                    q15=q15_enabled,
                    highlightly_interval=highlightly_interval,
                )
                sleep_seconds = next_sleep_seconds(window, interval)
            except Exception as exc:
                try:
                    log_line(f"web_collector_error={exc}")
                    write_health("error", error=exc)
                except Exception:
                    pass
                sleep_seconds = max(60, min(interval or 60, 300))
            time.sleep(max(30, int(sleep_seconds)))

    thread = threading.Thread(target=_loop, name="liga-web-collector", daemon=True)
    thread.start()
    app.extensions["web_collector_thread"] = thread
