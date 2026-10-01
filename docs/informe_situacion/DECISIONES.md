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
| 31 | Cómo se fijan el modelo y el esfuerzo de los agentes | **Definiciones de agente** en `.claude/agents/` (versionadas) con copia en `~/.claude/agents/`: `f1-implementador-alto` (Opus, alto), `f1-implementador-medio` (Opus, medio), `f1-revisor-opus` (Opus, medio), `f1-revisor-sonnet` (Sonnet, medio), `f1-revisor-sonnet-alto` (Sonnet, alto), `f1-investigador` (Opus, alto), `f1-investigador-max` (Opus, max), `f1-defensor` y `f1-critico` (Opus, medio) | Indicar el esfuerzo en el texto del encargo | El encargo no fija el esfuerzo real; el campo `effort` de la definición sí. Las normas comunes van en la definición y los encargos son más cortos. La copia de usuario hace falta porque las sesiones se abren en la carpeta superior del TFG |
| 32 | Plan B si los límites de uso se agotan a menudo | **Modo económico**: implementador `f1-implementador-medio` (Opus, medio) y revisor `f1-revisor-sonnet-alto` (Sonnet, alto) también en bloques de riesgo alto. **Escalado**: si se atasca (dos rondas sin aprobar, pruebas que no consigue arreglar o un error de datos que el revisor no ve claro), esa tarea se relanza con `f1-implementador-alto` y `f1-revisor-opus` | Mantener siempre la configuración por riesgo | Propuesta del autor. Se prueba solo si los cortes por límite son frecuentes; la escalada protege los bloques difíciles |
| 33 | Consumo de tokens tras medir D1 | **Subtareas e higiene de contexto.** Los bloques grandes (más de 2–3 días o que tocan más de dos capas) se parten en 2–3 subtareas, cada una con un implementador nuevo; un solo revisor por bloque. Las definiciones de agente incluyen normas para no acumular contexto: salidas resumidas de dbt y pytest, nada de volcar ficheros enteros y procesos largos en segundo plano sin comprobaciones en bucle. El revisor de los bloques de datos sigue siendo Opus; Opus Medio con revisor Sonnet se mide en el primer bloque de web (C3) | Modo económico en todos los bloques. Las dos cosas. Sin cambios | En D1 (≈14,7 M tokens ponderados) el implementador pesó el 78 % porque su contexto llegó a unos 600 000 tokens, releídos en cada llamada; la reanudación tras el corte costó el 28 % de su consumo en 30 llamadas. El revisor pesó el 14 % (frente al 39 % de los dos revisores de C1 y C2) y encontró fallos reales (B1, B4, B5): pasarlo a Sonnet ahorraría como mucho un 5–10 % |

## Plan de D1 (01/10/2026, cerrado con `/grill-me`)

