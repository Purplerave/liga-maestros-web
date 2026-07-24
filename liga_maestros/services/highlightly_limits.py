"""Highlightly circuit breaker and daily API quota accounting."""

import os
import threading
import time
from datetime import datetime

import config

from ..db.connection import get_db
from ..middleware.json_lock import write_json_locked
from ..utils import safe_read_json
from .ticket import today_madrid


HIGHLIGHTLY_DAILY_CALL_LIMIT = int(os.getenv("HIGHLIGHTLY_DAILY_CALL_LIMIT", "7500"))
HIGHLIGHTLY_DAILY_CALL_RESERVE = int(os.getenv("HIGHLIGHTLY_DAILY_CALL_RESERVE", "250"))
HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT = int(os.getenv("HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT", "3"))
HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS = int(os.getenv("HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS", "600"))
HIGHLIGHTLY_CIRCUIT_MAX_COOLDOWN_SECONDS = int(os.getenv("HIGHLIGHTLY_CIRCUIT_MAX_COOLDOWN_SECONDS", "3600"))

_circuit_lock = threading.RLock()


def get_highlightly_circuit():
    path = os.path.join(config.DATA_DIR, "HIGHLIGHTLY_CIRCUIT.json")
    with _circuit_lock:
        state = safe_read_json(path, {})
        until = float(state.get("open_until") or 0)
        return {
            "path": path,
            "failures": int(state.get("failures") or 0),
            "reopen_failures": int(state.get("reopen_failures") or 0),
            "cooldown_seconds": int(
                state.get("cooldown_seconds") or HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS
            ),
            "open_until": until,
            "open": until > time.time(),
            "last_error": state.get("last_error", ""),
            "last_success_at": state.get("last_success_at", ""),
            "calls_since_last_success": int(state.get("calls_since_last_success") or 0),
        }


def record_highlightly_success():
    path = os.path.join(config.DATA_DIR, "HIGHLIGHTLY_CIRCUIT.json")
    now = datetime.now().isoformat(timespec="seconds")
    with _circuit_lock:
        write_json_locked(path, {
            "failures": 0,
            "reopen_failures": 0,
            "cooldown_seconds": HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS,
            "open_until": 0,
            "last_error": "",
            "last_success_at": now,
            "calls_since_last_success": 0,
            "updated_at": now,
        })


def record_highlightly_failure(exc):
    with _circuit_lock:
        circuit = get_highlightly_circuit()
        failures = int(circuit.get("failures") or 0) + 1
        reopen_failures = int(circuit.get("reopen_failures") or 0)
        if failures >= HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT:
            reopen_failures += 1

        base_cooldown = int(
            circuit.get("cooldown_seconds") or HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS
        )
        cooldown = base_cooldown
        if reopen_failures >= 3:
            cooldown = min(
                max(base_cooldown * 2, HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS),
                HIGHLIGHTLY_CIRCUIT_MAX_COOLDOWN_SECONDS,
            )
        open_until = (
            time.time() + cooldown
            if failures >= HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT
            else 0
        )
        now = datetime.now().isoformat(timespec="seconds")
        write_json_locked(circuit["path"], {
            "failures": failures,
            "reopen_failures": reopen_failures,
            "cooldown_seconds": cooldown,
            "open_until": open_until,
            "last_error": str(exc),
            "last_success_at": circuit.get("last_success_at", ""),
            "calls_since_last_success": int(circuit.get("calls_since_last_success") or 0) + 1,
            "updated_at": now,
        })


def ensure_api_usage_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_usage_daily (
            service TEXT NOT NULL,
            date TEXT NOT NULL,
            calls INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (service, date)
        )
    """)


def highlightly_usage_payload(date_text, calls):
    calls = int(calls or 0)
    remaining = max(0, HIGHLIGHTLY_DAILY_CALL_LIMIT - calls)
    return {
        "date": date_text,
        "calls": calls,
        "limit": HIGHLIGHTLY_DAILY_CALL_LIMIT,
        "reserve": HIGHLIGHTLY_DAILY_CALL_RESERVE,
        "remaining": remaining,
        "usable_remaining": max(0, remaining - HIGHLIGHTLY_DAILY_CALL_RESERVE),
    }


def mirror_highlightly_usage_json(data):
    path = os.path.join(config.DATA_DIR, "API_USAGE_HIGHLIGHTLY.json")
    try:
        write_json_locked(path, data)
    except Exception:
        pass


def get_highlightly_usage():
    today = today_madrid()
    conn = get_db()
    try:
        ensure_api_usage_table(conn)
        row = conn.execute(
            "SELECT calls FROM api_usage_daily WHERE service = ? AND date = ?",
            ("highlightly", today),
        ).fetchone()
        if not row:
            legacy = safe_read_json(
                os.path.join(config.DATA_DIR, "API_USAGE_HIGHLIGHTLY.json"),
                {},
            )
            calls = int(legacy.get("calls") or 0) if legacy.get("date") == today else 0
            conn.execute("""
                INSERT OR IGNORE INTO api_usage_daily (service, date, calls, updated_at)
                VALUES (?, ?, ?, ?)
            """, ("highlightly", today, calls, datetime.now().isoformat(timespec="seconds")))
            conn.commit()
        else:
            calls = int(row["calls"] or 0)
        data = highlightly_usage_payload(today, calls)
        mirror_highlightly_usage_json(data)
        return data
    finally:
        conn.close()


def reserve_highlightly_calls(count=1):
    count = max(1, int(count or 1))
    today = today_madrid()
    conn = get_db()
    try:
        ensure_api_usage_table(conn)
        conn.execute("BEGIN IMMEDIATE")
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute("""
            INSERT OR IGNORE INTO api_usage_daily (service, date, calls, updated_at)
            VALUES (?, ?, 0, ?)
        """, ("highlightly", today, now))
        row = conn.execute(
            "SELECT calls FROM api_usage_daily WHERE service = ? AND date = ?",
            ("highlightly", today),
        ).fetchone()
        calls = int(row["calls"] or 0) if row else 0
        data = highlightly_usage_payload(today, calls)
        if count > int(data.get("usable_remaining") or 0):
            conn.rollback()
            return None
        conn.execute("""
            UPDATE api_usage_daily
            SET calls = calls + ?, updated_at = ?
            WHERE service = ? AND date = ?
        """, (count, now, "highlightly", today))
        updated = highlightly_usage_payload(today, calls + count)
        conn.commit()
        mirror_highlightly_usage_json(updated)
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
