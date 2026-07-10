"""Validate Liga de Maestros quiz bank files.

The rich quiz bank lives in data/quiz/{generated,approved}. This validator keeps
AI-generated batches from entering the approved bank with missing fields,
ambiguous answers, or obvious licensing/source problems.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUIZ_ROOT = ROOT / "data" / "quiz"
DEFAULT_DIRS = [QUIZ_ROOT / "approved", QUIZ_ROOT / "generated"]
ALLOWED_STATUSES = {"generated", "approved", "rejected"}
ALLOWED_OPTION_IDS = {"A", "B", "C"}
RISKY_SOURCE_HINTS = {
    "transfermarkt",
    "fbref",
    "fotmob",
    "flashscore",
    "sofascore",
    "marca",
    "as.com",
    "whoscored",
    "understat",
}


def load_questions(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("missing top-level 'questions' list")
    return questions


def validate_question(question: dict, seen_ids: set[str]) -> list[str]:
    errors: list[str] = []
    qid = str(question.get("id") or "").strip()
    if not qid:
        errors.append("missing id")
    elif qid in seen_ids:
        errors.append(f"duplicate id '{qid}'")
    else:
        seen_ids.add(qid)

    for field in ("mode", "category", "prompt", "explanation", "correct_option_id", "status"):
        if not str(question.get(field) or "").strip():
            errors.append(f"missing {field}")

    status = str(question.get("status") or "").strip()
    if status and status not in ALLOWED_STATUSES:
        errors.append(f"invalid status '{status}'")

    difficulty = question.get("difficulty")
    if not isinstance(difficulty, int) or not (1 <= difficulty <= 10):
        errors.append("difficulty must be an integer from 1 to 10")

    options = question.get("options")
    if not isinstance(options, list) or len(options) != 3:
        errors.append("options must contain exactly 3 entries for the current web quiz")
        option_ids = set()
        labels = []
    else:
        option_ids = {str(opt.get("id") or "").strip().upper() for opt in options if isinstance(opt, dict)}
        labels = [str(opt.get("label") or "").strip().casefold() for opt in options if isinstance(opt, dict)]
        if option_ids != ALLOWED_OPTION_IDS:
            errors.append("option ids must be A, B and C")
        if any(not label for label in labels):
            errors.append("all options need labels")
        if len(set(labels)) != len(labels):
            errors.append("option labels must be unique")

    correct = str(question.get("correct_option_id") or "").strip().upper()
    if correct not in ALLOWED_OPTION_IDS:
        errors.append("correct_option_id must be A, B or C")
    elif options and correct not in option_ids:
        errors.append("correct_option_id does not exist in options")

    source_facts = question.get("source_facts")
    if not isinstance(source_facts, list) or not source_facts:
        errors.append("source_facts must contain at least one source")
    else:
        for idx, source in enumerate(source_facts, start=1):
            provider = str(source.get("provider") or "").strip()
            ref = str(source.get("ref") or "").strip()
            license_name = str(source.get("license") or "").strip()
            if not provider or not ref or not license_name:
                errors.append(f"source_facts[{idx}] needs provider, ref and license")
            source_text = f"{provider} {ref}".casefold()
            if any(hint in source_text for hint in RISKY_SOURCE_HINTS):
                errors.append(f"source_facts[{idx}] uses risky/prohibited source '{provider}:{ref}'")

    return errors


def validate_file(path: Path, seen_ids: set[str]) -> int:
    try:
        questions = load_questions(path)
    except Exception as exc:
        print(f"ERROR {path}: {exc}")
        return 1

    failures = 0
    for idx, question in enumerate(questions, start=1):
        errors = validate_question(question, seen_ids)
        if errors:
            failures += 1
            qid = question.get("id") or f"#{idx}"
            print(f"ERROR {path} :: {qid}")
            for error in errors:
                print(f"  - {error}")
    return failures


def iter_json_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".json":
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.glob("*.json")))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Liga de Maestros quiz bank JSON files.")
    parser.add_argument("paths", nargs="*", help="Files or folders to validate. Defaults to approved and generated.")
    args = parser.parse_args()

    paths = [Path(p) for p in args.paths] if args.paths else DEFAULT_DIRS
    files = iter_json_files(paths)
    if not files:
        print("No quiz JSON files found.")
        return 1

    seen_ids: set[str] = set()
    failures = 0
    for file in files:
        failures += validate_file(file, seen_ids)

    if failures:
        print(f"FAILED: {failures} invalid question(s).")
        return 1
    print(f"OK: {len(files)} file(s) validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
