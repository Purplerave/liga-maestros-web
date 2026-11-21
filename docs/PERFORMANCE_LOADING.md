# Optimización de carga inicial

## Diagnóstico en el código

- `refreshData()` esperaba a la API de usuario y la de jornada antes de iniciar
  la descarga de los scripts/estilos de la vista. Esa cascada añadía otra fase
  de red a la primera carga. Ahora las tres operaciones empiezan en paralelo,
  manteniendo la barrera antes de hidratar/renderizar la vista.
- La ruta Flask de estáticos no negociaba compresión. Si el proxy frontal no
  la aplica, CSS/JS/SVG viajaban sin comprimir. Ahora negocia gzip para texto
  entre 1 KiB y 1 MiB, con una caché LRU de 128 revisiones de archivo.
- Se mantienen las políticas de caché existentes, los tipos MIME, HEAD,
  revalidación condicional y peticiones Range (estas usan la versión identity).
  Cada representación tiene su ETag y `Vary: Accept-Encoding`.
- No se comprimen HTML ni APIs personalizadas: las respuestas con secretos de
  sesión quedan fuera de esta optimización.

## Medición reproducible

Medido con el cliente de pruebas de Flask, comparando GET sin Accept-Encoding
con GET `Accept-Encoding: gzip`. Son bytes del cuerpo, no tiempos de producción.

| Archivo | Identity | gzip | Reducción |
| --- | ---: | ---: | ---: |
| css/kawaii.css | 90.961 B | 14.303 B | 84,3 % |
| js/pages/cover_page.js | 70.046 B | 20.671 B | 70,5 % |
| js/quantum_final.js | 37.248 B | 10.567 B | 71,6 % |

La compresión solo aporta reducción adicional si el frontal no la realizaba ya.
Los tests fijan equivalencia de contenido, presupuesto de transferencia y
semántica HTTP. Validación local: suite pytest completa, ruff y parser JS.

## Pendiente de comprobar en producción

No se ha medido Lighthouse ni TTFB/LCP en el host público desde este entorno.
Después de desplegar, revisar Network con caché desactivada: los archivos de la
vista deben solaparse con `/api/liga/data` y los estáticos admitir gzip. Comparar
LCP/TTFB en móvil bajo las mismas condiciones de red antes/después.

Hay otros costes no modificados aquí: 25 hojas bloqueantes, descarga de fuentes
externas y el gate de arranque que devuelve 503 mientras termina el primer pase
del collector. Se conserva ese gate para no servir una jornada previa al arranque.
Si el retraso ocurre solo tras reiniciar, revisar los logs de ese collector y el
`Server-Timing` existente antes de cambiar la política de frescura.
