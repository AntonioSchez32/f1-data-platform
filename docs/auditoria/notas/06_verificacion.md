# Auditoría 6: verificación crítica de los hallazgos (02/10/2026)

Papel: verificador. Objeto: los hallazgos de las notas 01–05, no el proyecto. Solo lectura y
consultas; la única escritura es esta nota.

## 1. Alcance y método

**Copia de datos.** Descarga propia de `data-latest` en el scratchpad (`rel/`): `manifest.json` →
`release_tag = data-2026-10-01-6.1`, F1DB `v2026.15.1`. Firma comparada (filas de
`agg_driver_season`/`fact_laptimes`/`dim_race`, puntos de Ferrari, pares DAT-01, `first_season` de
Ferrari, ganadores WEB-01) en tres bases: la release, `data/gold/f1.duckdb` local y la que reconstruí
en un clon limpio (ver DOC-01): **idénticas** (`1681/1270260/1172/…/1586/1958/21`).

**Copia antigua.** La carpeta temporal compartida es el scratchpad de la sesión (`pub/`, manifiesto
`data-2026-09-29`, también F1DB `v2026.15.1`). Con la misma firma da **los mismos valores** (incluidos
Ferrari 11 779,77 / 12 001,77 y los 1 586 pares): **ningún hallazgo de datos cambia** con la copia
actual. La nota 05 ya avisó y usó copia propia; la 02 usó la base local (idéntica); la 03, «la release».

**Producción** (solo GET, 9 peticiones en total): API `/drivers/ayrton-senna/seasons`,
`/drivers/ayrton-senna`, `/constructors/ferrari`, `/drivers?season=1985`, `/records/constructors`,
`/rankings/constructors`; web `/es/races/911`, `/es/drivers/fernando-alonso`, `/es/races/1110`,
`/es/records?entity=constructors`, y `curl -I` a `/es` y `/es/seasons/2024`.

## 2. Veredictos (críticos, altos y medios pedidos)

