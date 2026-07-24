"""Public legal pages and authenticated account deletion."""
import os
import logging

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from ..db.connection import get_db
from ..middleware.csrf import get_csrf_token

bp = Blueprint("legal", __name__)
logger = logging.getLogger(__name__)


def _legal_context():
    env = os.environ
    context = {
        "owner_name": env.get("LEGAL_OWNER_NAME"),
        "owner_id": env.get("LEGAL_OWNER_ID"),
        "owner_address": env.get("LEGAL_OWNER_ADDRESS"),
        "contact_email": env.get("LEGAL_CONTACT_EMAIL"),
        "user": session.get("user"),
    }
    if env.get("FLASK_ENV") == "production" or env.get("RENDER") == "1":
        missing = [k for k, v in context.items() if k != "user" and not v]
        if missing:
            logger.critical("Legal text incomplete - missing env vars: %s", missing)
    for key in ("owner_name", "owner_id", "owner_address", "contact_email"):
        if not context[key]:
            context[key] = "No configurado"
    return context


@bp.route("/privacidad")
def privacy():
    return render_template("legal/privacy.html", **_legal_context())


@bp.route("/aviso-legal")
def legal_notice():
    return render_template("legal/legal_notice.html", **_legal_context())


@bp.route("/cookies")
def cookies():
    return render_template("legal/cookies.html", **_legal_context())


@bp.route("/cuenta")
def account():
    user = session.get("user") or {}
    if not user:
        return redirect(url_for("auth.login"))
    account_user = {"id": user.get("id"), "name": user.get("name")}
    conn = get_db()
    try:
        row = conn.execute("SELECT nombre FROM usuarios WHERE id = ?", (user.get("id"),)).fetchone()
        if row:
            account_user["name"] = row["nombre"] or account_user["name"]
    finally:
        conn.close()
    context = _legal_context()
    context["user"] = account_user
    return render_template("legal/account.html", csrf_token=get_csrf_token(), **context)


def _table_exists(conn, table):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def delete_user_data(conn, user_id):
    """Delete every row directly owned by an authenticated human account."""
    owned_tables = {
        "predicciones": "user_id",
        "comentarios_jornada": "user_id",
        "porra_entries": "user_id",
        "snake_scores": "user_id",
        "quiz_participaciones": "user_id",
        "api_rate_limit": "identity",
    }
    deleted = {}
    for table, column in owned_tables.items():
        if not _table_exists(conn, table):
            continue
        cursor = conn.execute(f'DELETE FROM "{table}" WHERE "{column}" = ?', (user_id,))
        deleted[table] = cursor.rowcount
    if _table_exists(conn, "usuarios"):
        cursor = conn.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
        deleted["usuarios"] = cursor.rowcount
    return deleted


@bp.post("/cuenta/eliminar")
def delete_account():
    user = session.get("user") or {}
    user_id = str(user.get("id") or "")
    confirmation = str(request.form.get("confirmacion") or "").strip().upper()
    if not user_id:
        return redirect(url_for("auth.login"))
    if confirmation != "ELIMINAR":
        return "Escribe ELIMINAR para confirmar.", 400

    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        delete_user_data(conn, user_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    session.clear()
    return render_template("legal/account_deleted.html", **_legal_context())
