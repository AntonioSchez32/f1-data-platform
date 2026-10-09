# Siguientes pasos (actualizado el 09/10/2026)

Única fuente del estado actual y de lo pendiente. Las decisiones están en `DECISIONES.md`. `PROGRESO.md` es el registro histórico del informe de situación y ya no se actualiza.

## Dónde estamos

**Hecho y en producción**
- **Plan original, fases 0–6:** ingesta, dbt, pipeline, API, web y despliegue.
- **Plan de acción:**
  - **T1:** licencia, Dependabot, acciones fijadas y cabeceras de seguridad.
  - **T2:** releases fechadas, `bronze-static-v1`, prueba de humo y copia de respaldo de la API.
  - **T3:** sprints de 2021–2023, bandera roja, tiempos por sectores, compuestos y tipos.
  - **C1:** coches compartidos, códigos y dorsales.
  - **C2:** pruebas de la fusión de vueltas.
  - **D1:** OpenF1 automático como respaldo y contraste de FastF1; dirección de carrera y meteo desde 2018 (commit `92c0c9f`).
- **D1 funciona solo.** El cron del lunes 05/10 publicó `data-2026-10-05` con la ronda 16 (Malasia). Esa carrera aún no tiene FastF1, así que la cubrió OpenF1: 1 142 vueltas, 328 mensajes y 254 muestras de meteo.
- **Dependabot:** los PR #7–#10 fusionados el 09/10, con la CI en verde.
- **Auditoría del 02/10** (`docs/auditoria/AUDITORIA.md`): el proyecto está sano, con 5 fallos altos verificados. Sus decisiones (34–44) se cerraron con `/grill-me`.
- **Arreglos de documentación de la auditoría** (decisión 39, 09/10):
  - README con «Reproducir desde cero» y los endpoints `/rankings/*`;
  - corregidas la caché de la web y la opción `seasons` del pipeline, que ya no existe;
  - nota en la decisión 1 y decisiones 31–33 ordenadas en su tabla.

**En curso**
- **Paridad con el informe de Power BI del TFG y catálogo de sus gráficos** (decisión 38). Entregables: `docs/paridad_tfg.md` y `docs/catalogo_informe_tfg.md`.
- **C4, correcciones de agregados** (decisiones 34–37 y 44): C4a (datos) y después C4b (API y web).

## Lo que queda del plan (camino A, alcance estándar)

Un commit por bloque. El equipo de agentes depende del riesgo (ver «Forma de trabajar»).

| Bloque | Contenido | Riesgo | Estimación |
|---|---|---|---|
| **C4** | Correcciones de la auditoría (decisiones 34–37 y 44):<br>• temporadas y años de pilotos y constructores desde los resultados (inscripciones y salidas);<br>• puntos de constructor: «Puntos» de F1DB desde 1958 y «Puntos históricos» desde 1950, con selector;<br>• sprint en el duelo entre compañeros;<br>• tests de cobertura y `accepted_values`;<br>• `legacy` falla si no encuentra la carpeta;<br>• formato del tiempo de carrera y primera prueba unitaria de la web.<br>Dos subtareas: C4a datos y C4b API y web | alto | 1–2 días |
| **D2** | **Jolpica** como segunda fuente de contraste (sustituye al volcado Ergast de 2022). Validación cruzada de 2023–2026. De la auditoría: DAT-06 (contrastar con Jolpica las carreras que solo tienen OpenF1), ING-01 (descarga del snapshot verificada con SHA) e ING-02 (umbral 0 en las dimensiones) | alto | 1,5–2,5 días |
| **D3** | Eventos históricos (SC/VSC/banderas rojas, seed desde Wikipedia/TracingInsights) y compuestos Pirelli C1–C6 desde 2024 (seed a partir de las notas de prensa de Pirelli) | alto | 3 días |
| **S1** | Vueltas de las carreras al sprint (29 sprints) con selector carrera/sprint en la web | alto | 4–6 días |
| **C3** | Errores de lectura de los gráficos: la referencia de clasificación, el eje de temporadas, Ferrari 1950–57, las etiquetas solapadas y el formato de miles. De la auditoría: WEB-02 (título de la 404), WEB-05 (`loading.tsx`) y los países en español (WEB-06). **Lighthouse CI**, con accesibilidad ≥ 95 y rendimiento ≥ 90 (decisión 41) | bajo | 2–3 días |
| **W1** | Navegación de 5 pestañas de carrera (decisión 7), con un título por pestaña (WEB-03) | bajo | 3 días |
| **W2** | Tanda 1 de gráficos: race trace (1990+), franjas SC/VSC, matriz de resultados, récords ampliados y eliminación matemática. Series que no dependan solo del color (WEB-04) | bajo | 6–8 días |
| **A1** | Arquitectura A: `justfile`, sources dbt de todo el bronze y disparo por calendario. De la auditoría: diccionario de columnas (DOC-02), **sqlfluff** (decisión 42), API-02 a API-07, API-09, ING-04, ING-05, ING-08 e ING-10 | bajo | 3–4 días |
| **F0** | Preparar la fase 7: vueltas limpias, corrección de combustible y categorías de abandono, con los motivos de abandono en español (WEB-06) | alto | 3–4 días |