| ID | Veredicto | Gravedad (auditor → propuesta) | Evidencia de la reproducción | ¿Arreglo y bloque razonables? |
|---|---|---|---|---|
| **DAT-01** | CONFIRMADO | alta → **alta** | Release: 1 586 pares (temporada, piloto) de `fact_race_result` RACE ausentes de `agg_driver_season`, **todos con 0 puntos**, 1950–2017 (680 en los 50; 4 en los 2000; 4 en los 2010). 1985: 36 pilotos con resultados, 20 en el agregado. 472 pilotos con alguna inscripción (404 con salidas) sin ninguna fila. Producción: Senna `seasons` = 1984–1993 (falta 1994); `/drivers?season=1985` → 20 | Sí. Matiz: decidir si cuentan inscripciones sin salida (DNQ/DNPQ/EX), porque cambia los recuentos (472 frente a 404). Ver «duplicados»: un único bloque con DAT-02, DAT-03 y API-01 |
| **DAT-02** | CONFIRMADO | alta → **alta** | Con «salida» = `position_text` ∉ {DNQ, DNPQ, DNP, EX}: de 792 pilotos con salidas, 564 `first_season` y 529 `last_season` distintos de min/max de resultados (auditor: 560/527; la diferencia es la definición de salida), 404 nulos. Contando inscripciones: 638/600/472 de 860. Senna 1984–1993, Lauda 1973, Mansell 1994, Button 2016 en la release y en producción | Sí (min/max de resultados). Misma causa raíz que DAT-01: los años salen de la clasificación final de F1DB, que omite a quien no puntuó |
| **DAT-03** | CONFIRMADO CON MATIZ | media → **alta** | 28 constructores con `first_season` distinto de su primera carrera (Ferrari, Cooper, Maserati 1958 en vez de 1950; Mercedes 2010 en vez de 1954) **y 20 con `last_season` distinto, que el auditor no vio**: Tyrrell 1997 (corrió en 1998), Lotus 1993 (1994), Brabham 1991 (1992), Lola 1991 (1997). Producción: `/constructors/ferrari` → 1958 | El arreglo «`least`/`greatest`» funciona, pero lo correcto es tomar los años solo de los resultados (como DAT-02). Sube a alta: es el mismo error visible que DAT-02 en equipos muy conocidos, y la misma corrección |
| **WEB-01** | CONFIRMADO | alta → **media** | `node` con el código de `format.ts`: `raceTime(7204795)` → «2:00004.795». DuckDB: 21 ganadores afectados (el último, 2014; ninguno en sprint). Producción `/es/races/911` contiene «2:00004.795» | Sí (y prueba unitaria). Baja a media: una celda (el tiempo del ganador) en 21 de 1 172 carreras, ninguna desde 2014, y el valor es visiblemente ilegible, no un dato plausible pero falso. Solo llegaría a la portada si un ganador tarda entre 2 h 00 min y 2 h 01 min. Arreglo de minutos: conviene hacerlo ya, no esperar a C3 |
| **DOC-01** | CONFIRMADO CON MATIZ | alta → **alta** (arreglo inmediato) | Clon limpio en el scratchpad (`git clone` + `uv sync` OK). `f1-ingest legacy` → solo avisos y **código de salida 0** (escribe un `_metadata.json` con `{}`); `f1-ingest ergast` → `FileNotFoundError` (`…\ERGAST API\f1db_csv.zip`). Con solo el bronze de F1DB copiado del local: `dbt build` → 6 errores (staging de Ergast, FastF1 y formula1db: «No files found»), 68 omitidos. **Ruta alternativa probada**: `gh release download data-latest -p bronze.tar.gz` (60 MB, release propia) + `f1-ingest snapshot restore` + `dbt build` → **223 nodos, 0 errores** (147 pass, 76 success) | El arreglo propuesto (sección «Reproducir desde cero» con `snapshot restore`) está validado y la CI ya lo hace. El problema es solo documental, pero el README es la puerta del tribunal. Bloque: inmediato (documentación), no A1. Añadir que `legacy` falle (exit ≠ 0) si no encuentra la carpeta (ver N2) |
| **DOC-02** | CONFIRMADO CON MATIZ | alta → **media** | `transform/target/manifest.json` frente a `information_schema` de la release: 36 de 299 columnas de gold descritas (cuadra), pero **19 de 19 modelos de gold sí tienen descripción** y el OpenAPI de la API tiene 33 `description=` en `schemas.py` | Es el mismo hallazgo que **DAT-09** (baja): hay que unificarlo. Propongo media: el plan prometía un diccionario, pero la publicación de `dbt docs` está aplazada (decisión 10) y existe descripción por modelo. El arreglo (descripciones de columnas con `doc` blocks, empezando por los `agg_*`) es razonable; bloque A1 o junto a la memoria |
| **API-01** | CONFIRMADO, **arreglo propuesto incorrecto** | media → **alta** | Release y producción: Ferrari 11 779,77 (`/records`) frente a 12 001,77 (`/rankings`); la web de récords muestra «12.001,8». Pero el **total oficial de F1DB** (`constructor.total_points`) es **11 409**: carrera + sprint **desde 1958** (antes no había campeonato de constructores). Esa definición cuadra con F1DB en **186 de 186** constructores; `race_points` actual, en 154; la suma de `/rankings`, en 163. Pilotos: `agg_driver_career.points` cuadra en 917/917 | El arreglo del auditor (`points` = carrera + sprint) daría 12 001,77, que sigue siendo falso. Correcto: carrera + sprint, solo temporadas ≥ 1958, en dbt y en `/rankings` (que con rango anterior a 1958 debería dar 0 o nulo). Añadir `points` a `assert_constructor_totals_match_f1db.sql`, que hoy no lo compara (por eso no se detectó). Sube a alta: cifra errónea visible en la web para el equipo más conocido. Duplica **DAT-11**; encaja con «constructores sin barras antes de 1958» de C3 |
| **DAT-04** | CONFIRMADO CON MATIZ | media → **media** | `agg_teammate_h2h` 2021: Hamilton 385,5 / Verstappen 388,5 frente a 387,5 / 395,5 en `agg_driver_season` | Causa distinta de API-01 (otro modelo) pero misma familia: falta una definición única de «puntos» (DBT-7). Según el reglamento (y F1DB, y `agg_driver_career.points`), los puntos del campeonato incluyen el sprint desde 2021: incluirlo. Matiz: aun así el H2H nunca cuadrará con el campeonato si el compañero cambia a mitad de temporada (solo cuenta carreras compartidas); la web debe decirlo |
| **ING-01** | CONFIRMADO | media → **media** | `gh 2.102.0`: `release download data-latest --pattern no-existe.tar.gz --pattern manifest.json` → exit 0 y solo `manifest.json`; con el patrón inexistente solo → exit 1. `pipeline.yml:73` usa solo el código de salida | Sí. `--clobber` tiene que borrar el asset antes de subir (GitHub no admite dos con el mismo nombre), así que el estado «manifiesto sin bronze» es posible. La API no se ve afectada (lee la release fechada) |
| **ING-02** | CONFIRMADO CON MATIZ | media → **media** | `table_count_regressions(previous={dim_race:1172,…}, current={dim_race:1150,…})` → `[]` | Matiz: el histórico de vueltas (formula1db, Ergast) se restaura siempre desde `bronze-static-v1` inmutable (`--replace`) y FastF1 tiene su propia guarda por temporada (`snapshot.py:185`), así que el riesgo real son F1DB y los errores de dbt. El umbral 0 en dimensiones es razonable |
| **ING-03** | CONFIRMADO CON MATIZ | media → **baja** | `openf1_loader.py:342` salta ficheros existentes; no hay `--force` en la CLI de OpenF1 | Es la consecuencia directa de la **decisión 24** («pide solo las sesiones nuevas»), y la decisión 20 da prioridad a FastF1. Los tres defectos citados **no llegan a gold**: Australia 2026 y Miami 2025 tienen vueltas de `fastf1` y Monza 2023 de `formula1db`; en 2025–2026 todas las carreras tienen FastF1. El docstring citado habla de recuperar un manifiesto ilegible, no de refrescar datos. Riesgo residual: la carrera más reciente sin FastF1, hasta la rutina local. Una orden `--refresh-session` es razonable, pero de prioridad baja |
| **DOC-03** | CONFIRMADO CON MATIZ | media → **baja** | `/es` y `/es/seasons/2024`: `Cache-Control: private, no-cache, no-store`, `X-Vercel-Cache: MISS` | Las páginas no se cachean, pero las respuestas de la API sí (`client.ts:65`, `next: { revalidate: 3600 }` en la Data Cache), así que el efecto práctico que describe el README (solo espera quien pide datos que nadie pidió en la última hora) se cumple en lo esencial; lo erróneo es «conserva en caché las páginas». Otro desajuste: el README dice «espera hasta 60 s» y `fetchWithRetry` llega a 60 + 1 + 20 s |
| **DOC-05** | CONFIRMADO CON MATIZ | media → **baja** | `DECISIONES.md:7` (CC BY 4.0 para los datos derivados) frente a README `:466-480` | La decisión 2 ya enmienda la 1 para OpenF1 y Jolpica (NC-SA), y README, `api/app/main.py:149` y las notas de la release son coherentes entre sí. Solo falta una nota en la fila 1. Arreglo de una línea, inmediato |
| **WEB-05** | CONFIRMADO | media → **media** | No hay `loading.*` en `web/src/app` (sí `error.tsx`); espera máxima de un `fetch` ≈ 81 s | Sí. Matiz: la Data Cache (ver DOC-03) hace que solo pase con URL no pedidas en la última hora; el indicador sigue siendo útil |
| **WEB-06** | CONFIRMADO | media → **media** | Producción: «Spain · #14» en `/es/drivers/fernando-alonso`; «Collision», «Accident damage», «Engine» en `/es/races/1110` | Sí. El de abandonos encaja con la seed de categorías de F0; los países, con un diccionario por ISO (la API ya da `alpha2`) |

