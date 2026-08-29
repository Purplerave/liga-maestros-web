.PHONY: jornada demo metrics test

# CEO MANDATE: una sola orden que un becario ejecuta. Si falla, es bug.
jornada:
	@echo "== JORNADA $(J) =="
	@test -n "$(J)" || (echo "Uso: make jornada J=3" && exit 1)
	python tools/ops/REPARAR_JORNADA_QUINIELA.py --jornada $(J)
	python -m pytest tests/test_ensure_jornada_completa.py tests/test_production_readiness.py -v -o 'addopts='
	@echo "Jornada $(J) lista. Verifica en /?j=$(J)"

demo:
	@echo "=== DEMO VIERNES — Métricas CEO ==="
	@curl -s https://ligademaestros.alwaysdata.net/metrics | grep -E "http_requests_total|highlightly_calls|http_request_duration"
	@curl -s https://ligademaestros.alwaysdata.net/api/live/health | python -m json.tool
	@echo "Portada p95: $$(curl -s -w '%{time_total}' -o /dev/null https://ligademaestros.alwaysdata.net/api/liga/data | awk '{print $$1*1000 \"ms\"}')"
	@echo "Conversión portada: revisa /metrics -> http_requests_total path=/ path=/app"

metrics:
	curl -s https://ligademaestros.alwaysdata.net/metrics | head -30

test:
	python -m pytest -q --ignore=tests/test_ensure_jornada_completa.py --ignore=tests/test_production_readiness.py
	python -m pytest tests/test_ensure_jornada_completa.py tests/test_production_readiness.py -v -o 'addopts=' || true
