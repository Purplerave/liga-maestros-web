"""Gunicorn production config for Liga de Maestros."""

import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
workers = int(os.getenv("GUNICORN_WORKERS", min(4, (multiprocessing.cpu_count() or 2) * 2 + 1)))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
worker_class = "gthread"
preload_app = True
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")

# Security / forward secrecy
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1,::1")
secure_scheme_headers = {"X-FORWARDED-PROTO": "https"}
