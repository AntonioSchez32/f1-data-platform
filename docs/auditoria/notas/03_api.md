# Auditoría 3: API FastAPI (02/10/2026)

## 1. Alcance y método

Revisado `api/` entero (`main.py`, `config.py`, `deps.py`, `cache.py`, `database.py`, `release.py`, `codes.py`, `schemas.py`, los 7 routers, `Dockerfile`, pruebas y prueba de humo), `render.yaml`, la sección API del README, los jobs de la API en `.github/workflows/ci.yml` y el contrato `web/src/lib/api/openapi.json`. Base usada: la publicada `data-2026-10-01-6.1` (SHA `c7f296865759`, comprobado con `sha256sum`), descargada fuera del repo.

| Comprobación | Resultado |
|---|---|
| `uv run pytest api -q` | 54 passed, 10 skipped (9 de humo sin `F1_SMOKE_DB`, 1 de permisos POSIX en Windows) |
| `F1_SMOKE_DB=<release>/f1.duckdb uv run pytest api/tests/smoke -q` | 8 passed, 1 skipped |
| `ruff check api` / `ruff format --check api` | sin avisos / 25 ficheros formateados |
| Contrato OpenAPI regenerado (`create_app().openapi()`) vs `web/src/lib/api/openapi.json` | idénticos; y el `/openapi.json` de producción es igual (30 rutas) |
| Barrido local con `TestClient` sobre la base publicada: todas las carreras disputadas × 10 subrutas, telemetría, temporadas × 5, pilotos × 4, constructores × 2 (16 130 peticiones) | 0 respuestas 5xx; únicos 404: `standings/progression?type=constructors` de 1950-1957 (esperado, no hay campeonato de constructores) |
| Granos de las tablas que ordenan las respuestas (consultas DuckDB) | sin duplicados en `position_display_order` (resultados, clasificación, standings), `message_seq`, `sample_seq`, claves de vueltas, paradas y pasos por boxes; 89 empates en `/drivers/{id}/results` (coches compartidos), 2 nombres de constructor repetidos (ATS, Lotus) |
| Rankings con rango completo vs `agg_*_career` | pilotos: victorias, podios, poles y vueltas rápidas coinciden (0 discrepancias); constructores: coinciden victorias, podios y vueltas rápidas; **puntos difieren en 12 constructores** (API-01) |
| Producción (`https://f1-data-api-h7c7.onrender.com`, ~20 GET) | `/health` 200 `status: ok`, versión `c7f296865759`, `source: release`, sin error (arranque en frío a las 23:11:54 UTC provocado por la primera petición). **`/races/1126/race-control` 200 (29 KB) y `/races/1126/weather` 200 (44 KB): ya no dan 500**, la API ya sirve la base con las tablas de D1. 404 y 422 correctos; ETag débil + `Cache-Control: public, max-age=600, stale-while-revalidate=86400`; `If-None-Match` → 304; CORS solo para `https://f1-data-platform.vercel.app` (un `Origin` ajeno no recibe `Access-Control-Allow-Origin`); preflight admite `If-None-Match`; `Vary: Accept-Encoding, Origin`; gzip; `/docs` 200 |
| Validación de límites (local) | `offset=99999999999999999999` y un `race_id` de 41 cifras → **500** (API-03) |
| Latencias locales (base publicada) | todo < 40 ms salvo la primera consulta en frío (`/rankings/drivers?limit=500`, 530 ms); mayor respuesta: `/races/{id}/laps` sin filtro, ~400 KB sin comprimir |

## 2. Bien hecho

- **SQL siempre parametrizado.** Los únicos `f-string` interpolan listas cerradas (`DRIVER_METRICS`, `ORDER` como `Literal`, `type` como `Literal`) — `records.py:13-32`, `rankings.py:92`, `seasons.py:176-184`. Probado `category=x' or 1=1--` → `[]`.
- **Solo lectura real:** `duckdb.connect(..., read_only=True)` y se rechaza una base sin esquema gold (`database.py:58-64`).
- **Recarga sin cortes:** conexión nueva, la anterior se retira y se cierra 120 s después (`main.py:85-102`, `database.py:57-82`); reintento a los 10 min tras un fallo (`main.py:76-77`); versión fechada inmutable vía `release_tag` del manifiesto, SHA-256 verificado, ficheros versionados (`release.py:199-232`).
- **Arranque sin GitHub:** copia de respaldo en la imagen y última copia verificada (`database.py:118-134`, `release.py:235-249`), cubierto por pruebas (`test_infrastructure.py:205-262`) y por el job Docker de la CI con una release inexistente (`ci.yml:134`).
- **Contenedor:** usuario no root uid 1000, `/data` suyo, semilla `a+rX`, `HEALTHCHECK` con consulta real, uv fijado (`Dockerfile:7,36-53`).
- **Caché HTTP** completa (ETag por versión+URL, 304 sin ejecutar la consulta, `/health` y errores sin caché) y probada (`test_infrastructure.py:22-46`).
- **Contrato con la web vigilado en la CI** (`ci.yml:171-175`: regenera OpenAPI y tipos y falla si hay diff).
- **Prueba de humo** antes de publicar con control de regresión de filas (`smoke/test_snapshot_smoke.py`).
- Casos de coches compartidos tratados explícitamente (ganador único `seasons.py:27-31`, tramos por dorsal `races.py:150-168`, podios de constructor por coche `rankings.py:181-182`) y probados (`test_shared_cars.py`).

