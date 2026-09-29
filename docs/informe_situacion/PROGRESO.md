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

## Implementación (desde el 30/09)
- Equipo de 3 agentes: IMPLEMENTADOR a196494f17913b76e · REVISOR_A (corrección/datos, coordina) a84fb99bcf7d68b2b · REVISOR_B (seguridad/operación) ac5cfda629d74fac9.
- Orden: revisión de T1 (debe1eb) → T2 → T3. Un commit por bloque, sin push (lo hace el usuario).
- Si se cortan por el límite: reanudar cada agente con SendMessage a su ID ("continúa donde lo dejaste").