| # | Decisión | Elección | Alternativas valoradas | Motivo |
|---|---|---|---|---|
| 20 | Papel de OpenF1 frente a FastF1 | **Respaldo y contraste.** FastF1 manda donde existe; OpenF1 rellena automáticamente las carreras sin FastF1 y contrasta 2023+ (`validation_status`) | OpenF1 principal en 2023+. OpenF1 solo para lo nuevo, sin contraste | FastF1 ya está validado (correcciones, mayoría, unit tests) y trae la posición por vuelta. Con OpenF1 como respaldo la web se actualiza sin el PC del autor |
| 21 | Endpoints de OpenF1 | `sessions`, `laps`, `position`, `stints`, `pit` y `session_result`, más `race_control` y `weather` | Solo el núcleo. Además `overtakes` e `intervals` | `race_control` y `weather` eran el objetivo del D1 original y arreglan las banderas rojas de 2025. `car_data`, `location` y `team_radio` pesan mucho y no tienen uso. `overtakes` e `intervals` quedan para W2 si hacen falta |
| 22 | Sesiones | **Carrera y sprint** con los endpoints anteriores; **clasificación (Q y SQ)** solo `laps`, `stints` y `session_result`, guardada en bronze **sin modelar**. En D1 solo se modela la carrera; el sprint lo modela S1 | Solo carrera. Carrera y sprint. Clasificación modelada ya en D1 | S1 no tendrá que hacer la ingesta de 2023+. La clasificación cuesta unas 320 peticiones (≈11 min, una vez) y sirve de seguro ante cambios en OpenF1 y de base para gráficos futuros (vuelta ideal, evolución de la pista, mini-sectores) sin ampliar el alcance de D1 |
| 23 | Temporadas | **2023 en adelante** (todo lo que ofrece OpenF1) | Solo 2025+ | 2023–2024 tienen FastF1 y formula1db: sirven para validar el loader y el cálculo de la posición |
| 24 | Almacenamiento del bronze | Release **`bronze-openf1` incremental**: el pipeline la descarga, comprueba el SHA, pide solo las sesiones nuevas y la vuelve a subir. El SHA va en el manifiesto de los datos | Descargarlo todo en cada ejecución (≈35 min). Caché de Actions (se borra a los 7 días). Datos en el repositorio | Reutiliza el mecanismo de `bronze-fastf1`; copia propia del histórico; segundos por ejecución |
| 25 | Posición por vuelta | La posición vigente al acabar la vuelta según el endpoint **`position`**, comparada con el orden por tiempo acumulado; las discrepancias se marcan | Solo tiempo acumulado. Sin posición | OpenF1 suele dejar sin tiempo la vuelta 1 y algunas con roja o boxes: el tiempo acumulado solo sirve de control. La comparación de 2023–2024 con FastF1 mide la fiabilidad |
| 26 | Fallos de OpenF1 | **Publicar con aviso y reintentar.** La carrera nueva sale con los resultados de F1DB aunque falten vueltas; el resumen del pipeline lista las sesiones y los endpoints que faltan; la prueba de humo exige vueltas en la última carrera con datos de alguna fuente; los 404 conocidos se anotan en el manifiesto de la copia y no se vuelven a pedir | No publicar. Publicar y reintentar a diario con un cron | Un fallo ajeno no debe dejar la web sin los resultados del GP |
| 27 | Rutina local de FastF1 | **Periódica**: cada 2–3 GP o una vez al mes, y siempre a final de temporada. El resumen del pipeline lista las carreras que aún no tienen FastF1 | Tras cada GP. Opcional sin compromiso. Dejarla | FastF1 es la tercera fuente de 2025+ (permite resolver por mayoría junto a OpenF1 y Jolpica) y aporta la telemetría de clasificación, pero el contraste no tiene que ser inmediato |
| 28 | Cómo recoge la API los datos nuevos | **Sin cambios: comprobación cada 6 h** (o al reiniciarse) | Comprobar cada 15 min. *Deploy hook* de Render | Elección del autor; un retraso de hasta 6 h es aceptable. Se descarta el *deploy hook* (secreto y redespliegue completo) |
| 29 | Alcance de la dirección de carrera y la meteo | **Gold y API, sin web**: `fact_race_control_message`, `fact_weather_sample`, `/races/{id}/race-control` y `/races/{id}/weather`, con pruebas. La web, en W2 | Solo gold. Gold, API y web | D1 se verifica de punta a punta sin mezclar un bloque de datos con uno de web |
| 30 | Mensajes y meteo de 2018–2022 | **Sí, en D1**: el loader de FastF1 descarga también `messages` y `weather`; la recarga 2018+ la hace el implementador en el PC del autor (≈200 peticiones, las vueltas ya están en la caché); los modelos unifican FastF1 (preferente) y OpenF1. El autor publica con `fastf1-publish` | Solo 2023+ y un bloque aparte más adelante. Dejar solo el código preparado | La fase 7 (degradación) necesita la temperatura de pista: 8,5 temporadas en vez de 3,5. Las sanciones sirven para F0 y W2. Ambas fuentes leen el mismo feed, así que los campos casi coinciden. Coste: D1 crece ≈1 día |

**Atribución:** D1 añade OpenF1 (CC BY-NC-SA 4.0) a las atribuciones del README, la web y la API (decisión 2).
