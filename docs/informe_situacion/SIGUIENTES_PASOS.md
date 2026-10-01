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
| **D1** | **OpenF1 automático + dirección de carrera y meteo** (decisiones 20–30): OpenF1 2023+ (carrera, sprint y clasificación a bronze en la release incremental `bronze-openf1`; se modela la carrera) como respaldo y contraste de FastF1; posición por vuelta desde `position`; `fact_race_control_message` y `fact_weather_sample` 2018+ (FastF1 `messages`/`weather` recargado en local + OpenF1) con endpoints en la API; banderas rojas de 2025; publicar con aviso si OpenF1 falla. | alto | 4–5 días |
| **D2** | **Jolpica** como segunda fuente de contraste (sustituye al volcado Ergast de 2022). Validación cruzada de 2023–2026. | alto | 1–2 días |
| **D3** | Eventos históricos (SC/VSC/banderas rojas, seed desde Wikipedia/TracingInsights) y compuestos Pirelli C1–C6 desde 2024 (seed a partir de las notas de prensa de Pirelli). | alto | 3 días |
| **S1** | Vueltas de las carreras al sprint (29 sprints) con selector carrera/sprint en la web. | alto | 4–6 días |
| **C3** | Errores de lectura de los gráficos. Entre ellos: la referencia de clasificación, el eje de temporadas, Ferrari 1950–57, las etiquetas solapadas, el formato de miles y el NaN de «Evolución del campeonato» en `/es/seasons/2021`. | bajo | 2 días |
| **W1** | Navegación de 5 pestañas de carrera (decisión 7). | bajo | 3 días |
| **W2** | Tanda 1 de gráficos: race trace (1990+), franjas SC/VSC, matriz de resultados, récords ampliados, eliminación matemática. | bajo | 6–8 días |
| **A1** | Arquitectura A: `justfile`, sources dbt de todo el bronze, disparo por calendario. | bajo | 2–3 días |
| **F0** | Preparar la fase 7: vueltas limpias, corrección de combustible, categorías de abandono. | alto | 3–4 días |

Las decisiones y acciones tuyas para más adelante están en «Pendiente no obligatorio».

## Forma de trabajar (decisiones 15–19)

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
- **Decisiones:** `/grill-me <tema>` (skill del proyecto en `.claude/skills/grill-me/`). Hace una pregunta cada vez, con la opción recomendada, y anota el resultado en `DECISIONES.md`.

## Qué decirme para seguir

«Retoma». Con eso lanzo **D1** con el plan cerrado en las decisiones 20–30: riesgo alto, implementador Opus Alto y revisor Opus Medio. Al final de D1 tendrás que publicar FastF1 (`uv run f1-ingest fastf1-publish --run-pipeline`) porque la recarga añade mensajes y meteo.

## Notas técnicas abiertas

- **DBT-7:** unificar las definiciones de puntos entre la API y dbt (hoy ya coinciden gracias al redondeo).
- **A1/A2:** ninguna página de la web se cachea (todas son dinámicas).
- **API:** si la descarga de la release fechada falla (vimos un 500 puntual de GitHub), podría recurrir a `data-latest`, que tiene el mismo SHA-256.
- **Norma:** los cambios del Dockerfile o de `release.py` no se dan por buenos hasta que pase la CI de la imagen Docker.
- **Entorno:** el Python de la app de Claude está en su carpeta privada (MSIX). En tu terminal usa siempre `uv run …`.
