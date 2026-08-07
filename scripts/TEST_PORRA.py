#!/usr/bin/env python3
"""Test script for the porra system."""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config

DB_PATH = Path(config.DB_PATH)


def main():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # Check porra tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%porra%'"
        ).fetchall()
        print("Porra tables:", [t["name"] for t in tables])

        # Check porra entries
        entries = conn.execute("SELECT COUNT(*) as n FROM porra_entries").fetchone()
        print(f"Porra entries: {entries['n']}")

        # Check porra points
        try:
            puntos = conn.execute("SELECT COUNT(*) as n FROM porra_puntos").fetchone()
            print(f"Porra points awarded: {puntos['n']}")
        except Exception:
            print("porra_puntos table not found")

        # Show sample entries
        sample = conn.execute(
            """
            SELECT pe.jornada, pe.partido_id, pe.user_id, pe.nombre, pe.goles_local, pe.goles_visitante,
                   r.local, r.visitante, r.goles_local as r_gl, r.goles_visitante as r_gv, r.status
            FROM porra_entries pe
            LEFT JOIN resultados r ON pe.jornada = r.jornada AND pe.partido_id = r.partido_id
            ORDER BY pe.jornada DESC, pe.partido_id
            LIMIT 10
            """
        ).fetchall()

        if sample:
            print("\nSample porra entries:")
            for row in sample:
                status = row["status"] or "NS"
                match_result = f"{row['r_gl']}-{row['r_gv']}" if row["r_gl"] is not None else "TBD"
                porra_pred = f"{row['goles_local']}-{row['goles_visitante']}"
                is_correct = (
                    row["r_gl"] is not None
                    and row["r_gl"] == row["goles_local"]
                    and row["r_gv"] == row["goles_visitante"]
                )
                print(
                    f"  J{row['jornada']} P{row['partido_id']}: {row['nombre']} predijo {porra_pred} "
                    f"| Resultado: {match_result} ({status}) "
                    f"| {'✅ ACIERTO' if is_correct else '❌'}"
                )
        else:
            print("\nNo porra entries found")


if __name__ == "__main__":
    main()
