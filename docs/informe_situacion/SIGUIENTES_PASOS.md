# Siguientes pasos (actualizado el 01/10/2026)

Única fuente del estado actual y de lo pendiente. Las decisiones están en `DECISIONES.md`. `PROGRESO.md` es el registro histórico del informe de situación y ya no se actualiza.

## Dónde estamos

**En `main` y en producción:**
- Informe de situación, plan de acción y decisiones (`docs/informe_situacion/`).
- Tronco común del camino A:
  - **T1:** licencia, Dependabot, acciones fijadas y cabeceras de seguridad.
  - **T2:** releases fechadas, `bronze-static-v1`, prueba de humo y copia de respaldo de la API.
  - **T3:** sprints de 2021–2023, bandera roja, tiempos por sectores, compuestos y tipos.
- FastF1 cargado en tu PC y publicado en la release `bronze-fastf1` (`f1-ingest fastf1-publish`).
- PR de Dependabot #2 y #6 fusionados y #1, #3, #4 y #5 cerrados. No queda ningún PR abierto.
- C1 y C2 subidos (merge `6cee011`, CI en verde).
- El pipeline del 01/10 publicó `data-2026-10-01` con C1 y C2: dbt 173/173 y prueba de humo en verde.
  - La API la recoge en su siguiente comprobación (cada 6 h) o al reiniciarse.

**Hecho, pendiente de publicar (commit `92c0c9f`): D1**
- OpenF1 2023+ como respaldo y contraste de FastF1. Release incremental `bronze-openf1`, gestionada por el pipeline.
- Dirección de carrera y meteo de 2018 en adelante: `fact_race_control_message` (17 690 filas) y `fact_weather_sample` (28 225). Endpoints `/races/{id}/race-control` y `/races/{id}/weather`.
- Vueltas publicadas sin cambios: solo cambia `validation_status`. En 2025 las vueltas `single_source` pasan de 26 689 a 498 al confirmarlas OpenF1.
- Banderas rojas de 2025: no faltaba ninguna. La única fue la de Bélgica, antes de la vuelta 1, y ahora está en los mensajes.
- Defectos de OpenF1 detectados y aislados:
  - Australia 2026: vueltas desplazadas una posición;
  - Miami 2025: sin las vueltas 1–24;
  - Italia 2023: vueltas incompletas.
- Verificado: dbt 223/223, pytest 136 passed, ruff limpio. Revisado y aprobado en dos rondas.

## Qué tienes que hacer ahora, en este orden

1. **Publicar FastF1 con los mensajes y la meteo:** `uv run f1-ingest fastf1-publish`. Si no lo haces, la dirección de carrera y la meteo de 2018–2022 saldrán vacías.
2. **Push:** `git push`. Están pendientes `f9b3d2b`, `7509203`, `92c0c9f` y el commit de este documento. Comprueba que la CI sale en verde.
3. **Lanzar el pipeline:** `gh workflow run pipeline.yml`.
   - La primera ejecución descarga OpenF1 entero (unos 40 minutos) y crea la release `bronze-openf1`.
   - Hasta entonces, la API de producción da error 500 en `/race-control` y `/weather`. La web no los usa.

## Pendiente no obligatorio (para no olvidarlo)

Nada de esto bloquea el plan.

**Cuando te venga bien:**
- **Ver ya los datos nuevos en la web:** Render → servicio de la API → *Manual Deploy* → *Restart service*. Si no, se actualiza sola.
- **Web en local:** `npm ci --prefix web`, para pasar de React 19.2.8 a 19.3.0 tras el PR #2. Solo hace falta si vas a ejecutar la web en tu equipo.
- **Rutina de FastF1:** `uv run f1-ingest fastf1-publish --run-pipeline` (ver más abajo). Hasta que D1 funcione, tras cada GP; después, periódica (decisión 27).

**Decisiones o acciones tuyas para más adelante:**
- Región `fra1` en Vercel (decisión 6). Se hace al final del plan.
- Documentación de dbt en GitHub Pages (decisión 10).
- Publicar el issue de correcciones a F1DB (decisión 11). Hay que añadir el caso de Italia 2026 (race 1162): F1DB repite la parada 2 de 9 pilotos y no tiene su parada 1.

