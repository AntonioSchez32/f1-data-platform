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

## Consecuencias para el plan
- El tronco común queda en T1 (sin el cambio de región), T2 y T3.
- D2: Jolpica sustituye al volcado Ergast 2022. Su atribución y la licencia NC-SA se reflejan en README, web y API.
- W1: la reorganización a 5 pestañas entra en la iteración de web. «Récords» pasa a «Historia» en W2.
- Siguen aplazados los casos de numeración de San Marino y Japón 1994 y Bélgica 2001.
