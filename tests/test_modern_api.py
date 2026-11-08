from flask import Flask

from liga_maestros.routes import liga_data, modern_api, standings_modern


def _client():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="modern-api-test")
    app.register_blueprint(modern_api.bp)
    app.register_blueprint(standings_modern.bp)
    return app.test_client()


def test_modern_jornada_endpoint_returns_builder_payload(monkeypatch):
    expected = [{"id": 1, "local": "Andorra", "visitante": "Ceuta"}]
    seen = {}
    monkeypatch.setattr(modern_api, "get_db", lambda: "db")
    monkeypatch.setattr(liga_data, "load_team_logos", lambda: {"ANDORRA": "/andorra.svg"})

    def build_matches(conn, jornada, logos):
        seen.update(conn=conn, jornada=jornada, logos=logos)
        return expected

    monkeypatch.setattr(modern_api, "build_jornada_matches", build_matches)
    response = _client().get("/api/modern/jornada/9")

    assert response.status_code == 200
    assert response.get_json() == {"status": "success", "data": expected}
    assert seen == {"conn": "db", "jornada": "9", "logos": {"ANDORRA": "/andorra.svg"}}


def test_modern_standings_supports_both_slash_forms_and_maps_ranking(monkeypatch):
    payload = {
        "participant_contract": {"names": {"grok": "Grok"}},
        "ranking_maestros": {
            "grok": {"total": 13, "bonus": 2},
            "public-user": {"total": 9, "bonus": 0},
        },
    }
    seen = {}
    monkeypatch.setattr(standings_modern, "get_db", lambda: "db")

    def build_predictions(conn, jornada):
        seen.update(conn=conn, jornada=jornada)
        return payload

    monkeypatch.setattr(standings_modern, "build_predictions_payload", build_predictions)
    client = _client()

    for path in ("/api/modern/standings?jornada=4", "/api/modern/standings/?jornada=4"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.get_json() == {
            "status": "success",
            "data": [
                {"id": "grok", "name": "Grok", "hits": 11, "points": 13},
                {"id": "public-user", "name": "public-user", "hits": 9, "points": 9},
            ],
        }

    assert seen == {"conn": "db", "jornada": "4"}


def test_modern_standings_does_not_expose_internal_errors(monkeypatch):
    monkeypatch.setattr(standings_modern, "get_db", lambda: "db")

    def fail_to_build(*_args):
        raise RuntimeError("internal database details")

    monkeypatch.setattr(standings_modern, "build_predictions_payload", fail_to_build)
    response = _client().get("/api/modern/standings/")

    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "No se pudo cargar la clasificación"}
    assert "internal database details" not in response.get_data(as_text=True)
