import os
import sys
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring import normalize_prediction_sign, pleno_score_key, score_prediction


def test_pleno_score_key_buckets_three_or_more_as_m():
    assert pleno_score_key("3-0") == "M-0"
    assert pleno_score_key("M-0") == "M-0"
    assert pleno_score_key("5-4") == "M-M"


def test_pleno_score_key_preserves_exact_low_scores():
    assert pleno_score_key("2-2") == "2-2"
    assert pleno_score_key("2-2") != pleno_score_key("3-2")


def test_normalize_prediction_sign_orders_and_uppercases_doubles():
    assert normalize_prediction_sign(5, "1x") == "1X"
    assert normalize_prediction_sign(5, "x1") == "1X"
    assert normalize_prediction_sign(5, "21") == "12"


def test_normalize_prediction_sign_handles_pleno_and_invalid_values():
    assert normalize_prediction_sign(15, "3-0") == "M-0"
    assert normalize_prediction_sign(15, "M-0") == "M-0"
    assert normalize_prediction_sign(16, "1") == ""
    assert normalize_prediction_sign(1, "A") == ""


def test_score_prediction_standard_matches_single_and_multiple_signs():
    assert score_prediction(1, "1X", "X") == 1
    assert score_prediction(1, "12", "X") == 0
    assert score_prediction(1, "1", "-") == 0


def test_score_prediction_pleno_uses_bucketed_score():
    assert score_prediction(15, "3-0", "M-0") == 1
    assert score_prediction(15, "2-2", "3-2") == 0
