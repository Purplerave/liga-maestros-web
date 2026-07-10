"""Teams: logos, contracts, name normalization, participant ecosystem."""
import os
import json
import re
from datetime import datetime

import config
from ..utils import normalize_team_key, clean_team_key, short_team_name, team_token, load_team_logos, build_team_contract, safe_read_json


def short_ai_label(name, uid):
    labels = {
        "programa": "PROG",
        "gemini": "GEM",
        "grok": "GROK",
        "claude": "CLAU",
        "copilot": "COP",
        "chatgpt": "GPT",
    }
    canonical = canonical_contest_id(uid)
    if canonical in labels:
        return labels[canonical]
    text = re.sub(r"[^A-Z0-9]+", "", str(name or uid or "").upper())
    return (text[:4] or str(uid or "")[:4].upper())


def public_contest_name(uid, users):
    names = {
        "v260_omnisciente": "PROGRAMA",
        "programa": "PROGRAMA",
        "gemini": "GEMINI",
        "grok": "GROK",
        "claude": "CLAUDE",
        "copilot": "COPILOT",
        "chatgpt": "CHATGPT",
        "chipi": "CHIPI",
        "deepseek": "CHIPI",
        "kimi": "KIMI",
        "profe": "PROFE",
    }
    if uid in names:
        return names[uid]
    user_name = (users.get(uid) or "").strip()
    if user_name:
        return user_name.split()[0][:16]
    return str(uid or "").split("@")[0][:16].upper()


def canonical_contest_id(uid):
    value = str(uid or "").strip()
    low = value.lower()
    if low in ("v260_omnisciente", "programa"):
        return "programa"
    if low in ("deepseek", "chipi"):
        return "chipi"
    if low in (
        "gemini", "grok", "claude", "copilot", "chatgpt", "kimi", "profe",
        "ernie", "fortu", "geli", "mrpurple", "oraculo", "pepe", "consenso",
        "hermes", "jenova", "momo", "manu", "manus", "qwen", "gwen", "meta",
        "perplexity", "glm5", "geli_glm5", "chema_cohere", "momo_molbot",
        "tecnotron", "consejo_ias", "fistro", "sesudo", "jimmy", "falcon",
    ):
        return low
    return value


def contest_aliases_for_uid(uid):
    canonical = canonical_contest_id(uid)
    aliases = {str(uid or "").strip(), canonical}
    if canonical == "programa":
        aliases.update({"programa", "v260_omnisciente"})
    elif canonical == "chipi":
        aliases.update({"chipi", "deepseek"})
    return sorted(alias for alias in aliases if alias)


def prediction_source_priority(uid):
    low = str(uid or "").strip().lower()
    if low == "programa":
        return 0
    if low == "v260_omnisciente":
        return 1
    if low == "chipi":
        return 0
    if low == "deepseek":
        return 1
    canonical = canonical_contest_id(low)
    return 0 if low == canonical else 1


def is_scored_status(status):
    return str(status or "").upper() in ("FT", "FINISHED", "TERMINADO")


def is_live_scored_status(status):
    return str(status or "").upper() in ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO")


def build_participant_contract():
    path = os.path.join(config.DATA_DIR, "ECOSISTEMA_PARTICIPANTES.json")
    raw = safe_read_json(path, {})
    names_raw = raw.get("nombres_publicos", {}) if isinstance(raw, dict) else {}
    names = {
        canonical_contest_id(uid): name
        for uid, name in names_raw.items()
        if canonical_contest_id(uid)
    }
    hidden_ids = sorted({
        canonical_contest_id(uid)
        for uid in (raw.get("ids_obsoletos", []) if isinstance(raw, dict) else [])
        if canonical_contest_id(uid)
    } | {"consenso", "v260_omnisciente", "consejo_ias"})
    fallback_aliases = {
        "programa": "v260_omnisciente",
    }
    visible_ai_columns = []
    for uid in (raw.get("maestros_oficiales", []) if isinstance(raw, dict) else []):
        canonical = canonical_contest_id(uid)
        if not canonical:
            continue
        if canonical in hidden_ids:
            continue
        name = names.get(canonical) or public_contest_name(canonical, {})
        visible_ai_columns.append({
            "id": canonical,
            "fallback": fallback_aliases.get(canonical),
            "label": short_ai_label(name, canonical),
            "name": name,
        })
    if not visible_ai_columns:
        visible_ai_columns = [
            {"id": "programa", "fallback": "v260_omnisciente", "label": "PROG", "name": "Programa"},
            {"id": "gemini", "fallback": None, "label": "GEM", "name": "Gemini"},
            {"id": "grok", "fallback": None, "label": "GROK", "name": "Grok"},
            {"id": "claude", "fallback": None, "label": "CLAU", "name": "Claude"},
            {"id": "copilot", "fallback": None, "label": "COP", "name": "Copilot"},
            {"id": "chatgpt", "fallback": None, "label": "GPT", "name": "ChatGPT"},
        ]
    return {
        "version": raw.get("version", 1) if isinstance(raw, dict) else 1,
        "names": names,
        "hidden_ids": hidden_ids,
        "visible_ai_columns": visible_ai_columns,
        "roles": raw.get("roles", {}) if isinstance(raw, dict) else {},
    }
