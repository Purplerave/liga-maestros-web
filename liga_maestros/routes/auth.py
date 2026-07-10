"""Auth routes: Google OAuth login/authorize/logout."""
from flask import Blueprint, redirect, url_for, session
import os

import config
from ..db.connection import get_db

bp = Blueprint("auth", __name__)


def _get_google():
    from flask import current_app
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(current_app)
    return oauth.register(
        name='google',
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        server_metadata_url=config.GOOGLE_SERVER_METADATA_URL,
        client_kwargs=config.GOOGLE_CLIENT_KWARGS,
    )


@bp.route('/login/google')
def login():
    if not config.GOOGLE_AUTH_ENABLED:
        return "Google OAuth no configurado en variables de entorno.", 503
    google = _get_google()
    redirect_uri = url_for('auth.authorize', _external=True)
    return google.authorize_redirect(redirect_uri)


@bp.route('/authorize')
def authorize():
    if not config.GOOGLE_AUTH_ENABLED:
        return redirect('/')
    google = _get_google()
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if user_info:
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO usuarios (id, nombre, email)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre, email=excluded.email
            """, (user_info['sub'], user_info['name'], user_info['email']))
            conn.commit()
        finally:
            conn.close()
        session['user'] = {'id': user_info['sub'], 'name': user_info['name'], 'email': user_info['email']}
    return redirect('/')


@bp.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')
