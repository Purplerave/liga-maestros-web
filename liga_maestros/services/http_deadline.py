"""GET con tope de tiempo TOTAL para las llamadas de los hilos de fondo.

``requests`` solo limita cada operacion de socket por separado (conectar, cada
lectura): un servidor que contesta a goteo, o una IP que acepta la conexion y
se queda callada entre trozos, puede retener la llamada mucho mas que su
``timeout``. En un hilo de fondo eso es un colector colgado y una jornada sin
resultados. Aqui el cuerpo se lee por trozos y se corta en cuanto se supera el
tope total, de modo que ninguna pasada pueda quedarse esperando a la red.
"""

from __future__ import annotations

import time

import requests

# Reloj del tope (los tests lo sustituyen para simular un servidor a goteo).
_monotonic = time.monotonic


class DeadlineExceeded(requests.Timeout):
    """La respuesta no termino de llegar dentro del tope total."""


def get_with_deadline(
    url,
    *,
    params=None,
    headers=None,
    connect_timeout=5.0,
    read_timeout=10.0,
    total_timeout=20.0,
    max_bytes=8 * 1024 * 1024,
):
    """``requests.get`` que nunca dura (mucho) mas de ``total_timeout``.

    Devuelve un ``requests.Response`` normal con el cuerpo ya leido
    (``.text``, ``.json()`` y ``raise_for_status()`` funcionan igual). Lanza
    ``DeadlineExceeded`` (subclase de ``requests.Timeout``) si se agota el
    tope y ``requests.RequestException`` si el cuerpo supera ``max_bytes``.
    """
    started = _monotonic()
    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=(connect_timeout, read_timeout),
        stream=True,
    )
    iter_content = getattr(response, "iter_content", None)
    if not callable(iter_content) or not hasattr(response, "raw"):
        # Dobles de test (o adaptadores raros) que ya traen el cuerpo leido.
        return response
    chunks = []
    received = 0
    try:
        for chunk in iter_content(chunk_size=64 * 1024):
            if chunk:
                chunks.append(chunk)
                received += len(chunk)
            if received > max_bytes:
                raise requests.RequestException(f"respuesta de {url} supera {max_bytes} bytes")
            if _monotonic() - started > total_timeout:
                raise DeadlineExceeded(f"{url} supera el tope total de {total_timeout:.0f}s")
    except BaseException:
        response.close()
        raise
    response._content = b"".join(chunks)
    response._content_consumed = True
    response.close()
    return response
