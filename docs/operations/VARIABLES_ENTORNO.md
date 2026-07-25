# Variables de Entorno - Liga de Maestros

## Variables de Sistema
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `ADMIN_EMAILS` | Emails de administradores separados por coma | admin@email.com |
| `API_FOOTBALL_KEY` | Clave API de football-api.com (respaldo) | xxxxxxxxxxxxxxxx |
| `DATA_DIR` | Directorio de datos en producción | /var/data |
| `DB_BACKUP_DIR` | Directorio de backups de la BD | /var/data/backups |
| `DB_PATH` | Ruta completa a la base de datos SQLite | /var/data/LIGA_MAESTROS_PRO.db |

## Variables de APIs Externas
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `HIGHLIGHTLY_API_KEY` | Clave API de Highlightly para datos de fútbol | xxxxxxxxxxxxxxxx |
| `API_FOOTBALL_HOST` | Host de API Football (default: v3.football.api-sports.io) | v3.football.api-sports.io |
| `API_FOOTBALL_DAILY_LIMIT` | Límite diario de llamadas API Football (default: 100) | 100 |
| `API_FOOTBALL_DAILY_RESERVE` | Reserva diaria API Football (default: 10) | 10 |

## Variables de Google OAuth
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `GOOGLE_CLIENT_ID` | ID de cliente Google OAuth | xxxxxxxxxx.apps.googleusercontent.com |
| `GOOGLE_CLIENT_SECRET` | Secreto de cliente Google OAuth | xxxxxxxxxxxxxxxx |

## Variables de Email y Contacto
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `LEGAL_CONTACT_EMAIL` | Email de contacto legal | contacto@liga.com |
| `LEGAL_OWNER_ADDRESS` | Dirección del propietario | Calle Ficticia 123 |
| `LEGAL_OWNER_ID` | ID del propietario | 12345678A |
| `LEGAL_OWNER_NAME` | Nombre del propietario | Juan García |

## Variables de Datos
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `PRODUCTION_SEED_PATH` | Ruta al archivo de seed de producción | /var/data/production_seed.json |

## Variables de Noticias (opcional)
| Variable | Descripción | Default |
|----------|-------------|---------|
| `NEWS_REFRESH_SECONDS` | Segundos entre refrescos de noticias | 900 (15 min) |

## Variables de Aplicación (opcional)
| Variable | Descripción | Default |
|----------|-------------|---------|
| `MAX_DOBLES_PER_TICKET` | Máximo de dobles por quiniela | 14 |
| `MAX_TRIPLES_PER_TICKET` | Máximo de triples por quiniela | 14 |

## Configuración Render.com (automática)
| Variable | Descripción |
|----------|-------------|
| `RENDER` | Detecta si está en Render (automático) |

---

## Notas importantes
1. Las variables con `SECRET` o `KEY` son sensibles - nunca exponerlas
2. `DB_PATH` debe apuntar a un directorio persistente en Render
3. `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` se configuran en Google Cloud Console
4. `HIGHLIGHTLY_API_KEY` se obtiene en highlightly.net
5. `API_FOOTBALL_KEY` se obtiene en api-football.com (respaldo, no siempre necesario)