**Cosas que no hay que hacer:**
- No activar *Immutable releases* en GitHub: `data-latest` se reescribe en cada publicación.
- No fusionar los saltos de versión mayor de Dependabot (Python 3.14, TypeScript 7, ESLint 10, @types/node 26). Están ignorados a propósito; se revisarán aparte.

## Historial: C1 y C2

- `978fd6d` **C1**, correcciones visibles:
  - coches compartidos: una serie por coche y `driver_number` en la API;
  - códigos de piloto únicos por carrera (MSC/RSC);
  - dorsales solo de sesiones de carrera;
  - desempate determinista en la numeración de vueltas;
  - 4 812 vueltas que estaban ocultas vuelven a verse;
  - el dorsal vacío pasa a `0`.
- `b977fa7` **C2**, pruebas:
  - 14 unit tests de dbt (la fusión de vueltas, una regla por test) más tests de clave y relación. Detectan 30 de 30 roturas deliberadas.
  - Además: 9 paradas duplicadas de F1DB menos, equipo principal determinista y puntos redondeados.

## Lanzar el pipeline a mano

Actions → «Pipeline de datos» → *Run workflow*. Deja el campo de temporadas vacío y sin casillas marcadas.
- O desde tu terminal: `gh workflow run pipeline.yml`.
- Vercel y Render se despliegan solos con cada push.

## Rutina de FastF1 (tras cada GP hasta D1; después, cada 2–3 GP o mensual y a final de temporada)

```
uv run f1-ingest fastf1-publish --run-pipeline
```

- Si no pasas `--run-pipeline`, los datos se publican el lunes a las 06:00 UTC.
- Códigos de salida:

| Código | Significado |
|---|---|
| 0 | Publicada |
| 1 | Alguna carrera aún sin datos; se reintenta la semana siguiente |
| 3 | Falta `gh` o no hay sesión; la copia queda en `dist/` |
| 4 | La copia local tiene menos carreras que la publicada |
| 5 | No se pudo consultar la release |
| 6 | Falló la subida; repite con `--skip-ingest` |
| 7 | Publicada, pero lanza el pipeline a mano |

## Lo que queda del plan (camino A, alcance estándar)

Orden recomendado (ver `plan_accion.pdf`). Un commit por bloque. El equipo de agentes depende del riesgo del bloque (ver «Forma de trabajar»).

| Bloque | Contenido | Riesgo | Estimación |
|---|---|---|---|
| ~~**D1**~~ | **OpenF1 automático + dirección de carrera y meteo** (decisiones 20–30): OpenF1 2023+ (carrera, sprint y clasificación a bronze en la release incremental `bronze-openf1`; se modela la carrera) como respaldo y contraste de FastF1; posición por vuelta desde `position`; `fact_race_control_message` y `fact_weather_sample` 2018+ (FastF1 `messages`/`weather` recargado en local + OpenF1) con endpoints en la API; banderas rojas de 2025; publicar con aviso si OpenF1 falla. | alto | **Hecho** (`92c0c9f`) |
| **D2** | **Jolpica** como segunda fuente de contraste (sustituye al volcado Ergast de 2022). Validación cruzada de 2023–2026. | alto | 1–2 días |
| **D3** | Eventos históricos (SC/VSC/banderas rojas, seed desde Wikipedia/TracingInsights) y compuestos Pirelli C1–C6 desde 2024 (seed a partir de las notas de prensa de Pirelli). | alto | 3 días |
| **S1** | Vueltas de las carreras al sprint (29 sprints) con selector carrera/sprint en la web. | alto | 4–6 días |
| **C3** | Errores de lectura de los gráficos. Entre ellos: la referencia de clasificación, el eje de temporadas, Ferrari 1950–57, las etiquetas solapadas, el formato de miles y el NaN de «Evolución del campeonato» en `/es/seasons/2021`. | bajo | 2 días |
| **W1** | Navegación de 5 pestañas de carrera (decisión 7). | bajo | 3 días |
| **W2** | Tanda 1 de gráficos: race trace (1990+), franjas SC/VSC, matriz de resultados, récords ampliados, eliminación matemática. | bajo | 6–8 días |
| **A1** | Arquitectura A: `justfile`, sources dbt de todo el bronze, disparo por calendario. | bajo | 2–3 días |
| **F0** | Preparar la fase 7: vueltas limpias, corrección de combustible, categorías de abandono. | alto | 3–4 días |

