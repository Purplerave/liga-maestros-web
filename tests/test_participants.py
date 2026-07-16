from liga_maestros.services.payloads.predictions import _build_pena_consensus, _build_pena_pleno_consensus
from liga_maestros.services.teams import canonical_contest_id, contest_aliases_for_uid


def test_fictitious_pena_aliases_hide_the_source_models():
    expected = {
        "deepseek": "chipi",
        "glm5": "geli",
        "perplexity": "pepe",
        "meta": "profe",
        "mistral": "fortu",
        "qwen": "oraculo",
        "ernie": "fistro",
        "kimi": "sesudo",
        "luzia": "jimmy",
    }
    for source, public_alias in expected.items():
        assert canonical_contest_id(source) == public_alias
        assert source in contest_aliases_for_uid(public_alias)


def test_pena_doubles_split_one_vote_between_both_signs():
    preds = {
        "chipi": {"signos": ["1X"] + ["-"] * 14},
        "geli": {"signos": ["2"] + ["-"] * 14},
        "claude": {"signos": ["1"] + ["-"] * 14},
    }
    contract = {
        "visible_ai_columns": [{"id": "claude"}],
        "hidden_ids": [],
        "pena_ids": ["chipi", "geli"],
    }

    first = _build_pena_consensus(preds, contract)[0]

    assert first["total"] == 2
    assert first["votes"] == {"1": 0.5, "X": 0.5, "2": 1}
    assert (first["p1"], first["px"], first["p2"]) == (25, 25, 50)
    assert first["ganador"] == "2"


def test_personal_user_ticket_is_not_counted_as_pena_consensus():
    preds = {
        "chipi": {"signos": ["1"] + ["-"] * 14},
        "116699982648036669051": {"signos": ["2"] + ["-"] * 14},
    }
    contract = {
        "visible_ai_columns": [],
        "hidden_ids": [],
        "pena_ids": ["chipi"],
    }

    first = _build_pena_consensus(preds, contract)[0]

    assert first["total"] == 1
    assert (first["p1"], first["px"], first["p2"]) == (100, 0, 0)


def test_pena_pleno_accepts_m_goal_bucket_without_revealing_members():
    preds = {
        "pepe": {"signos": ["-"] * 14 + ["M-1"]},
        "geli": {"signos": ["-"] * 14 + ["3-1"]},
        "claude": {"signos": ["-"] * 14 + ["2-1"]},
    }
    contract = {
        "visible_ai_columns": [{"id": "claude"}],
        "hidden_ids": [],
        "pena_ids": ["pepe", "geli"],
    }

    summary = _build_pena_pleno_consensus(preds, contract)

    assert summary["valid"] == 2
    assert summary["invalid"] == 0
    assert summary["exactCounts"] == {"M-1": 2}
    assert summary["homeBuckets"]["M"] == 2
    assert summary["awayBuckets"]["1"] == 2
    assert summary["topScore"] == ("M-1", 2)
