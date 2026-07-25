# ADR-0002: JavaScript vanilla sin bundler

## Estado: Aceptado

## Contexto

El frontend de Liga de Maestros es una SPA con 6 vistas (Portada, Quiniela, Directo, Ligas, Juegos, La Peña) renderizada por JS vanilla.

## Decisión

No usar bundler (Webpack, Vite, esbuild). Usar `<script defer>` con módulos globales y `@layer` CSS para especificidad.

## Consecuencias

- **Positivo**: Cero config de build, deploy instantáneo, debugging directo en navegador, sin node_modules pesado.
- **Negativo**: 8 requests JS en portada, sin tree-shaking, sin minificación automática, globals implícitos.
- **Mitigación**: HTTP/2 mitiga los requests múltiples. Para producción, un esbuild opcional (30 líneas) puede concatenar y minificar sin cambiar el flujo de desarrollo.
