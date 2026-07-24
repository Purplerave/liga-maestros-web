"""Teams: logos, contracts, name normalization, participant ecosystem."""
import os
import re

import config
from ..utils import safe_read_json


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
        "geli": "GELI",
        "pepe": "PEPE",
        "profe": "PROFE",
        "fortu": "FORTU",
        "oraculo": "ORACULO",
        "fistro": "FISTRO",
        "sesudo": "SESUDO",
        "jimmy": "JIMMY",
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
    pena_aliases = {
        "deepseek": "chipi", "chipi": "chipi",
        "glm5": "geli", "geli_glm5": "geli", "geli": "geli",
        "perplexity": "pepe", "pepe": "pepe",
        "meta": "profe", "profe_llama": "profe", "profe": "profe",
        "mistral": "fortu", "fortu": "fortu",
        "qwen": "oraculo", "gwen": "oraculo", "oraculo": "oraculo",
        "ernie": "fistro", "ernie_ai": "fistro", "fistro": "fistro",
        "kimi": "sesudo", "sesudo": "sesudo",
        "luzia": "jimmy", "jimmy": "jimmy",
    }
    if low in pena_aliases:
        return pena_aliases[low]
    if low in (
        "gemini", "grok", "claude", "copilot", "chatgpt", "mrpurple", "consenso",
        "hermes", "jenova", "momo", "manu", "manus", "qwen", "gwen", "meta",
        "chema_cohere", "momo_molbot",
        "tecnotron", "consejo_ias", "fistro", "sesudo", "jimmy", "falcon",
    ):
        return low
    return value


def contest_aliases_for_uid(uid):
    canonical = canonical_contest_id(uid)
    aliases = {str(uid or "").strip(), canonical}
    if canonical == "programa":
        aliases.update({"programa", "v260_omnisciente"})
    pena_sources = {
        "chipi": {"chipi", "deepseek"},
        "geli": {"geli", "glm5", "geli_glm5"},
        "pepe": {"pepe", "perplexity"},
        "profe": {"profe", "meta", "profe_llama"},
        "fortu": {"fortu", "mistral"},
        "oraculo": {"oraculo", "qwen", "gwen"},
        "fistro": {"fistro", "ernie", "ernie_ai"},
        "sesudo": {"sesudo", "kimi"},
        "jimmy": {"jimmy", "luzia"},
    }
    aliases.update(pena_sources.get(canonical, set()))
    return sorted(alias for alias in aliases if alias)


def prediction_source_priority(uid):
    low = str(uid or "").strip().lower()
    if low == "programa":
        return 0
    if low == "v260_omnisciente":
        return 1
    canonical = canonical_contest_id(low)
    return 0 if low == canonical else 1


def is_scored_status(status):
    return str(status or "").upper() in ("FT", "FINISHED", "TERMINADO")


def is_live_scored_status(status):
    return str(status or "").upper() in ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO")


def build_participant_contract():
    seed_path = os.path.join(config.SEED_DATA_DIR, "ECOSISTEMA_PARTICIPANTES.json")
    runtime_path = os.path.join(config.DATA_DIR, "ECOSISTEMA_PARTICIPANTES.json")
    raw = safe_read_json(seed_path, {}) or safe_read_json(runtime_path, {})
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
    pena_ids = []
    for uid in (raw.get("pena_aliases", []) if isinstance(raw, dict) else []):
        canonical = canonical_contest_id(uid)
        if canonical and canonical not in pena_ids:
            pena_ids.append(canonical)
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
        "pena_ids": pena_ids,
        "visible_ai_columns": visible_ai_columns,
        "roles": raw.get("roles", {}) if isinstance(raw, dict) else {},
    }