## 3. Duplicados y contradicciones entre notas

- **DAT-09 = DOC-02** (cobertura de descripciones), con gravedades baja y alta. Unificar en uno (propongo media).
- **API-01 ⊃ DAT-11** (constructores: `race_points` sin sprint frente a `/rankings`), media y baja. Unificar; ver N1.
- **API-08 ⊂ DOC-12** (README sin `/rankings/*`). Unificar en DOC-12.
- **DAT-01, DAT-02 y DAT-03**: una sola causa raíz (años y temporadas tomados de las clasificaciones finales de F1DB, que omiten a quien no puntúa) y un solo arreglo; el test de cobertura de **DAT-05** es el que los habría detectado. Conviene un único bloque «correcciones de agregados» con API-01/N1 y DAT-04, antes de C3.
- **DOC-03 y WEB-05** describen el mismo comportamiento (caché y arranque en frío) desde la documentación y desde la web; no se contradicen, pero DOC-03 sobrestima el efecto (ver matiz).
- **Contradicción con el estado del proyecto**: `SIGUIENTES_PASOS.md:144` (DBT-7, «hoy ya coinciden») y el docstring de `rankings.py:3-4` («coinciden con los totales oficiales de F1DB») son falsos para los puntos de 23 constructores.
- **ING-03** atribuye al docstring de `openf1_upload_decision` una promesa de refresco que no hace (habla de un manifiesto ilegible).
- No encontré contradicciones de datos entre notas: todas las cifras que reproduje cuadran con la release actual.

