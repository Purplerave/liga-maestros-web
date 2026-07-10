"""Export approved rich quiz questions to the current web quiz format.

The live web already imports data/QUIZ_BANK_J{jornada}.json with 10 questions,
3 options and answers A/B/C. This script bridges the richer long-term bank and
the existing production format.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APPROVED_DIR = ROOT / "data" / "quiz" / "approved"
OUTPUT_DIR = ROOT / "data"


def load_approved_questions() -> list[dict]:
    questions: list[dict] = []
    for path in sorted(APPROVED_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        questions.extend(data.get("questions", []))
    return [q for q in questions if q.get("status") == "approved"]


def to_web_question(question: dict) -> dict:
    options = {str(opt["id"]).upper(): opt["label"] for opt in question["options"]}
    return {
        "tipo": "multiple",
        "enunciado": question["prompt"],
        "opcion_a": options["A"],
        "opcion_b": options["B"],
        "opcion_c": options["C"],
        "respuesta_correcta": str(question["correct_option_id"]).upper(),
        "explicacion": question.get("explanation", ""),
        "dificultad": int(question.get("difficulty") or 1),
        "tema": question.get("category", ""),
        "source_id": question.get("id", ""),
    }


def select_questions(questions: list[dict], count: int, seed: str) -> list[dict]:
    pool = list(questions)
    random.Random(seed).shuffle(pool)
    selected: list[dict] = []
    category_counts: dict[str, int] = {}
    for question in pool:
        category = str(question.get("category") or "")
        if category_counts.get(category, 0) >= 3:
            continue
        selected.append(question)
        category_counts[category] = category_counts.get(category, 0) + 1
        if len(selected) >= count:
            return selected
    if len(selected) < count:
        selected_ids = {q.get("id") for q in selected}
        selected.extend(q for q in pool if q.get("id") not in selected_ids)
    return selected[:count]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export approved quiz questions to QUIZ_BANK_J{jornada}.json.")
    parser.add_argument("--jornada", "-j", type=int, required=True)
    parser.add_argument("--count", "-n", type=int, default=10)
    parser.add_argument("--seed", default="")
    parser.add_argument("--output", "-o", default="")
    args = parser.parse_args()

    questions = load_approved_questions()
    if len(questions) < args.count:
        print(f"Need {args.count} approved questions, found {len(questions)}.")
        return 1

    seed = args.seed or f"jornada-{args.jornada}"
    selected = select_questions(questions, args.count, seed)
    payload = {
        "jornada": args.jornada,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "data/quiz/approved",
        "preguntas": [to_web_question(question) for question in selected],
    }

    output = Path(args.output) if args.output else OUTPUT_DIR / f"QUIZ_BANK_J{args.jornada}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {output}")
    print(f"Preguntas: {len(payload['preguntas'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
