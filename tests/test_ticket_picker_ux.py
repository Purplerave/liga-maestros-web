from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TICKET_JS = ROOT / "static" / "js" / "pages" / "ticket_page.js"
EVENTS_JS = ROOT / "static" / "js" / "events.js"
TICKET_CSS = ROOT / "static" / "css" / "pages" / "ticket.css"
TICKET_COMPACT_CSS = ROOT / "static" / "css" / "pages" / "ticket_compact.css"


def test_user_1x2_picker_is_a_single_three_column_group():
    ticket = TICKET_JS.read_text(encoding="utf-8")
    css = TICKET_CSS.read_text(encoding="utf-8")

    assert 'class="ticket-user-sign-group action-buttons"' in ticket
    assert 'role="group"' in ticket
    assert 'aria-pressed="${mySign === sign ? "true" : "false"}"' in ticket
    picker_rule = css.split(".tension-chip-user .ticket-user-sign-group,", 1)[1].split("}", 1)[0]
    assert "display: grid" in picker_rule
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in picker_rule
    assert "width: 100%" in picker_rule

    compact = TICKET_COMPACT_CSS.read_text(encoding="utf-8")
    compact_picker = compact.split(".ticket-user-cell .action-buttons {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in compact_picker
    assert "width: 100%" in compact_picker
    assert "repeat(3, 28px)" not in compact_picker


def test_a_pick_has_only_one_click_handler():
    ticket = TICKET_JS.read_text(encoding="utf-8")
    events = EVENTS_JS.read_text(encoding="utf-8")

    # A direct onclick plus the delegated matches-body listener used to run for
    # the same event: it selected a sign and immediately toggled it off again.
    assert ".ticket-user-sign-group button.ia-signo.clickable" not in ticket
    assert 'event.target.closest(".clickable")' in events
    assert 'state.my_signs[idx] = state.my_signs[idx] === btn.dataset.sign ? "-" : btn.dataset.sign;' in events


def test_pleno_uses_the_exact_score_picker_instead_of_1x2():
    ticket = TICKET_JS.read_text(encoding="utf-8")

    assert "if (exactScore)" in ticket
    assert 'data-pleno="true"' in ticket
    assert 'class="ticket-user-sign-group ticket-pleno-sign-group"' in ticket
    assert "grid-column: 1 / -1" in TICKET_CSS.read_text(encoding="utf-8")


def test_saved_ticket_stays_in_the_row_instead_of_showing_the_1x2_picker():
    ticket = TICKET_JS.read_text(encoding="utf-8")
    events = EVENTS_JS.read_text(encoding="utf-8")

    # El selector 1X2 solo se pinta sin quiniela guardada o en modo edicion;
    # con la quiniela guardada la fila muestra el signo en solo lectura.
    assert "(state.editMode || state.draftDirty || !hasSavedTicket())" in ticket
    assert 'class="ia-signo ticket-user-sign ${stateClass} active' in ticket
    assert '"empty-user-pick"' in ticket
    assert '"saved-ticket-sign"' in ticket
    # El listener delegado tampoco debe permitir editar un boleto ya guardado.
    assert "hasSavedTicket() && !state.editMode && !state.draftDirty" in events
    assert "Editar quiniela" in events
