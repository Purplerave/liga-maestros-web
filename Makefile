.PHONY: install test lint format audit jornada health clean

install:
	pip install -r requirements.txt -r requirements-dev.txt
	pre-commit install 2>/dev/null || echo "pre-commit not installed"

test:
	python -m pytest -q --ignore=tests/test_ensure_jornada_completa.py --ignore=tests/test_production_readiness.py

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

audit:
	pip-audit 2>&1 | head -n 100
	ruff check .
	python -m pytest tests/test_security_hardening.py tests/test_game_security.py -q

jornada:
	@echo "Uso: make jornada J=N  (ej: make jornada J=77)"
	@test -n "$(J)" || (echo "Falta J=numero" && exit 1)
	python AUDITAR_JORNADA_LIGA_MAESTROS.py --jornada $(J)

health:
	curl -s http://127.0.0.1:5000/health | python -m json.tool || curl -s http://127.0.0.1:5000/api/live/health | python -m json.tool

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	rm -rf .pytest_cache .ruff_cache
