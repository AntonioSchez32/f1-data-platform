# Informe de situación del proyecto: progreso del trabajo nocturno (29-30/09/2026)

Encargo del usuario (resumen):
1. Datos que faltan: volver a analizarlos, ver cómo obtenerlos y contrastarlos, e investigar en la web más allá de las fuentes ya usadas. Explorar si se pueden recuperar las vueltas de las carreras al sprint.
2. Documentar con exactitud la arquitectura y la estructura del proyecto (LaTeX/PDF), investigar si podría estructurarse mejor y proponer alternativas.
3. Documentar la arquitectura de datos:
   - esquemas en estrella y datos en bruto;
   - capas bronze, silver y gold, cómo se alimentan unas a otras y qué ocurre en cada fase;
   - qué hace cada parte del código, con un detalle medio-alto;
   - propuestas de mejora.
4. Gráficos y récords:
   - investigar formula1db.com, statsf1, documentos FIA y otros proyectos;
   - evaluar los gráficos actuales (útiles, poco útiles, repetidos);
   - proponer nuevos, algunos inéditos.

Salida: `docs/informe_situacion/informe.tex`, compilado a PDF. Las notas de trabajo de cada agente están en `notas/`.

## Estado de las notas

| Nota | Tema | Estado |
|---|---|---|
| notas/01_inventario_huecos.md | Inventario cuantificado de datos que faltan (DuckDB + docs) | HECHA |
| notas/02_fuentes_externas.md | Fuentes web para cubrir los huecos, licencias y cómo contrastar | HECHA |
| notas/03_sprint.md | Viabilidad de las vueltas de las carreras al sprint | HECHA |
| notas/04_arquitectura_datos.md | Ingesta + dbt: capas, estrella, linaje, cada modelo | HECHA |
| notas/05_arquitectura_app.md | API + web + CI/CD + despliegue: recorrido por el código | HECHA |
| notas/06_alternativas.md | Investigación de estructuras y arquitecturas alternativas | HECHA |
| notas/07_mejoras_codigo.md | Revisión del código e infraestructura: mejoras concretas | HECHA |
| notas/08_graficos_externos.md | Catálogo de gráficos y récords de otras webs y proyectos | HECHA |
| notas/09_graficos_propios.md | Evaluación de nuestros gráficos + ideas nuevas | HECHA |
| informe.tex / informe.pdf | Síntesis final | HECHA (build/informe.pdf, 171 págs.) |

## Cómo retomarlo
- Si una nota falta o está incompleta, relanzar su agente con el mismo encargo (ver la sección «Encargos» del final).
- Cuando estén todas, redactar `informe.tex`, compilarlo con `latexmk -xelatex` y revisar el PDF.

## Encargos
Los encargos completos están en el historial de la sesión. Resumen: cada agente escribe su nota en `notas/` sin tocar el código del repositorio.

## Registro
- 29/09 noche: se lanzan los 9 agentes. Los 9 se cortan por el límite de sesión (se restablece a las 4:50) antes de escribir sus notas.
- Tras el restablecimiento: se reanudan los 9 desde su transcripción, con la indicación de guardar las notas de forma incremental.
- 29/09 07:45: segunda parada por límite (se restablece a las 6:20). Seis notas hechas (01, 04–08); se reanudan 02, 03 y 09.
- 29/09 ~08:00: las 9 notas HECHAS. Empieza la síntesis: md2tex.py convierte notas/ → capitulos/; informe.tex = síntesis propia + capítulos.
- 29/09 ~08:30: informe.pdf compilado (171 páginas). Vigilancia automática desactivada. Siguiente: plan de acción con alternativas (plan_accion.tex).
- 30/09: plan_accion.pdf (8 págs.) con 4 caminos y camino A recomendado. Corregido en el informe el alcance del race trace (1990+, no 1950+).
- 30/09: decisiones registradas en DECISIONES.md. Informe y plan versionados en el repositorio. Empieza la implementación del tronco común (T1, T2, T3).
- 30/09: revisión de T1 aplicada (commit «T1: arreglos de la revisión»): licencias de los datos por fuente, Dependabot sin las mayores que no pasan (TS 7, ESLint 10, Python 3.14, pandas 3) y con pre-commit y cooldown, @types/node 24, fetch deduplicado y con espera de 60 s + 20 s, runners ubuntu-24.04, prueba de cabeceras y CSP. Pendiente del usuario: desactivar la Vercel Toolbar, cerrar las PR de Dependabot n.º 1, 3, 4 y 5, mirar el log del job de uv y lanzar el pipeline a mano antes del lunes.
- 30/09: T2 (robustez operativa): releases fechadas e inmutables (`data-AAAA-MM-DD`, retención de 8) con `data-latest` como puntero (manifest.json el último, `release_tag`); copia inmutable `bronze-static-v1` de formula1db.com y Ergast, restaurada con `--replace` en cada ejecución; prueba de humo de la API contra el snapshot nuevo antes de publicar (con `cambios_esperados.json` y el input de emergencia `allow_shrink`); API con reintentos, arranque con la última copia verificada o la copia de la imagen Docker si GitHub falla, y `/health` con consulta real y estado del refresco; token solo en los pasos con `gh`. La primera ejecución del pipeline crea `bronze-static-v1` y la primera release fechada.
- 30/09: T3 (arreglos de datos rápidos): `has_sprint` desde los resultados de sprint (12 sprints de 2021–2023) y `has_sprint_qualifying` en la API/web; bandera roja en la vuelta que contiene la suspensión (24 vueltas de 22 carreras, São Paulo 2024 v.33 incluida; vars `red_flag_*`); 570 tiempos de 2025–2026 como suma de sectores (`lap_time_ms:sectors`, `confirmed_by fastf1:sectors`); compuestos NAN/NONE/UNKNOWN/'' a nulo; sin HUGEINT; tabla huérfana borrada de la base local; Italia 2018 de FastF1 recuperada con un rodeo del fallo de FastF1 3.8.3 (cargada en el bronze local). dbt build 115 PASS, QA sin cambios (23 PASS, 17 INFO). Pendiente del usuario: lanzar el pipeline a mano con `seasons=2018` para publicar Italia 2018.

