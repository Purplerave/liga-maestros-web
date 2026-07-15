"""Public legal pages and authenticated account deletion."""
import os

from flask import Blueprint, redirect, render_template, request, session, url_for

from ..db.connection import get_db
from ..middleware.csrf import get_csrf_token

bp = Blueprint("legal", __name__)


def _legal_context():
    return {
        "owner_name": os.getenv("LEGAL_OWNER_NAME", "Responsable de Liga de Maestros"),
        "owner_id": os.getenv("LEGAL_OWNER_ID", "Pendiente de configurar"),
        "owner_address": os.getenv("LEGAL_OWNER_ADDRESS", "Pendiente de configurar"),
        "contact_email": os.getenv("LEGAL_CONTACT_EMAIL", "Pendiente de configurar"),
        "user": session.get("user"),
    }


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
    if not session.get("user"):
        return redirect(url_for("auth.login"))
    return render_template("legal/account.html", csrf_token=get_csrf_token(), **_legal_context())


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