Después: fase 7 (analítica) y memoria del TFG. Opcional: W3, W4 y A2.

**Hallazgos bajos de la auditoría sin bloque** (decisión 43; se revisan al cerrar A1):
- ING-03 (orden `--refresh-session` para OpenF1) e ING-06;
- WEB-07 a WEB-12;
- DAT-07, DAT-08, DAT-10 y DAT-12;
- DOC-10, DOC-11, DOC-13 y DOC-14.

## Tus tareas manuales

**Ahora**
- `git push` de lo que haya en `main` local.

**Rutina periódica**
- FastF1 cada 2–3 GP o una vez al mes, y siempre a final de temporada (decisión 27). El resumen del pipeline lista las carreras que solo tienen OpenF1; hoy, la ronda 16.

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

**Lanzar el pipeline a mano** (si hace falta)
- Actions → «Pipeline de datos» → *Run workflow*, sin casillas marcadas.
- O desde la terminal: `gh workflow run pipeline.yml`.
- Vercel y Render se despliegan solos con cada push.

**Opcional**
- `npm ci --prefix web` si vas a ejecutar la web en tu equipo.
- Ver ya los datos nuevos: Render → API → *Manual Deploy* → *Restart service*. Si no, la API los recoge en menos de 6 h.

**Decisiones o acciones tuyas para más adelante**
- Región `fra1` en Vercel (decisión 6), al final del plan.
- Documentación de dbt en GitHub Pages (decisión 10).
- Publicar el issue de correcciones a F1DB (decisión 11). Hay que añadir el caso de Italia 2026 (race 1162): F1DB repite la parada 2 de 9 pilotos y no tiene su parada 1.

**Cosas que no hay que hacer**
- No activar *Immutable releases* en GitHub: `data-latest` se reescribe en cada publicación.
- No fusionar los saltos de versión mayor de Dependabot (Python 3.14, TypeScript 7, ESLint 10, @types/node 26). Están ignorados a propósito.

## Forma de trabajar (decisiones 15–19 y 31–33)

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
- **Bloques grandes en subtareas** (decisión 33): 2–3 subtareas con un implementador nuevo cada una y un solo revisor por bloque. Las definiciones de agente incluyen normas de higiene de contexto.
- **Modo económico** (decisión 32), si los límites de uso se agotan a menudo: Opus Medio implementa y Sonnet Alto revisa; si se atasca, se escala a Opus Alto con revisor Opus.
- **Decisiones:** `/grill-me <tema>` (skill del proyecto en `.claude/skills/grill-me/`). Hace una pregunta cada vez, con la opción recomendada, y anota el resultado en `DECISIONES.md`.

## Qué decirme para seguir

«Retoma». Con eso compruebo el estado de C4 y de la paridad con el TFG (o los retomo si se cortaron) y, al acabar C4, preparamos **D2 (Jolpica)** con `/grill-me plan de D2`.

## Notas técnicas abiertas

- **Riesgos de D1** (no bloqueantes):
  - La guarda de fiabilidad de OpenF1 solo mira los tiempos. Si una carrera trae roto entero el endpoint `position` o `stints`, los controles de posición (umbral 99, hoy 99,56) o de compuesto (98, hoy 99,18) podrían fallar al publicar su FastF1.
  - Un fichero de sesión ya subido a `bronze-openf1` no se corrige sin borrar la release; la siguiente ejecución la vuelve a crear.
  - Si una carrera con FastF1 tiene una roja en carrera sin el código 5 de TrackStatus, el control `red_flag_messages_on_laps` fallará y habrá que revisarla.
  - La vida del neumático de OpenF1 coincide con FastF1 en el 85,9 % (diferencias de ±1); queda como control informativo.

- **DBT-7:** las definiciones de puntos de la API y de dbt **no** coinciden (auditoría API-01/N1/DAT-11; Ferrari 11 779,77 frente a 12 001,77, cuando la cifra de F1DB es 11 409). Se unifican en C4 (decisión 37).
- **A1/A2:** ninguna página de la web se cachea (todas son dinámicas).
- **API:** si la descarga de la release fechada falla (vimos un 500 puntual de GitHub), podría recurrir a `data-latest`, que tiene el mismo SHA-256.
- **Norma:** los cambios del Dockerfile o de `release.py` no se dan por buenos hasta que pase la CI de la imagen Docker.
- **Entorno:** el Python de la app de Claude está en su carpeta privada (MSIX). En tu terminal usa siempre `uv run …`.
