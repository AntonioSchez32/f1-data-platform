# 07 · Revisión de código e infraestructura: mejoras propuestas

Revisión de solo lectura del repositorio `f1-data-platform` a 29/09/2026 (commit `cceddd3`, rama
`main`). No se ha modificado ningún fichero salvo esta nota.

## 1. Método y estado de partida

Qué se ha hecho:

- Lectura completa de `ingestion/`, `api/`, `scripts/`, `tests/`, `api/tests/`, los workflows,
  `render.yaml`, `api/Dockerfile`, los modelos dbt intermedios y *marts*, macros, seeds y YAML, y
  los ficheros clave de `web/` (cliente de la API, `proxy.ts`, layout, páginas de carrera, gráficos).
- Ejecución de linters y pruebas:
  - `ruff check .` y `ruff format --check .`: sin errores (ruff 0.16.9, 50 ficheros).
  - `pytest`: **40 pruebas superadas en 2,3 s**.
  - `npm run lint` (ESLint) y `tsc --noEmit`: sin errores.
  - `npm audit --omit=dev`: **0 vulnerabilidades**. `npm outdated`: eslint 9→10,
    typescript 5.9→7.0, react/react-dom 19.2.8→19.3.0, @types/node 20→26.
- Medición de los endpoints con `TestClient` contra `dist/f1.duckdb` (la base de datos que se
  publica), 5 repeticiones, mediana (ver §4).
- Consultas de integridad contra `data/gold/f1.duckdb` (solo lectura): unicidad de claves,
  cruces por dorsal, estados de numeración y relaciones huérfanas.
- Tiempo de `dbt build` según `transform/target/run_results.json`: **21,7 s** en total
  (`int_laptimes` 6,7 s, `int_formula1db_laps` 4,2 s, `fact_laptimes` 2,6 s).

Puntos fuertes que conviene conservar: consultas siempre parametrizadas (las pocas
interpolaciones usan listas cerradas); escritura atómica de Parquet; `tarfile` con `filter="data"`;
descarga verificada por SHA-256 y versionada por nombre; ETag + `Cache-Control`; GZip; CORS
restringido a GET; usuario no root y `HEALTHCHECK` en la imagen; contrato OpenAPI comprobado en la
CI (`git diff --exit-code`); pruebas de accesibilidad con axe; seeds de correcciones que se
desactivan solas cuando F1DB corrige el dato.

Leyenda: **Esfuerzo** S (< 2 h), M (medio día a 2 días), L (> 2 días). **Prioridad** alta, media o
baja.

## 2. Hallazgos por área

### 2.1 Ingesta (`ingestion/`)

**ING-1. Extracción de F1DB no atómica.** `ingestion/f1db_loader.py:42-59`.
Si `zf.extract("f1db.db", ...)` se interrumpe, queda un `f1db.db` truncado y en la siguiente
ejecución `db_path.exists()` (línea 45) lo da por bueno para siempre (el directorio lleva el tag
de la release).
*Impacto:* bronze construido sobre una SQLite corrupta; el error aparece más tarde y es críptico.
*Propuesta:* extraer a un temporal y renombrar; comprobar la integridad.
```python
tmp = target_dir / "f1db.db.part"
with zipfile.ZipFile(zip_path) as zf, zf.open("f1db.db") as src, open(tmp, "wb") as dst:
    shutil.copyfileobj(src, dst, 1 << 20)
with sqlite3.connect(tmp) as con:
    assert con.execute("pragma quick_check").fetchone()[0] == "ok"
os.replace(tmp, db_path)
```
Esfuerzo S · Prioridad media.

**ING-2. Descargas sin reintentos.** `ingestion/f1db_loader.py:25-39,51-55`.
`requests.get` sin `Retry`; un 502 de GitHub hace fallar el pipeline entero. `next(a for a in
release["assets"] ...)` (línea 34) lanza `StopIteration` si falta el asset, con un mensaje
ininteligible.
*Propuesta:* `requests.Session` con `HTTPAdapter(max_retries=Retry(total=5, backoff_factor=2,
status_forcelist=[429, 500, 502, 503, 504]))` y `next(..., None)` con error explícito.
Esfuerzo S · Prioridad media.

**ING-3. Sustitución del directorio bronze de F1DB no atómica.** `ingestion/f1db_loader.py:84-86`.
`rmtree(out_dir)` y después `rename(tmp_dir)`: entre ambos no hay directorio, y en Windows el
`rename` falla si algo tiene abierto un Parquet (DuckDB, Power BI).
*Propuesta:* `out_dir → out_dir.old`, `tmp_dir → out_dir`, borrar `.old`; si el segundo paso
falla, restaurar. Esfuerzo S · Prioridad baja.

**ING-4. Carreras de FastF1 «congeladas» tras la primera carga.** `ingestion/fastf1_loader.py:153-157`.
Una carrera se da por cargada si existe su Parquet. Con 6 h de margen (línea 121) FastF1 a veces
publica datos incompletos que no se vuelven a pedir salvo con `--force`. Además `_load_race`
escribe `laps` y `results`, pero solo se comprueba `laps`: si falta `results` nunca se regenera.
*Propuesta:* recargar siempre las dos últimas carreras disputadas (o las que tengan menos vueltas
que el resultado oficial de F1DB) y añadir `results` a `kinds`.
Esfuerzo S · Prioridad media.

