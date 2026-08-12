from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "static" / "css" / "base" / "tokens.css"
MOBILE = ROOT / "static" / "css" / "mobile_responsive.css"
TICKET = ROOT / "static" / "js" / "pages" / "ticket_page.js"
APP = ROOT / "static" / "js" / "quantum_final.js"


def test_save_feedback_is_visible_in_a_fixed_toast_layer():
    tokens = TOKENS.read_text(encoding="utf-8")
    mobile = MOBILE.read_text(encoding="utf-8")

    toast_rule = tokens.split("#toast-container {", 1)[1].split("}", 1)[0]
    assert "position: fixed" in toast_rule
    assert "z-index:" in toast_rule
    assert "width: min(" in toast_rule
    assert "#toast-container" in mobile
    assert ".toast-container" not in mobile


def test_empty_pleno_is_not_presented_as_a_real_zero_zero_pick():
    ticket = TICKET.read_text(encoding="utf-8")

    assert 'const plenoLabel = mySign === "-" ? "Elegir" : mySign;' in ticket
    assert 'mySign === "-" ? "0-0" : mySign' not in ticket
    assert "Elegir resultado del Pleno al 15" in ticket


def test_save_validates_all_picks_and_recovers_an_expired_csrf_token():
    app = APP.read_text(encoding="utf-8")
    save = app.split("async function savePredictions()", 1)[1].split("\nfunction shareTicket()", 1)[0]

    assert "missingMatches" in save
    assert "Completa la quiniela" in save
    assert 'saveButton.textContent = "Guardando..."' in save
    assert 'fetch("/api/user/status", { cache: "no-store" })' in save
    assert "state.csrfToken = statusPayload.csrf_token" in save
    assert "Quiniela guardada correctamente." in save
    assert "finally" in save