## 4. Nuevos

| ID | Gravedad | Hallazgo | Evidencia | Propuesta |
|---|---|---|---|---|
| **N1** | alta | Los puntos de constructores incluyen las temporadas 1950–1957, en las que no había campeonato de constructores; ninguna de las dos cifras de la API es la oficial | F1DB `constructor.total_points` de Ferrari = 11 409 = suma de carrera + sprint con `season >= 1958`; cuadra en 186/186 constructores. API: 11 779,77 y 12 001,77; web de récords: «12.001,8». `assert_constructor_totals_match_f1db.sql` no compara puntos | Definición única en dbt (carrera + sprint, ≥ 1958), usada también por `/rankings`; añadir `points` al test de paridad. Mismo bloque que DAT-01–03 (o C3, que ya prevé «constructores sin barras antes de 1958») |
| **N2** | baja | `f1-ingest legacy` sin la carpeta de origen termina con código 0 y deja `data/bronze/formula1db/_metadata.json` con `{}` | Clon limpio: solo `WARNING … se omite` por cada CSV; exit 0. El error aparece después, en `dbt build` («No files found») | Fallar con un mensaje claro que remita a `snapshot restore`; va con DOC-01 |

Observación de proceso: el scratchpad lo comparten todos los agentes de la sesión (`pub/`, `doc05/`, `aud/`…). Por eso un auditor pudo usar la copia antigua; aquí no cambió ningún resultado.

## 5. Dudas

- No comprobé en el código de `gh` el orden de borrado y subida de `--clobber` (lo deduzco de que GitHub no admite dos assets con el mismo nombre).
- DOC-03: no medí tiempos con la API dormida (estaba despierta por las peticiones anteriores), así que la eficacia de la Data Cache en Vercel se deduce del código.
- No reproduje los hallazgos bajos ni WEB-02/03/04, DAT-05/06/07 y DOC-04/06/07 (fuera del encargo).