Las decisiones y acciones tuyas para más adelante están en «Pendiente no obligatorio».

## Forma de trabajar (decisiones 15–19, 31 y 32)

- **Implementación por riesgo:**
  - Riesgo alto (datos, pipeline, Dockerfile, `release.py`, publicación): implementador Opus Alto y un revisor Opus Medio.
  - Riesgo bajo (web, gráficos, organización): implementador Opus Medio y un revisor Sonnet Medio.
  - Un solo revisor y como mucho dos rondas. Ningún bloque está terminado sin la CI en verde.
- **Commits:** los hace Claude en la sesión principal, sin agentes.
- **Push y pipeline:** los haces tú. Claude comprueba la CI y los datos publicados con `gh`.
- **Investigación y replanificación:**
  - Investigador o planificador Opus Alto (Max solo en replanificaciones grandes).
  - Si hay disyuntivas reales, se añaden un defensor y un crítico, ambos Opus Medio.
  - Las decisiones se cierran con `/grill-me`.
- **Agentes definidos** (decisión 31): `f1-implementador-alto`, `f1-implementador-medio`, `f1-revisor-opus`, `f1-revisor-sonnet`, `f1-revisor-sonnet-alto`, `f1-investigador`, `f1-investigador-max`, `f1-defensor` y `f1-critico`, con modelo y esfuerzo fijados en `.claude/agents/`.
- **Modo económico** (decisión 32), si los límites de uso se agotan a menudo: Opus Medio implementa y Sonnet Alto revisa; si se atasca, se escala a Opus Alto con revisor Opus.
- **Decisiones:** `/grill-me <tema>` (skill del proyecto en `.claude/skills/grill-me/`). Hace una pregunta cada vez, con la opción recomendada, y anota el resultado en `DECISIONES.md`.

## Qué decirme para seguir

«Retoma». Con eso compruebo la CI y los datos publicados de D1 y preparo **D2 (Jolpica)**. Antes conviene cerrar sus detalles con `/grill-me plan de D2`.

## Notas técnicas abiertas

- **Riesgos de D1** (no bloqueantes):
  - La guarda de fiabilidad de OpenF1 solo mira los tiempos. Si una carrera trae roto entero el endpoint `position` o `stints`, los controles de posición (umbral 99, hoy 99,56) o de compuesto (98, hoy 99,18) podrían fallar al publicar su FastF1.
  - Un fichero de sesión ya subido a `bronze-openf1` no se corrige sin borrar la release; la siguiente ejecución la vuelve a crear.
  - Si una carrera con FastF1 tiene una roja en carrera sin el código 5 de TrackStatus, el control `red_flag_messages_on_laps` fallará y habrá que revisarla.
  - La vida del neumático de OpenF1 coincide con FastF1 en el 85,9 % (diferencias de ±1); queda como control informativo.

- **DBT-7:** unificar las definiciones de puntos entre la API y dbt (hoy ya coinciden gracias al redondeo).
- **A1/A2:** ninguna página de la web se cachea (todas son dinámicas).
- **API:** si la descarga de la release fechada falla (vimos un 500 puntual de GitHub), podría recurrir a `data-latest`, que tiene el mismo SHA-256.
- **Norma:** los cambios del Dockerfile o de `release.py` no se dan por buenos hasta que pase la CI de la imagen Docker.
- **Entorno:** el Python de la app de Claude está en su carpeta privada (MSIX). En tu terminal usa siempre `uv run …`.