**ING-5. Errores sin traza.** `ingestion/fastf1_loader.py:170-172` usa `log.error("... %s", exc)`;
usar `log.exception` para conservar la traza en los logs de Actions. Esfuerzo S · Prioridad baja.

**ING-6. Desfase entre FastF1 y F1DB los lunes.** `pipeline.yml:181` y
`transform/models/marts/core/dim_race.sql:10-14`.
El pipeline corre una sola vez (lunes 06:00 UTC). Si F1DB aún no ha publicado la release con el GP
del domingo, entran las vueltas de FastF1 (`fastf1_fill`) pero la carrera queda
`is_completed = false` y la web la muestra como «próxima» durante una semana.
*Propuesta:* un segundo `cron` ligero (p. ej. diario) que solo compare el tag de F1DB y el
calendario de FastF1 y lance el pipeline si hay algo nuevo; o repetir el martes y el miércoles.
Esfuerzo S · Prioridad media.

**ING-7. Rutas interpoladas en SQL.** `ingestion/f1db_loader.py:70`, `ingestion/snapshot.py:75,114`,
`scripts/make_api_fixture.py:38`, `api/tests/conftest.py:22`. Las rutas se meten entre comillas
simples: una ruta con `'` rompe la sentencia (no es un riesgo de seguridad, las rutas son
locales). *Propuesta:* un helper `sql_literal(path) = "'" + path.as_posix().replace("'", "''") + "'"`.
Esfuerzo S · Prioridad baja.

**ING-8. Restos al fallar la exportación.** `ingestion/snapshot.py:100-122`: si falla un `COPY`,
queda el directorio `.d` a medias. Usar `tempfile.TemporaryDirectory(dir=out.parent)`.
Esfuerzo S · Prioridad baja.

**ING-9. Rutas fijas al equipo del autor.** `ingestion/config.py:20` y
`ingestion/ergast_loader.py:20` apuntan a `PROJECT_ROOT.parent / ...`. Está documentado, pero
convendría leerlas de variables de entorno (`F1_LEGACY_CSV_DIR`, `F1_ERGAST_ZIP`).
Esfuerzo S · Prioridad baja.

### 2.2 dbt y modelo de datos (`transform/`)

**DBT-1. Grano de las vueltas y consumidores que lo ignoran.** Datos + `api/app/routers/races.py:99-156`.
`fact_laptimes` tiene **85 filas repetidas en (race_id, driver_id, lap_number)**: pilotos que
condujeron dos coches en la misma carrera (Harry Schell 1955, Bob Scott y Jimmy Davies en
Indianápolis 1954, Stirling Moss 1961…). El test de unicidad incluye `driver_number`, así que el
modelo es coherente, pero:
- `Lap` y `Stint` (`api/app/schemas.py:163-192`) no devuelven `driver_number`, así que el cliente
  no puede separar los dos coches;
- `/stints` particiona la ventana por `driver_id` (`races.py:139,143`): mezcla las vueltas de los
  dos coches y calcula tramos erróneos;
- la web agrupa por `driver_id` (`web/src/app/[lang]/races/[id]/lap-chart/page.tsx:28,37`) y la
  última fila pisa a la primera.
*Propuesta:* añadir `driver_number` a `Lap` y `Stint`, particionar `/stints` por
`(driver_id, driver_number)` y agrupar en la web por esa pareja.
Esfuerzo S-M · Prioridad media.

