"""Directo: un mismo partido no puede salir dos veces.

Bug: `build_live_matches` deduplica por `fixture_id`/`id`, pero el partido de
la quiniela se construye con un id sintético (`quiniela-{jornada}-{n}`) que
JAMÁS coincide con el `fixture_id` numérico que manda Highlightly para ese
mismo encuentro. Resultado: Alavés-Getafe aparecía dos veces en Directo, una
con los datos del proveedor y otra con los de la quiniela.

`build_all_league_matches` sí lo resolvía comparando los nombres de equipo
(`_duplicates_quiniela_match`); el camino de Directo se quedó sin esa red.
"""

from liga_maestros.services.payloads import league_matches


def _external_live():
    return {
        "id": 987654,
        "fixture_id": 987654,
        "status": "LIVE",
        "score": "1-0",
        "time": "34",
        "added": "2026-08-15 19:30:00",
        "fecha_raw": "2026-08-15",
        "hora": "19:30",
        "competition_name": "LA LIGA",
        "competition": {"name": "LA LIGA"},
        "home": {"name": "Alavés"},
        "away": {"name": "Getafe"},
        "local": "Alavés",
        "visitante": "Getafe",
    }


def _quiniela_partido():
    return {
        "id": 1,
        "local": "Alavés",
        "visitante": "Getafe",
        "status": "LIVE",
        "marcador": "1-0",
        "minuto": "34",
        "fecha_raw": "2026-08-15",
        "hora": "19:30",
        "logo_local": "",
        "logo_visitante": "",
    }


def _pairs(matches):
    return [
        (
            str(m.get("local") or (m.get("home") or {}).get("name")),
            str(m.get("visitante") or (m.get("away") or {}).get("name")),
        )
        for m in matches
    ]


def test_el_mismo_partido_no_se_duplica_en_directo(monkeypatch):
    """El proveedor y la quiniela describen el mismo encuentro: debe salir UNO."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-15")
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [_external_live()])

    result = league_matches.build_live_matches([_quiniela_partido()], {})

    assert _pairs(result) == [("Alavés", "Getafe")], f"Partido duplicado en Directo: {_pairs(result)}"
    assert len(result) == 1


def test_se_conserva_el_marcador_del_proveedor_al_deduplicar(monkeypatch):
    """Al fusionar, no se pierde el dato en vivo."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-15")
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [_external_live()])

    result = league_matches.build_live_matches([_quiniela_partido()], {})

    assert len(result) == 1
    assert (result[0].get("score") or result[0].get("marcador")) == "1-0"


def test_partidos_distintos_siguen_saliendo_todos(monkeypatch):
    """La deduplicación no puede comerse encuentros diferentes."""
    otro = _external_live()
    otro.update(
        {
            "id": 111222,
            "fixture_id": 111222,
            "home": {"name": "Sevilla"},
            "away": {"name": "Rayo Vallecano"},
            "local": "Sevilla",
            "visitante": "Rayo Vallecano",
        }
    )
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-15")
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [_external_live(), otro])

    result = league_matches.build_live_matches([_quiniela_partido()], {})

    assert len(result) == 2
    assert ("Sevilla", "Rayo Vallecano") in _pairs(result)
    assert ("Alavés", "Getafe") in _pairs(result)


def test_deduplica_aunque_el_nombre_venga_escrito_distinto(monkeypatch):
    """'Alaves' sin tilde o 'Deportivo Alavés' son el mismo equipo."""
    externo = _external_live()
    externo.update({"home": {"name": "Deportivo Alaves"}, "local": "Deportivo Alaves"})
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-15")
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [externo])

    result = league_matches.build_live_matches([_quiniela_partido()], {})

    assert len(result) == 1, f"No se detectó el mismo equipo con otra grafía: {_pairs(result)}"