## 3. Hallazgos

| ID | Gravedad | Título | Evidencia | Impacto | Propuesta | Bloque |
|---|---|---|---|---|---|---|
| API-01 | media | `points` de constructores significa cosas distintas según el endpoint (verificado) | `records.py:31` mapea `points` → `race_points` (solo carreras, `agg_constructor_career.sql:31`); `/records/drivers` usa `points` con sprints (`agg_driver_career.sql:69`) y `/rankings/constructors` suma todas las sesiones (`rankings.py:188-191`). Consulta sobre la release: Ferrari 11 779,77 (`/records/constructors?metric=points`) vs 12 001,77 (`/rankings/constructors?order_by=points`); 12 constructores difieren. El docstring de `rankings.py:3-4` afirma que con el rango completo coinciden. | Dos cifras de «puntos» para el mismo equipo en la API pública; contradice la nota DBT-7 de SIGUIENTES_PASOS («hoy ya coinciden»). La web no usa `/records` (usa `/rankings`), así que no se ve en la web. | Unificar: `points` = carrera + sprint en `agg_constructor_career` (o exponer `race_points` y `points` por separado) y añadir una prueba que compare `/records` y `/rankings` con rango completo. | C3 (o con DBT-7) |
| API-02 | baja | La ETag no depende de la versión del código (lectura) | `cache.py:334-336`: `W/"{version_id}-{sha1(url)}"`. | Tras desplegar un cambio de forma de respuesta sin datos nuevos, un cliente que revalida recibe 304 y conserva el cuerpo antiguo hasta la siguiente publicación de datos. La web usa la caché de Next (`client.ts:64-66`), no la ETag, así que el riesgo es para clientes directos. | Incluir en la ETag un identificador del build (p. ej. `RENDER_GIT_COMMIT` o `app.version`). | nuevo bloque (o W1) |
| API-03 | baja | Enteros fuera de rango dan 500 en vez de 422 (verificado) | `TestClient` sobre la release: `/drivers?offset=99999999999999999999` → 500; `/races/99999999999999999999999999999999999999999/laps` → 500. `drivers.py:34`, `constructors.py:156` (`offset` sin `le`), parámetros `race_id`/`season` sin cotas. | Error 500 registrado como excepción; ruido en logs, sin riesgo de datos. | `le=` razonables (`offset ≤ 10 000`, `season` 1950-2100, `race_id` ≤ 2^31) o un manejador de `duckdb.ConversionException` → 422. | nuevo bloque (menor) |
| API-04 | baja | Orden no totalmente determinista en algunos listados (verificado en datos / lectura) | `/drivers/{id}/results` ordena por `season, round, session_type` (`drivers.py:107`): 89 combinaciones piloto-carrera-sesión con dos filas (coches compartidos) quedan en orden arbitrario. `constructor_seasons` usa `list(distinct {...})` sin `order by` (`constructors.py:215`). `/constructors` y `/rankings/*` desempatan por `name`, con nombres repetidos (ATS, Lotus). | Pequeñas variaciones de orden entre ejecuciones/versiones de DuckDB; con `offset` puede repetir u omitir filas en empates exactos. | Añadir desempate por id (`driver_number`, `constructor_id`, `driver_id`) y `order by` dentro de `list(...)`. | nuevo bloque (menor) |
| API-05 | baja | Fechas UTC sin zona en `race-control` y `weather` (verificado) | Producción: `"utc":"2025-03-16T03:15:05"` (sin `Z`); `schemas.py:249,276` declara `datetime` (OpenAPI `format: date-time`, que en RFC 3339 exige desfase). | Un cliente JS que haga `new Date(utc)` la interpreta como hora local. La web no usa hoy el campo. | Devolver `timestamptz` o serializar con `Z` (p. ej. `AwareDatetime` o `message_utc at time zone 'UTC'`). | D2/D3 si se usan en la web; si no, nuevo bloque |
| API-06 | baja | La búsqueda trata `%` y `_` como comodines (verificado) | `/drivers?search=__` devuelve todos los pilotos (`drivers.py:40`, `constructors.py:162`). | Sin riesgo de seguridad (parametrizado); resultados sorprendentes. | Usar `contains(...)` o escapar con `ESCAPE`. | nuevo bloque (menor) |
| API-07 | baja | `drivers=,,,` en `/laps` devuelve `[]` con 200 (verificado) | `split_ids` devuelve `[]` (no `None`) y el filtro excluye todo (`deps.py:310-317`, `races.py:136`). | Inconsistente con `/telemetry`, que da 404. | Tratar lista vacía como «sin filtro» o 422. | nuevo bloque (menor) |
| API-08 | baja | README sin los endpoints `/rankings/*` (lectura) | Tabla de `README.md:239-245`; la web los usa (`web/src/app/[lang]/records/page.tsx:38-39`). | Documentación incompleta de la API (sí aparecen en `/docs`). | Añadir la fila. | F0 (documentación) |
| API-09 | baja | `GET /constructors` (listado y búsqueda) sin prueba (lectura) | Ninguna prueba llama a `/constructors` ni `/constructors?search=` (grep en `api/tests`). | Una regresión en ese SQL no la detectaría la CI (sí la e2e si la web lo usa). | Prueba mínima de búsqueda y paginación. | nuevo bloque (menor) |
| API-10 | observación | Sin límites de DuckDB ni de peticiones en Render free (lectura) | `database.py:58` no fija `memory_limit` ni `threads`; no hay limitación de peticiones. | Con 512 MB y 0,1 CPU, ráfagas de consultas en frío (la primera de `/rankings` tarda ~0,5 s en local) podrían saturar; Cloudflare de Render amortigua poco (`cf-cache-status: DYNAMIC`). | `SET memory_limit='256MB', threads=2` al abrir; si hiciera falta, caché de respuestas en CDN. | nuevo bloque (si se observa) |
| API-11 | observación | Imagen con el binario `uv` y `README.md` en la capa final (lectura) | `Dockerfile:11,20`. | ~40 MB extra; sin impacto funcional. | Etapa de construcción separada (opcional). | — |

