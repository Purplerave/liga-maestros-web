# Paginas del diario

Objetivo: cada pagina visual del diario debe poder editarse sin tocar el motor entero.

Flujo actual:

```text
liga_index.html
  -> quantum_final.js        motor comun: estado, datos, eventos y renderArena()
  -> pages/cover_page.js     Pag. 1 Portada
  -> snake_gol_arcade.js     Juego Snake Gol
```

Regla de trabajo:

- Una pagina nueva vive en `static/js/pages/nombre_page.js`.
- El CSS comun de estilo mecanografiado vive en `static/css/typewriter_system.css`.
- El CSS especifico de portada vive en `static/css/newspaper_cover.css`.
- No duplicar versiones antiguas de una pagina dentro de `quantum_final.js`.
- No meter Snake, Quiz, clasificaciones o La Pena dentro de Portada o Quiniela.

Siguientes extracciones razonables:

```text
pages/ticket_page.js      Pag. 2 Quiniela
pages/live_page.js        Pag. 3 Directo
pages/standings_page.js   Pag. 4 Ligas
pages/contest_page.js     Pag. 6 La Pena
pages/quiz_page.js        Pag. 7 Quiz
```
