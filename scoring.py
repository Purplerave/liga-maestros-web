import re


def pleno_score_key(value):
    raw = str(value or "").strip().upper().replace(" ", "")
    match = re.search(r"([0-9M]+)-([0-9M]+)", raw)
    if not match:
        return ""

    def bucket(part):
        if part == "M":
            return "M"
        try:
            goals = int(part)
        except Exception:
            return ""
        return "M" if goals >= 3 else str(goals)

    home = bucket(match.group(1))
    away = bucket(match.group(2))
    return f"{home}-{away}" if home and away else ""


def normalize_prediction_sign(partido_id, value):
    raw = str(value or "").strip().upper().replace(" ", "")
    if not raw or raw == "-":
        return "-"
    try:
        match_id = int(partido_id)
    except Exception:
        return ""
    if match_id == 15:
        return pleno_score_key(raw)
    if match_id < 1 or match_id > 14:
        return ""
    if any(ch not in "1X2" for ch in raw):
        return ""
    chars = "".join(ch for ch in "1X2" if ch in set(raw))
    return chars if chars else ""


def score_prediction(partido_id, prediction, real_sign):
    pred = str(prediction or "").strip().upper()
    real = str(real_sign or "").strip().upper()
    if not pred or pred == "-" or not real or real == "-":
        return 0
    if int(partido_id or 0) == 15:
        return 1 if pleno_score_key(pred) == pleno_score_key(real) else 0
    return 1 if real in pred else 0