## 4. Promesas del plan no cumplidas o desviadas (Fase 4)

Se cumple lo esencial: solo lectura, descarga al arrancar (más copia de respaldo y refresco), Pydantic en todas las respuestas, `Cache-Control` + ETag por versión, CORS limitado al dominio de Vercel, OpenAPI en `/docs`, pytest sobre DuckDB de muestra (parquets en `api/tests/fixtures`) y Docker en Render. Desviaciones de nombres (todas a mejor y reflejadas en README y en el contrato OpenAPI, pero no registradas como decisión):

| Plan | Implementado |
|---|---|
| `/seasons/{year}/standings` | `/seasons/{año}/standings/drivers`, `…/constructors`, `…/progression` |
| `/drivers/{id}/h2h` | `/drivers/{id}/teammates` |
| `/records?entity=driver\|constructor` | `/records/drivers`, `/records/constructors` y además `/rankings/*` filtrable por temporadas |
| `/circuits/map` | `/circuits?season_from&season_to` |
| `/telemetry/{race}/{driver}` | `/races/{id}/telemetry?drivers=a,b` (1-4 pilotos) |

Extras no previstos: `/results`, `/qualifying`, `/pit-lane-passes`, `/race-control`, `/weather` (D1), `/quality`, `/health` detallado.

## 5. Dudas

- No pude verificar el comportamiento del refresco cada 6 h en producción: el plan free de Render duerme el servicio tras inactividad y cada arranque en frío ya descarga la versión vigente (en mi visita el proceso acababa de arrancar), así que el refresco periódico apenas llega a ejecutarse; el mecanismo está probado solo en pruebas unitarias.
- No medí el tiempo de arranque en frío en Render ni el consumo de memoria del contenedor.
- No ejecuté `docker build` en local (sí existe el job en la CI, `ci.yml:107-145`); no comprobé la última ejecución de ese job.
- Si DuckDB detecta los límites de CPU del contenedor de Render (afecta a API-10).
