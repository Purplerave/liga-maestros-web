/* ==========================================================================
   SCROLL LOCK — Bloquea el scroll del documento mientras haya overlays.

   No existia ninguno en el proyecto. En escritorio el efecto pasa desapercibido
   porque hay raton, pero en tactil arrastrar sobre un modal desplazaba la pagina
   de fondo: el modal se quedaba flotando sobre otro contenido y se perdia el
   sitio. Con la barra de herramientas del navegador en juego, el salto al volver
   a mover la pagina era desconcertante.

   `overscroll-behavior` por si solo no basta: el fondo conserva su propio scroll,
   asi que hay que bloquearlo de verdad.

   Se usa un contador y no un simple toggle porque pueden convivir varios
   overlays (por ejemplo la command palette sobre un modal). Si uno cierra y
   desbloquea mientras el otro sigue abierto, la pagina se queda bloqueada para
   siempre. El ultimo en cerrar es el que restaura.

   Se expone en `window` a proposito: el resto de scripts del proyecto son
   globales planos cargados con `<script defer>`, sin modulos ES.
   ========================================================================== */

let _lmOverlaysAbiertos = 0;

function lmBloquearScroll() {
    const body = document.body;
    if (_lmOverlaysAbiertos === 0) {
        // Se guarda la posicion actual para devolver al usuario al mismo punto:
        // en movil, saltarse el bloqueo al cerrar y aparecer arriba del todo es
        // desconcertante cuando estabas a media quiniela.
        body.dataset.lmScrollY = String(window.scrollY || 0);
        body.style.position = "fixed";
        body.style.top = `-${body.dataset.lmScrollY}px`;
        body.style.left = "0";
        body.style.right = "0";
        body.style.width = "100%";
    }
    _lmOverlaysAbiertos += 1;

    let liberado = false;
    return function liberar() {
        // Una doble llamada no debe decrementar dos veces: dejaria el contador
        // en 0 con otro overlay todavia abierto y dejaria la pagina bloqueada.
        if (liberado) return;
        liberado = true;
        _lmOverlaysAbiertos = Math.max(0, _lmOverlaysAbiertos - 1);
        if (_lmOverlaysAbiertos > 0) return;

        const y = Number(body.dataset.lmScrollY || 0);
        body.style.position = "";
        body.style.top = "";
        body.style.left = "";
        body.style.right = "";
        body.style.width = "";
        delete body.dataset.lmScrollY;
        window.scrollTo(0, y);
    };
}

function lmOverlaysActivos() {
    return _lmOverlaysAbiertos;
}

window.lmBloquearScroll = lmBloquearScroll;
window.lmOverlaysActivos = lmOverlaysActivos;