**DBT-2. Dorsales tomados de todas las sesiones.** `transform/models/intermediate/int_driver_race_numbers.sql:3-12`.
El modelo usa `race_data` completo, incluidos los libres. Resultado: **294 parejas
(carrera, dorsal) con dos pilotos**, casi todas de 2010-2013 (pilotos de pruebas del viernes con
el dorsal del titular; p. ej. carrera 897, #23: Chilton y Rodolfo González). Hoy no causa daño
porque FastF1 empieza en 2018 y `ergast_fill` filtra por el resultado oficial, pero
`int_fastf1_laps.sql:35-37` y `fact_quali_telemetry.sql:12-14` cruzan solo por
`(race_id, driver_number)`: si vuelve a pasar en la era FastF1, las vueltas se duplican sin aviso.
*Propuesta:* limitar a `RACE_RESULT`, `QUALIFYING_RESULT` y `SPRINT_*`, o priorizar con
`qualify row_number() over (partition by race_id, driver_number order by <sesión de carrera
primero>) = 1` en una vista para FastF1; añadir `unique_combination [race_id, driver_number,
lap_number]` a `int_fastf1_laps` y `[race_id, driver_id, distance_m]` a `fact_quali_telemetry`.
Esfuerzo S · Prioridad media.

**DBT-3. Empates no deterministas y estado `consistent` demasiado laxo.**
`transform/models/intermediate/int_lap_numbering.sql:402-405,419,441,480`.
`arg_min`/`arg_max` no desempatan (un desfase de +1 y otro de −1 con la misma distancia, o dos
desfases con el mismo número de casos), así que la salida puede variar entre ejecuciones. Además
`consistent` solo exige `distinct_offsets = 1 and common_offset = 0`, sin `min_share >= 0.8`: hay
**2 carreras marcadas `consistent` con una cuota dominante < 0,8**. Solo afecta a la etiqueta
(`applied_lap_shift` sí exige 0,8), pero la etiqueta se publica en `fact_laptimes`.
*Propuesta:* `arg_max(lap_offset, (cases, -abs(lap_offset)))` y exigir `min_share >= 0.8` en
`consistent` (lo que no llegue, `inconsistent`). Esfuerzo S · Prioridad baja-media.

**DBT-4. Corrección de tiempos acumulados por dorsal.** `int_laptimes.sql:87-91`.
La suma acumulada va por `(race_id, driver_number)`; en coches compartidos mezcla pilotos. Hoy solo
hay una carrera con corrección (2024), pero la regla es general. Particionar por
`(race_id, driver_id, driver_number)`. Esfuerzo S · Prioridad baja.

**DBT-5. Vueltas sin tiempo en formula1db que las otras dos fuentes sí tienen.**
`int_laptimes.sql:139-143,158-162`. Si `lap_time_ms` es nulo y FastF1 y Ergast coinciden, la
mayoría no se aplica (`abs(null)`) y la vuelta queda sin tiempo y `single_source`. Añadir la rama
«rellenada por mayoría». Esfuerzo S · Prioridad baja.

**DBT-6. Equipo principal no determinista.** `transform/models/marts/metrics/agg_driver_season.sql:20`.
`mode(constructor_id)` no desempata cuando un piloto corre el mismo número de carreras con dos
equipos. Usar `arg_max(constructor_id, (carreras, última_ronda))`. Esfuerzo S · Prioridad baja.

**DBT-7. Definiciones de récords duplicadas entre dbt y la API.**
`api/app/routers/rankings.py:39-77,93-133` frente a `agg_driver_career.sql` y
`agg_constructor_career.sql`. Hoy coinciden (comprobado: los podios por coche dan lo mismo con
`race_id || driver_number` y con `(race_id, position_number)`), pero hay dos implementaciones de
las mismas reglas (inscripciones, salidas, podios por coche, vueltas rápidas por piloto).
*Propuesta:* modelos `agg_driver_season_stats` y `agg_constructor_season_stats` (una fila por
entidad y temporada, con las mismas definiciones), y que `/rankings` solo haga
`sum(...) where season between ? and ?`. Los agregados de carrera deportiva serían la suma sin
filtro. Una definición, consultas más simples y más rápidas. Esfuerzo M · Prioridad media.

**DBT-8. Cobertura de pruebas de dbt desigual.**
- Los 10 modelos intermedios no tienen YAML (ni descripciones ni tests); staging tampoco.
- Solo hay 2 `unit_tests` (`int_formula1db_laps`, `int_formula1db_race_alignment`,
  en `models/quality/_quality__models.yml:33`). La lógica más delicada no tiene pruebas unitarias:
  la mayoría y el recálculo de posiciones de `int_laptimes`, la regla A6, `int_lap_numbering`,
  `int_tyre_compound_mapping` y la macro `parse_duration_ms`.
- Faltan tests de grano en `fact_pit_stops`, `fact_quali_telemetry`, `fact_driver_standing` y
  `fact_constructor_standing`.
- Las *sources* no tienen `freshness` (se podría avisar si F1DB lleva más de N días sin
  actualizarse durante la temporada).
*Propuesta:* un `unit_test` de 4-6 filas por regla (el formato ya se usa en el proyecto) y
`unique_combination` en los hechos que faltan. Esfuerzo M · Prioridad **alta** (es la parte con
más lógica y menos red).

**DBT-9. Relación huérfana en el almacén local.** `silver.int_formula1db_laps_validated`
(1,2 M filas) existe en `data/gold/f1.duckdb` pero no corresponde a ningún modelo: es un resto de
una versión anterior. No llega a la API (`build_api_database` copia solo `gold` y `qa_summary`),
pero ocupa espacio y confunde. Borrarla y añadir un script que liste relaciones sin nodo dbt.
Esfuerzo S · Prioridad baja.

**DBT-10. Materializaciones y almacenamiento.** El build tarda 22 s, así que los modelos
incrementales no compensan. `int_laptimes` y `fact_laptimes` duplican 1,27 M filas;
`int_laptimes` podría ser `view`/`ephemeral` (o `fact_laptimes` absorberla). Ordenar
físicamente `fact_laptimes` por `race_id` apenas mejora (medido: 10,7 → 9,7 ms en la consulta de
`/laps`), así que no es prioritario. Esfuerzo S · Prioridad baja.

**DBT-11. Tipos.** `dim_race.race_time_utc` es `VARCHAR` y nulo en muchas carreras antiguas;
exponer un `race_start_utc TIMESTAMPTZ` calculado facilitaría calendarios y zonas horarias en la
web. Esfuerzo S · Prioridad baja.

**DBT-12. Estilo SQL sin comprobar.** No hay `sqlfluff` (u otro linter SQL) ni en pre-commit ni en
la CI; con 60 modelos convendría fijar el estilo (dialecto duckdb, plantilla dbt).
Esfuerzo S · Prioridad baja.

### 2.3 API (`api/`)

**API-1. Arranque en frío frágil y lento en Render.** `api/app/main.py:56-62`,
`api/app/release.py:93-118`, `render.yaml:8`, `api/Dockerfile:24-29`.
El plan gratuito duerme la API a los 15 min y su disco es efímero: cada arranque descarga de nuevo
**54 MB** y calcula su SHA-256 antes de servir la primera petición. El README habla de unos 30 s,
pero la descarga los alarga. Si GitHub falla justo entonces, `resolve_database` lanza una excepción
y la API no arranca (bucle de reinicios).
*Propuesta:* (a) si falla la descarga y hay alguna copia en `data_dir`, arrancar con ella y
reintentar en segundo plano; (b) disco persistente o plan de pago cuando haya tráfico real;
(c) en la web, timeout y reintento (WEB-2) para no depender del arranque.
Esfuerzo M · Prioridad alta.

**API-2. Descarga de la release sin reintentos.** `api/app/release.py:38-50,104-116`.
No hay reintentos ni *backoff*. El temporal tiene nombre fijo (`f1-<sha>.download`): dos procesos
(varios *workers* de uvicorn) escribirían el mismo fichero. La descarga no es reanudable.
*Propuesta:* 3 intentos con espera exponencial y `tempfile.NamedTemporaryFile(dir=data_dir,
delete=False)`. Esfuerzo S · Prioridad media.

**API-3. Publicación no atómica de la release.** `.github/workflows/pipeline.yml:267-268`.
`gh release upload --clobber` borra y vuelve a subir cada asset. Mientras tanto la API puede leer
el manifiesto nuevo con la base antigua (se detecta por el SHA y se reintenta 6 h después) o no
encontrar el asset (404).
*Propuesta:* subir `manifest.json` en un último comando aparte y, mejor aún, releases inmutables
por versión (`data-2026-09-28-<sha>`) con `data-latest` apuntando a la última (ver CI-6).
Esfuerzo S-M · Prioridad alta.

**API-4. Cierre de la conexión antigua por tiempo, no por uso.** `api/app/database.py:76-94`,
`api/app/main.py:44-47`.
Tras el cambio de versión, la conexión anterior se cierra a los 120 s aunque haya consultas en
curso; una consulta que llegue tarde daría `Connection already closed` (500). Hoy es improbable
(todas las consultas tardan menos de 60 ms), pero la garantía no existe.
*Propuesta:* contador de uso por conexión (un *context manager* que incremente y decremente) y
cerrar cuando llegue a 0. Esfuerzo S · Prioridad baja.

**API-5. ETag calculada antes de la consulta.** `api/app/cache.py:32-40`. Si el cambio de versión
cae entre el cálculo y la consulta, una respuesta con datos nuevos sale con la ETag antigua y se
cachea (600 s + `stale-while-revalidate` de 1 día). Guardar la versión en `request.state` y usar
esa misma conexión en la consulta. Esfuerzo S · Prioridad baja.

**API-6. Validación de parámetros mejorable.** Comprobado con peticiones reales:
- `LIKE` sin escapar: `/drivers?search=%25%25` y `search=__` devuelven todos los pilotos
  (`drivers.py:40`, `constructors.py:29`). Usar
  `contains(strip_accents(lower(c.name)), strip_accents(lower(?)))`.
- `season_from > season_to` devuelve `[]` en vez de 422 (`rankings.py:33-34`, `circuits.py:14-15`).
- `?drivers=,,,` produce una lista vacía y responde `[]` (`deps.py:21-28`): devolver `None` o 422.
- Límites incoherentes: `/drivers` admite `limit ≤ 1000`, `/constructors` ≤ 500.
- Temporadas sin rango (`seasons.py:65`): añadir `Path(ge=1950, le=2100)`.
Esfuerzo S · Prioridad media-baja.

**API-7. `ORDER BY` interpolado y rango sin empates.** `api/app/routers/rankings.py:74,79,130,135`.
`order by {order_by}` es seguro porque `Literal` valida el valor, pero depende de esa validación;
mapear a columnas con un diccionario, como hace `records.py:13-32`. `rank` es el índice de la fila,
así que no respeta empates, a diferencia de `/records`, que usa `rank()`.
Esfuerzo S · Prioridad baja.

**API-8. Rendimiento y tamaño de las respuestas.** Ver §4. Todo responde en menos de 60 ms en
local, pero:
- `/races/{id}/laps` pesa 455 KB en Baréin 2024 (1 129 filas) y **1,9 MB en Indianápolis 1954**
  (4 828 filas); con gzip, 27 KB y 19 KB.
- La mayor parte del tiempo es validación y serialización de Pydantic (la consulta de `/laps`
  tarda unos 10 ms y el endpoint 34 ms).
*Propuesta:* formato columnar opcional (`?format=columns`, listas paralelas como ya hace
`/telemetry`) y selección de columnas (`fields=`); `ORJSONResponse` para listas grandes.
Esfuerzo M · Prioridad baja.

**API-9. `BaseHTTPMiddleware`.** `api/app/cache.py:22`. Añade coste por petición y tiene
limitaciones conocidas (tareas en segundo plano, *streaming*). Reescribirlo como middleware ASGI
puro (unas 30 líneas). Esfuerzo S · Prioridad baja.

**API-10. Sin límite de peticiones ni cabeceras de seguridad.** `api/app/main.py:90-98`,
`api/Dockerfile:36`.
La API es pública; en Render free (0,1 CPU) una ráfaga de `/races/{id}/laps` la satura. No envía
`X-Content-Type-Options: nosniff` ni `Referrer-Policy`. `--forwarded-allow-ips='*'` hace que
`X-Forwarded-For` sea falsificable: hay que tenerlo en cuenta antes de limitar por IP.
*Propuesta:* `slowapi` (p. ej. 120 peticiones/min por IP) tomando la IP de la cabecera que fija
Render, o un CDN delante (Cloudflare) aprovechando que las respuestas ya son cacheables; cabeceras
básicas en un middleware. Esfuerzo S-M · Prioridad media.

**API-11. Observabilidad mínima.** `api/app/main.py:49-50,136`.
Solo hay `logging.basicConfig` y el log de accesos de uvicorn. Si el refresco falla una y otra vez,
solo queda un `log.exception` que nadie ve. `/health` (`main.py:102-115`) no toca la base de datos.
*Propuesta:* `/health` con `select 1`, `last_refresh_at` y `last_refresh_error`; logs en JSON con
id de petición y latencia; monitor externo (UptimeRobot o un workflow programado que haga
`curl /health` y abra un *issue* si falla). Esfuerzo S-M · Prioridad media.

**API-12. Configuración sin validar.** `api/app/config.py:38,42`: un valor no numérico en
`F1_API_REFRESH_HOURS` rompe el arranque con un `ValueError` poco claro. `pydantic-settings`
valida y documenta. Esfuerzo S · Prioridad baja.

**API-13. Detalles menores.** `database.py:96-98`: `query_one` hace `fetchall`; `races.py:225-226`
reordena en Python lo que puede ordenar SQL (`order by list_position(?, driver_id)`); versión
fija `"1.0.0"` en `main.py:80` (tomarla de `importlib.metadata`). Esfuerzo S · Prioridad baja.

Seguridad: **no se han encontrado inyecciones SQL**. Todas las entradas del usuario van como
parámetros `?`; las interpolaciones (`rankings.py`, `records.py`, `seasons.py:186-205`) usan
valores de listas cerradas validadas por FastAPI.

### 2.4 Web (`web/`)

**WEB-1. Sin cabeceras de seguridad.** `web/next.config.ts:1-7` está vacío. No hay CSP,
`X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` ni `frame-ancestors`, y se envía
`X-Powered-By: Next.js`. Una CSP con *nonce* obliga a renderizar en dinámico y rompe el ISR, así
que conviene una CSP estática.
```ts
const csp = [
  "default-src 'self'", "script-src 'self' 'unsafe-inline'", "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:", "font-src 'self'", "connect-src 'self'",
  "frame-ancestors 'none'", "object-src 'none'", "base-uri 'self'", "form-action 'self'",
].join("; ");
const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "Content-Security-Policy", value: csp },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ]}];
  },
};
```
Esfuerzo S · Prioridad alta (mucho valor por poco trabajo).

**WEB-2. `fetch` sin timeout ni reintento.** `web/src/lib/api/client.ts:33-38`.
Con la API dormida, la función de servidor espera hasta agotar su límite de duración y acaba en
`error.tsx`. *Propuesta:* `signal: AbortSignal.timeout(20_000)` y un reintento con espera corta
para 502/503/504 y errores de red. Esfuerzo S · Prioridad alta.

**WEB-3. Dirección de la API por defecto en producción.** `client.ts:7`. Si falta `F1_API_URL` en
Vercel, la web intenta `127.0.0.1:8000` y falla en silencio. Lanzar un error en el arranque si
`process.env.VERCEL_ENV === "production"` y no está definida. Esfuerzo S · Prioridad baja.

**WEB-4. Códigos de piloto ambiguos.** `web/src/lib/format.ts:40-45` deduce el código de las
tres primeras letras del apellido del identificador. En la misma carrera, «michael-schumacher» y
«ralf-schumacher» dan los dos `SCH` (1997-2006), y «nico-rosberg» y «pedro-de-la-rosa» los dos
`ROS` (2010-2012). Afecta al gráfico de posiciones y a la tabla de ritmo
(`lap-chart/page.tsx:42`, `pace/page.tsx:135,190`).
*Propuesta:* exponer `abbreviation` de `dim_driver` (F1DB tiene MSC/RSC) en `RaceResult` y usarla,
con la heurística solo como último recurso. Esfuerzo S · Prioridad media.

**WEB-5. Tamaño del bundle.** `.next/static` ocupa 1,6 MB; el chunk mayor, **663 KB (220 KB con
gzip)**, es ECharts (núcleo, 4 tipos de gráfico, 6 componentes y el renderizador SVG,
`web/src/components/charts/echart.tsx:3-28`) y se carga en 10 páginas.
*Propuesta:* medir con el analizador de bundles; cargar `EChart` con `next/dynamic` cuando entre en
pantalla (la tabla alternativa ya da el contenido sin JavaScript); registrar cada tipo de gráfico
solo en el componente que lo usa. Esfuerzo M · Prioridad media.

**WEB-6. El gráfico se recrea en cada cambio.** `web/src/components/charts/echart.tsx:133-144`.
Cada cambio de `build` (p. ej. marcar una casilla en `LapTimesChart`) hace `dispose()` + `init()`:
se pierde el zoom y se repite la animación. Mantener la instancia en un `ref` y llamar a
`chart.setOption(option, { notMerge: true })`. Esfuerzo S · Prioridad baja.

**WEB-7. Lógica en las páginas y sin pruebas unitarias.** Las funciones estadísticas `density` y
`quantile` están en `web/src/app/[lang]/races/[id]/pace/page.tsx:11-30`; `format.ts` y
`proxy.ts:6-17` (negociación de idioma; `Number(q)` puede dar `NaN` y desordenar la lista) tampoco
tienen pruebas. Solo hay 8 pruebas Playwright (navegación y axe).
*Propuesta:* mover las funciones a `lib/stats.ts` y añadir Vitest para las funciones puras.
Esfuerzo S-M · Prioridad media.

**WEB-8. Dependencias.** `@types/node` ^20 mientras la CI usa Node 24 (`ci.yml:125`): alinear a
^24 y declarar `engines`. Planificar eslint 10 y TypeScript 7 (cambio mayor). Esfuerzo S ·
Prioridad baja.

Accesibilidad: no se han visto problemas claros. Hay enlace para saltar al contenido,
`role="img"` con tabla alternativa en cada gráfico, paleta Okabe-Ito con tipo de línea y marcador,
`prefers-reduced-motion`, fechas con `T12:00:00Z` para evitar el día anterior por zona horaria, y
pruebas axe en claro y oscuro.

### 2.5 CI/CD e infraestructura

**CI-1. Acciones sin fijar a SHA.** `ci.yml:23-24,67,123,168`, `pipeline.yml:210,212,284,290,311`.
Todas van por etiqueta mayor (`@v5`, `@v6`, `@v4`…). El pipeline tiene `contents: write`: una
acción comprometida podría reescribir las releases de datos.
*Propuesta:* fijar a SHA con comentario de versión (`uses: actions/checkout@<sha> # v5.0.0`) y
dejar que Dependabot las actualice. Esfuerzo S · Prioridad alta.

**CI-2. Acciones en Node 20.** `actions/upload-artifact@v4` (`ci.yml:67,168`,
`pipeline.yml:290`), `actions/upload-pages-artifact@v3` (usa `upload-artifact@v4` por dentro,
`pipeline.yml:284`), `actions/deploy-pages@v4` (`pipeline.yml:311`) y, según su versión,
`astral-sh/setup-uv@v6` usan Node 20. GitHub lo ha retirado como runtime por defecto en 2026: primero
avisos y después fallos. Subir a las mayores con Node 24 (hay que comprobar la última en cada
repositorio). `checkout@v5` y `setup-node@v5` ya usan Node 24. Esfuerzo S · Prioridad alta.

**CI-3. Sin Dependabot ni Renovate.** `.github/` solo contiene `workflows/`.
```yaml
# .github/dependabot.yml
version: 2
updates:
  - { package-ecosystem: github-actions, directory: "/", schedule: { interval: weekly } }
  - { package-ecosystem: uv, directory: "/", schedule: { interval: weekly } }
  - { package-ecosystem: npm, directory: "/web", schedule: { interval: weekly },
      groups: { minor: { update-types: [minor, patch] } } }
  - { package-ecosystem: docker, directory: "/api", schedule: { interval: monthly } }
```
Esfuerzo S · Prioridad alta.

**CI-4. Permisos de escritura en todo el job del pipeline.** `pipeline.yml:193-194`.
El job que ejecuta código de terceros (FastF1, pandas, dbt) tiene `contents: write`.
*Propuesta:* dividir en `build` (solo lectura, sube `dist/` como artefacto) y `publish`
(`contents: write`, solo `gh release`). Esfuerzo M · Prioridad media.

**CI-5. Se publica sin probar el snapshot.** `pipeline.yml:255-269`.
`dbt build` valida los datos, pero la API no se arranca contra el `dist/f1.duckdb` nuevo antes de
publicarlo; la CI sí lo hace, pero sobre lo que ya está publicado.
*Propuesta:* antes de `gh release upload`, `F1_API_DB_PATH=dist/f1.duckdb pytest api/tests/smoke`
con unas cuantas pruebas de contrato (temporadas, última carrera, `/races/{id}/laps` no vacío,
`/quality` sin FAIL). Esfuerzo S · Prioridad alta.

**CI-6. Sin copias de seguridad de los datos.** `pipeline.yml:267-268` y
`ingestion/snapshot.py:41-53`. `data-latest` se sobrescribe cada semana (`--clobber`) y
`bronze.tar.gz` es la **única copia en la nube** de formula1db.com y Ergast, datos que no se pueden
volver a obtener. `pack_bronze` exige que existan (bien), pero un snapshot publicado con datos
malos no tiene marcha atrás.
*Propuesta:* (1) una release inmutable `bronze-static-v1` con las fuentes estáticas, que no cambian
nunca; (2) releases fechadas con retención de las 8 últimas (un paso que borre las antiguas);
(3) documentar la restauración y la vuelta atrás (DOC-2). Esfuerzo S-M · Prioridad alta.

**CI-7. pre-commit desfasado.** `.pre-commit-config.yaml:3,11`. `ruff-pre-commit v0.8.4` frente a
ruff 0.16.9 en `uv.lock` (lo que usa la CI), y `pre-commit-hooks v5.0.0`. El formateo local y el de
la CI pueden diferir. `pre-commit autoupdate`, o un *hook* local `uv run ruff`.
Esfuerzo S · Prioridad media.

**CI-8. Imagen Docker.** `api/Dockerfile:5,7,36`. `python:3.12-slim` y
`ghcr.io/astral-sh/uv:0.12` sin *digest*; el binario de uv (unos 35 MB) se queda en la imagen
final; `--forwarded-allow-ips='*'` (ver API-10); no se analiza la imagen en la CI.
*Propuesta:* construcción en dos etapas (builder con uv y `--mount=type=cache`, final solo con
`.venv` y código), imágenes fijadas por *digest* (Dependabot las mantiene) y Trivy en el job
`api-image`. Ya está bien: usuario no root, `HEALTHCHECK`, capa de dependencias reutilizable.
Esfuerzo S-M · Prioridad media.

**CI-9. Huecos de la CI.** Sin cobertura (`pytest-cov`) ni comprobación de tipos en Python
(mypy o pyright); Playwright instala Chromium en cada ejecución sin caché (`ci.yml:163`); el job
dbt descarga 52 MB de bronze en cada PR (cachear por el SHA del manifiesto); los cambios que solo
tocan `docs/` lanzan todos los jobs (`paths-ignore`). Esfuerzo S · Prioridad baja.

**CI-10. `render.yaml`.** `buildFilter` (`render.yaml:15-19`) no incluye `ingestion/__init__.py`,
que el Dockerfile copia (`Dockerfile:19`). Es trivial, pero conviene alinear los dos o eliminar la
copia si no hace falta. Esfuerzo S · Prioridad baja.

### 2.6 Pruebas

Estado: 40 pruebas de Python (`tests/` 10, `api/tests/` 30) que cubren bien la API, la caché, el
CORS, la descarga verificada y el snapshot. Qué **no** está probado:

| Componente | Qué falta | Propuesta | Esfuerzo |
|---|---|---|---|
| `f1db_loader` | `export_tables`, `download_sqlite`, `load` (idempotencia por tag) | SQLite de 2 tablas creada con `sqlite3` en `tmp_path`; `latest_release` con *monkeypatch* | S |
| `fastf1_loader.load_season` | omitir lo ya cargado, `force`, `rate_limited`, `failed` | *monkeypatch* de `completed_races` y `_load_race` | S |
| `ergast_loader`, `cli.main` | parseo y códigos de salida | zip en memoria; `main([...])` | S |
| `main.refresh_periodically` | cambio de versión, error de red, cierre de la conexión antigua | `refresh_hours` diminuto y `FakeRelease` (ya existe) | S |
| `Database` | consultas concurrentes durante el cambio de versión | `ThreadPoolExecutor` con consultas y `swap` a la vez | S |
| dbt intermedios | reglas de `int_laptimes`, `int_lap_numbering`, `int_tyre_compound_mapping`, `parse_duration_ms` | `unit_tests` (DBT-8) | M |
| Web | funciones puras y componentes | Vitest (WEB-7) | S-M |
| Pipeline | snapshot antes de publicar | pruebas de humo (CI-5) | S |

### 2.7 Documentación

**DOC-1. No hay fichero `LICENSE`.** El repositorio es público y redistribuye datos (F1DB con
CC BY 4.0, que exige atribución; los datos de formula1db.com con permiso). Añadir `LICENSE` para el
código (MIT o Apache-2.0) y un `DATA_LICENSE`/`NOTICE` con las licencias y atribuciones de cada
fuente. Esfuerzo S · Prioridad alta.

**DOC-2. Falta un runbook de operación.** Cómo volver a una versión anterior de los datos, qué hacer
si el pipeline falla a mitad, cómo republicar el bronze estático, cómo rotar
`F1_GITHUB_TOKEN`, cómo forzar la recarga en Render. Esfuerzo S · Prioridad media.

**DOC-3. README.** La cifra de unos 30 s de arranque en frío (`README.md:203-205`) no cuenta la
descarga de 54 MB. Esfuerzo S · Prioridad baja.

**DOC-4. Linaje incompleto en `dbt docs`.** Los modelos intermedios solo se documentan con
comentarios Jinja; pasarlos a YAML y declarar `exposures` para la API y la web completaría el
catálogo que publica el pipeline. Esfuerzo S · Prioridad baja.

**DOC-5. Scripts que dependen del directorio de trabajo.** `scripts/generate_override_seed.py:19-23`
se ejecuta al importarse y exige estar en `transform/`; `export_openapi.py:14` y
`make_api_fixture.py:16-17`, en la raíz. Usar `Path(__file__).resolve()` y `if __name__ ==
"__main__"`. Esfuerzo S · Prioridad baja.

## 3. Dependencias

- Python: las dependencias se declaran con cotas mínimas (`>=`) y se fijan en `uv.lock` (se
  instala con `--locked`), lo cual es correcto. Versiones instaladas: duckdb 1.5.5,
  fastapi 0.141.1, starlette 1.7.0, pydantic 2.13.5, dbt-core 1.12.5.
- `httpx2` (`pyproject.toml:33`) es legítima: la exige `starlette.testclient` en Starlette 1.x. Pero
  su versión se publicó el 23/09/2026: conviene que Dependabot vigile estos paquetes nuevos.
- `requires-python = ">=3.12,<3.13"`: valorar 3.13, porque todas las dependencias lo admiten.
- Web: 0 vulnerabilidades; desactualizadas solo en versiones mayores de herramientas (§1).

## 4. Mediciones de la API (TestClient, `dist/f1.duckdb`, mediana de 5)

| Endpoint | Tiempo | Tamaño | Con gzip | Filas |
|---|---:|---:|---:|---:|
| `/seasons` | 8,9 ms | 12,6 KB | 1,3 KB | 77 |
| `/seasons/2024/standings/drivers` | 21,9 ms | 4,3 KB | 1,0 KB | 24 |
| `/seasons/2024/standings/progression?top=20` | 10,9 ms | 58,7 KB | 3,6 KB | 464 |
| `/races/1102/laps` (Baréin 2024) | 34,5 ms | 454,6 KB | 26,8 KB | 1 129 |
| `/races/34/laps` (Indianápolis 1954) | 59,7 ms | 1 946,8 KB | 19,4 KB | 4 828 |
| `/races/1102/telemetry` (4 pilotos) | 22,7 ms | 116,1 KB | 45,0 KB | 4 |
| `/races/1102/stints` | 14,8 ms | 7,3 KB | 0,8 KB | 63 |
| `/drivers?limit=1000` | 16,0 ms | 156,3 KB | 19,9 KB | 917 |
| `/drivers/lewis-hamilton/results` | 10,8 ms | 74,4 KB | 4,9 KB | 424 |
| `/rankings/drivers?limit=500` | 41,6 ms | 106,4 KB | 14,1 KB | 500 |
| `/rankings/constructors?limit=500` | 25,5 ms | 35,2 KB | 4,2 KB | 186 |
| `/circuits` | 11,5 ms | 17,6 KB | 3,8 KB | 78 |
| resto (`/races/{id}`, `/records`, `/quality`…) | 4-10 ms | < 10 KB | < 2 KB | — |

Conclusión: el rendimiento de DuckDB no es un problema. El cuello de botella real es el arranque en
frío (API-1) y, en menor medida, el tamaño de `/laps` sin comprimir y la serialización (API-8).

## 5. Top 15 de mejoras (ordenadas por valor/esfuerzo)

| # | Mejora | Ref. | Esfuerzo | Prioridad |
|---:|---|---|:---:|:---:|
| 1 | Dependabot (acciones, uv, npm, docker) y acciones fijadas a SHA | CI-3, CI-1 | S | alta |
| 2 | Subir las acciones que aún usan Node 20 | CI-2 | S | alta |
| 3 | Cabeceras de seguridad en la web (CSP estática, nosniff, Referrer-Policy) y `poweredByHeader: false` | WEB-1 | S | alta |
| 4 | Timeout y reintento en el `fetch` de la web | WEB-2 | S | alta |
| 5 | Prueba de humo de la API contra el snapshot nuevo antes de publicarlo | CI-5 | S | alta |
| 6 | Copia inmutable del bronze estático y releases fechadas con retención; manifiesto subido al final | CI-6, API-3 | S-M | alta |
| 7 | `LICENSE` y atribución de las fuentes de datos | DOC-1 | S | alta |
| 8 | Arranque de la API con la última copia si falla GitHub; reintentos en la descarga | API-1, API-2 | M | alta |
| 9 | Códigos de piloto desde `abbreviation` y `driver_number` en `Lap`/`Stint` (corrige SCH/SCH y los stints de coches compartidos) | WEB-4, DBT-1 | S-M | media |
| 10 | Dorsales solo de sesiones de carrera y tests de grano en los cruces por dorsal | DBT-2, DBT-8 | S | media |
| 11 | `unit_tests` de dbt para `int_laptimes`, `int_lap_numbering` y `parse_duration_ms` | DBT-8 | M | alta |
| 12 | Extracción atómica y reintentos en la ingesta de F1DB; recarga de las últimas carreras de FastF1 | ING-1, ING-2, ING-4 | S | media |
| 13 | Segundo disparo del pipeline cuando F1DB publica tarde | ING-6 | S | media |
| 14 | `/health` que consulte la base de datos e informe del último refresco, más un monitor externo | API-11 | S-M | media |
| 15 | pre-commit alineado con el ruff de `uv.lock` y un linter SQL | CI-7, DBT-12 | S | media |

Siguientes candidatos: separar permisos del pipeline (CI-4), límite de peticiones (API-10), ECharts
con carga diferida (WEB-5), definiciones de récords únicas en dbt (DBT-7), imagen Docker en dos
etapas con Trivy (CI-8) y runbook de operación (DOC-2).
