# Banco de preguntas - Liga de Maestros

Esta carpeta separa el banco grande de preguntas del quiz que la web consume por jornada.

## Carpetas

- `sources/`: datos de origen o capturas limpias de fuentes permitidas.
- `generated/`: preguntas generadas por IA o scripts, todavia sin aprobar.
- `approved/`: preguntas revisadas y listas para jugar.
- `rejected/`: preguntas descartadas, para no repetir errores.

## Flujo recomendado

1. Otra IA o un script genera preguntas en `generated/`.
2. `scripts/quiz/validate_quiz_bank.py` valida estructura y riesgos basicos.
3. Las buenas se mueven a `approved/`.
4. `scripts/quiz/export_jornada_quiz.py` crea `data/QUIZ_BANK_JXX.json`.
5. `IMPORTAR_QUIZ_JORNADA.py` importa ese JSON a la base de datos.

## Regla de oro

No se aceptan preguntas sin fuente. La fuente puede ser:

- `wikidata:Q...`
- `openfootball:...`
- `liga_maestros:...`
- `rules:ifab`
- otra fuente permitida y documentada

Evitar scraping de webs propietarias y no usar imagenes, escudos o fotos oficiales.