## Implementación (desde el 30/09)
- Equipo de 3 agentes: IMPLEMENTADOR a196494f17913b76e · REVISOR_A (corrección/datos, coordina) a84fb99bcf7d68b2b · REVISOR_B (seguridad/operación) ac5cfda629d74fac9.
- Orden: revisión de T1 (debe1eb) → T2 → T3. Un commit por bloque, sin push (lo hace el usuario).
- Si se cortan por el límite: reanudar cada agente con SendMessage a su ID ("continúa donde lo dejaste").
- 29/09: la CI de bc2f2f9 falló en «Arranque sin GitHub con la copia de la imagen» (PermissionError: la copia se descargaba con 0600 como root y la API corre como app). Arreglado en el commit siguiente, aprobado por los dos revisores. Norma nueva: los cambios del Dockerfile o de release.py no se dan por buenos hasta que pase el job «Imagen Docker de la API».
- 30/09: livetiming.formula1.com responde 403 a GitHub Actions (CloudFront, cualquier User-Agent): el pipeline no puede descargar FastF1. Decisión del usuario: carga local de FastF1 publicada en la release `bronze-fastf1` y, más adelante, OpenF1 automático. Nuevo equipo: IMPLEMENTADOR a81adc7c5166aa026 · REVISOR_A abd8d55db2bc39fa8 · REVISOR_B a010b93434c6d53dd.
- 30/09: FastF1 desde el equipo del autor: livetiming.formula1.com responde 403 a GitHub Actions. Nueva orden `f1-ingest fastf1-publish` (carga, empaqueta `bronze/fastf1` en `bronze-fastf1.tar.gz` + manifiesto y lo sube con `gh` a la release `bronze-fastf1`); el pipeline ya no ingesta FastF1: comprueba el SHA-256 y superpone la copia (solo `bronze/fastf1/<tabla>/season=AAAA/round=RR.parquet`), anota la copia usada en manifest.json y en las notas, y diagnostica también OpenF1 y Jolpica. La prueba de humo busca vueltas en la temporada anterior si la última aún no tiene. Pendiente del usuario: `winget install GitHub.cli`, `gh auth login` y `uv run f1-ingest fastf1-publish --skip-ingest --run-pipeline`.
- 30/09 (retoma): diagnóstico desde GitHub: livetiming 403, OpenF1 200, Jolpica 200. Decisión: OpenF1 + Jolpica automáticos tras C1 y C2. Equipo C1/C2: IMPLEMENTADOR a994c509ccf5c5155 · REVISOR_A a493fa3e36eae8af9 · REVISOR_B abf964635530c4e13.
- 30/09: C1 (correcciones visibles), aprobado por los dos revisores: `driver_number` en /laps, /stints y /pit-lane-passes y series por coche en la web (Behra #20/#24 en Bélgica 1955, Fangio #20/#26 en Mónaco 1956); `driver_code` único por carrera en /results (MSC/RSC, TMO/FMO; 0 repetidos en 1 164 carreras); dorsales solo de sesiones de carrera, parrilla y clasificación (parejas carrera-dorsal con dos pilotos 294 → 151, todas anteriores a 1982; test de unicidad desde 1982); desempate determinista en `int_lap_numbering` (Pacífico 1994 y São Paulo 2023 pasan a inconsistent); ya no se ocultan 4 812 vueltas de coches compartidos y descalificados; dorsal '' → '0' (Hill 1993-94, Scheckter 1973). dbt 124 PASS, QA sin regresiones. Pendiente del usuario: `git push` y lanzar el pipeline para publicar los datos nuevos.
- 30/09: C2 (pruebas), aprobado por los dos revisores: 14 unit tests de dbt (int_laptimes con una regla por test: fusión y validation_status, mayoría, sectores, seed, recálculo y mayoría de posición, A6, desfase de numeración, relleno de Ergast, timing_convention y bandera roja con vars fijadas; int_lap_numbering con sus estados, desempates y mínimo de casos; parse_duration_ms; equipo principal de agg_driver_season); tests de grano y relationships en paradas, standings, telemetría y agg_*. 30/30 mutaciones detectadas en una copia. Datos: fact_pit_stops sin los 9 duplicados de F1DB en Italia 2026, equipo principal determinista (13 empates) y puntos redondeados a 2 decimales en agg_* y /rankings. dbt 173 PASS. Pendiente del usuario: `git push` y lanzar el pipeline.
