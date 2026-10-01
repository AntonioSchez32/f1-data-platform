# Decisiones tomadas sobre el plan de acción (30/09/2026)

Tomadas por el autor a partir de `plan_accion.pdf`, sección 6.

| # | Decisión | Elección |
|---|---|---|
| 1 | Licencia | **MIT** para el código y **CC BY 4.0** para los datos derivados, con atribución a F1DB, FastF1 y los datos © F1/FIA |
| 2 | Fuentes CC BY-NC-SA (Jolpica, OpenF1) | **Se aceptan**. Los datos derivados de ellas se publican como CC BY-NC-SA 4.0; el código sigue siendo MIT |
| 3 | Descarga de volcados de terceros | **Solo Jolpica**; f1resultsdatabase no se descarga |
| 4 | Camino | **A · Consolidar y ampliar** |
| 5 | Alcance | **Estándar**: hasta el hito 4 (preparación de la fase 7) |
| 6 | Región de Vercel | **fra1**, pero **más adelante**: es cuestión de despliegue y la prioridad es la implementación. Sale del tronco común y se hace al final |
| 7 | Navegación | **5 pestañas de carrera ya**; las secciones nuevas entran cuando exista su contenido (Historia con la tanda 1; Circuitos y Comparar solo con el alcance ampliado) |
| 8 | Empezar la implementación | **Sí, por el tronco común**, con un commit por bloque (T1, T2 y T3) y una parada tras cada uno para hacer push |
| 9 | Informe y plan en el repositorio | **Fuentes y los dos PDF finales**; los auxiliares de `build/` quedan fuera |
| 10 | Documentación de dbt en GitHub Pages | **Más adelante** |
| 11 | Issue de correcciones a F1DB | **Más adelante** |
| 12 | FastF1 bloqueado en GitHub Actions (403 de CloudFront) | Por ahora, carga en el PC del autor y publicación en la release `bronze-fastf1` (`f1-ingest fastf1-publish`); FastF1 queda como complemento opcional |
| 13 | Fuente automática del pipeline para las carreras nuevas | **OpenF1** como fuente principal (2023+) y **Jolpica** como segunda fuente de contraste. Las dos responden 200 desde GitHub (diagnóstico del 30/09) |
| 14 | Orden | **C1 y C2 primero** (correcciones visibles y pruebas de la fusión de vueltas); después D1 con OpenF1 y Jolpica |

## Forma de trabajar (01/10/2026)

Desde aquí cada decisión indica las alternativas valoradas y el motivo.

| # | Decisión | Elección | Alternativas valoradas | Motivo |
|---|---|---|---|---|
| 15 | Equipo de agentes para implementar | **Según el riesgo del bloque.** Datos, pipeline, Dockerfile, `release.py` y publicación: implementador Opus Alto y un revisor Opus Medio. Web, gráficos y organización: implementador Opus Medio y un revisor Sonnet Medio. Un solo revisor, como mucho dos rondas, y la CI en verde obligatoria | Mantener un implementador y dos revisores, todos Opus Alto (lo usado en T1–C2). Opus Medio + Sonnet Medio en todo. Opus Alto + Opus Alto | El segundo revisor repetía lo que encontraba el primero y provocaba bloqueos esperando aprobaciones. El fallo más grave (PermissionError en Docker) lo detectó la CI, no un revisor. Los bloques de datos tienen errores sutiles que justifican mantener modelos fuertes. Se gasta entre la mitad y un tercio de tokens |
| 16 | Commits | Los hace Claude en la sesión principal, sin agentes | Delegarlos en un agente | Es una tarea mecánica; lanzar un agente cuesta más que hacerla |
| 17 | Push y pipeline | **Los hace el autor**. Claude comprueba la CI y los datos publicados con `gh` | Claude lanza el pipeline; Claude hace push y lanza el pipeline | El autor conserva el control de lo que llega a GitHub y a producción |
| 18 | Investigación y replanificación | Investigador o planificador **Opus Alto** (Max solo en replanificaciones grandes). Si hay disyuntivas reales, se añaden un **defensor** y un **crítico** Opus Medio. Las decisiones se cierran con `/grill-me` | Opus Alto o Max con defensor y crítico en cualquier investigación. Un solo investigador | El debate aporta donde hay alternativas reales, no al recopilar datos. Max sale caro y solo compensa en lo más grande |
| 19 | Seguimiento | `SIGUIENTES_PASOS.md` es la única fuente del estado y de lo pendiente. `DECISIONES.md` recoge cada decisión con fecha, alternativas y motivo. `PROGRESO.md` queda como histórico y no se actualiza. Skill `/grill-me` en `.claude/skills/` | Seguir actualizando los tres documentos | Los tres documentos se solapaban. El registro de decisiones con alternativas sirve directamente para la memoria del TFG |

## Consecuencias para el plan
- El tronco común queda en T1 (sin el cambio de región), T2 y T3.
- D2: Jolpica sustituye al volcado Ergast 2022. Su atribución y la licencia NC-SA se reflejan en README, web y API.
- W1: la reorganización a 5 pestañas entra en la iteración de web. «Récords» pasa a «Historia» en W2.
- Siguen aplazados los casos de numeración de San Marino y Japón 1994 y Bélgica 2001.
