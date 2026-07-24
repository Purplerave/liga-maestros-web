# Paginas del diario

Objetivo: cada pagina visual del diario debe poder editarse sin tocar el motor entero.

Flujo actual:

```text
liga_index.html
  -> quantum_final.js        motor comun: datos e inicio
  -> navigation.js           carga CSS y JS solo para la pagina activa
  -> arena.js                distribuye el render de la pagina activa
  -> pages/cover_page.js     Pag. 1 Portada, cargada bajo demanda
  -> snake/index.js          entrada del juego Snake Gol
     -> engine.js            reglas, estado y bucle de juego
     -> renderer.js          campo, balon, serpiente y efectos
     -> controls.js          teclado, tactil y botones
     -> ranking.js           Top 10 y nombres
     -> config.js            constantes y utilidades
```

Regla de trabajo:

- Una pagina nueva vive en `static/js/pages/nombre_page.js`.
- Sus recursos se registran en `VIEW_STYLES` y `VIEW_SCRIPTS` de `navigation.js`.
- El CSS comun de estilo mecanografiado vive en `static/css/typewriter_system.css`.
- Las formas compartidas viven en `static/css/components/surface_shape.css`.
- El CSS especifico de portada vive en `static/css/cover_hero.css`.
- No duplicar versiones antiguas de una pagina dentro de `quantum_final.js`.
- No meter Snake, Quiz, clasificaciones o La Pena dentro de Portada o Quiniela.

Paginas ya separadas:

```text
pages/ticket_page.js      Pag. 2 Quiniela
live.js                   Pag. 3 Directo
standings.js              Pag. 4 Ligas
pages/games_hub.js        Pag. 5 Juegos
contest.js                Pag. 6 La Pena
quiz.js                   Pag. 7 Quiz
```
