"""Build standings payloads."""

from ...utils import load_standings_override, normalize_team_key, parse_score_text


def build_standings_payload(conn, partidos):
    standings_raw = conn.execute("SELECT * FROM clasificacion ORDER BY pos ASC").fetchall()
    standings = {"primera": [], "segunda": []}
    standings_db = {"primera": {}, "segunda": {}}
    for s in standings_raw:
        cat = "primera" if s["division"] == 1 else "segunda"
        item = {
            "n": s["equipo"],
            "pj": s["pj"],
            "pts": s["pts"],
            "pos": s["pos"],
            "pg": s["pg"],
            "pe": s["pe"],
            "pp": s["pp"],
            "gf": s["gf"],
            "gc": s["gc"],
            "racha": s["racha"] if "racha" in s.keys() else "",
            "source": "db",
        }
        standings_db[cat][normalize_team_key(s["equipo"])] = item
        standings[cat].append(item)

    standings_override = load_standings_override()
    if standings_override:
        for cat in ("primera", "segunda"):
            official_rows = []
            for item in standings_override.get(cat, []):
                official_rows.append({
                    "n": item.get("n"),
                    "pj": item.get("pj", 0),
                    "pts": item.get("pts", 0),
                    "pos": item.get("pos", 0),
                    "pg": item.get("pg"),
                    "pe": item.get("pe"),
                    "pp": item.get("pp"),
                    "gf": item.get("gf"),
                    "gc": item.get("gc"),
                    "racha": item.get("racha", ""),
                    "base_oficial": True,
                    "source": "official",
                })
            if official_rows:
                standings[cat] = official_rows

    _apply_finished_results(standings, partidos)
    return standings, standings_db


def _apply_finished_results(standings_data, matches):
    category_by_key = {}
    row_by_key = {}
    for cat, rows in standings_data.items():
        for row in rows:
            key = normalize_team_key(row.get("n"))
            if key:
                category_by_key[key] = cat
                row_by_key[key] = row

    max_pj = {"primera": 38, "segunda": 42}
    for match in matches:
        if str(match.get("status") or "").upper() not in ("FT", "FINISHED", "TERMINADO"):
            continue
        home_key = normalize_team_key(match.get("local"))
        away_key = normalize_team_key(match.get("visitante"))
        cat = category_by_key.get(home_key)
        if not cat or cat != category_by_key.get(away_key):
            continue
        home = row_by_key.get(home_key)
        away = row_by_key.get(away_key)
        if not home or not away:
            continue
        target_pj = max_pj.get(cat)
        if target_pj and (int(home.get("pj") or 0) >= target_pj or int(away.get("pj") or 0) >= target_pj):
            continue

        gh = match.get("goles_local")
        ga = match.get("goles_visitante")
        if gh is None or ga is None:
            gh, ga = parse_score_text(match.get("marcador_base") or match.get("marcador"))
        if gh is None or ga is None:
            continue

        if int(gh) > int(ga):
            _add_result(home, gh, ga, 3, "pg")
            _add_result(away, ga, gh, 0, "pp")
        elif int(gh) < int(ga):
            _add_result(home, gh, ga, 0, "pp")
            _add_result(away, ga, gh, 3, "pg")
        else:
            _add_result(home, gh, ga, 1, "pe")
            _add_result(away, ga, gh, 1, "pe")

    for rows in standings_data.values():
        rows.sort(key=lambda row: (
            -int(row.get("pts") or 0),
            -(int(row.get("gf") or 0) - int(row.get("gc") or 0)),
            -int(row.get("gf") or 0),
            str(row.get("n") or ""),
        ))
        for idx, row in enumerate(rows, start=1):
            row["pos"] = idx


def _add_result(row, gf, gc, points, result_key):
    row["pj"] = int(row.get("pj") or 0) + 1
    row["gf"] = int(row.get("gf") or 0) + int(gf)
    row["gc"] = int(row.get("gc") or 0) + int(gc)
    row["pts"] = int(row.get("pts") or 0) + int(points)
    row[result_key] = int(row.get(result_key) or 0) + 1

