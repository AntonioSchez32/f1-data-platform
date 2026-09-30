# Siguientes pasos (actualizado el 30/09/2026, noche)

## Dónde estamos

**En `main` y en producción:**
- Informe de situación, plan de acción y decisiones (`docs/informe_situacion/`).
- Tronco común del camino A:
  - **T1:** licencia, Dependabot, acciones fijadas y cabeceras de seguridad.
  - **T2:** releases fechadas, `bronze-static-v1`, prueba de humo y copia de respaldo de la API.
  - **T3:** sprints de 2021–2023, bandera roja, tiempos por sectores, compuestos y tipos.
- FastF1 cargado en tu PC y publicado en la release `bronze-fastf1` (`f1-ingest fastf1-publish`).
- La release `data-2026-09-30` ya incluye Italia 2018. La API la sirve.
- PR de Dependabot #2 y #6 fusionados. CI en verde.

**Hecho, pendiente de tu `git push`:**
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

## Qué tienes que hacer ahora (a mano)

1. **Subir los commits:** `git push`. Comprueba que la CI sale en verde (o dime «comprueba la CI»).
2. **Publicar los datos nuevos de C1 y C2:** Actions → «Pipeline de datos» → *Run workflow*. Deja el campo de temporadas vacío y sin casillas marcadas.
   - O desde tu terminal: `gh workflow run pipeline.yml`.
   - Ninguna tabla pierde más del 2 %, así que no hace falta `allow_shrink`.
3. **Nada más de despliegue:** Vercel y Render se despliegan solos. La web y la API son compatibles en cualquier orden.

## Rutina fija tras cada GP (hasta que llegue D1)

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

Orden recomendado (ver `plan_accion.pdf`). Cada bloque se hace con el equipo de tres agentes (un implementador y dos revisores) y un commit por bloque.

| Bloque | Contenido | Estimación |
|---|---|---|
| **D1** | **Fuente automática: OpenF1** (decisión 13): vueltas, stints, paradas, dirección de carrera y meteorología de las carreras nuevas, sin depender de tu PC. Incluye las banderas rojas de 2025 (hoy ninguna). | 3–4 días |
| **D2** | **Jolpica** como segunda fuente de contraste (sustituye al volcado Ergast de 2022). Validación cruzada de 2023–2026. | 1–2 días |
| **D3** | Eventos históricos (SC/VSC/banderas rojas, seed desde Wikipedia/TracingInsights) y compuestos Pirelli C1–C6 desde 2024 (seed a partir de las notas de prensa de Pirelli). | 3 días |
| **S1** | Vueltas de las carreras al sprint (29 sprints) con selector carrera/sprint en la web. | 4–6 días |
| **C3** | Errores de lectura de los gráficos. Entre ellos: la referencia de clasificación, el eje de temporadas, Ferrari 1950–57, las etiquetas solapadas, el formato de miles y el NaN de «Evolución del campeonato» en `/es/seasons/2021`. | 2 días |
| **W1** | Navegación de 5 pestañas de carrera (decisión 7). | 3 días |
| **W2** | Tanda 1 de gráficos: race trace (1990+), franjas SC/VSC, matriz de resultados, récords ampliados, eliminación matemática. | 6–8 días |
| **A1** | Arquitectura A: `justfile`, sources dbt de todo el bronze, disparo por calendario. | 2–3 días |
| **F0** | Preparar la fase 7: vueltas limpias, corrección de combustible, categorías de abandono. | 3–4 días |

Por decidir o por hacer más adelante (acciones tuyas):
- Región `fra1` en Vercel (decisión 6).
- Documentación de dbt en GitHub Pages (decisión 10).
- Publicar el issue de correcciones a F1DB (decisión 11). Hay que añadir el caso de Italia 2026 (race 1162): F1DB repite la parada 2 de 9 pilotos y no tiene su parada 1.

## Qué decirme para seguir

«Retoma» (y, si lo has hecho, «he hecho push y lanzado el pipeline»). Con eso:
1. compruebo la CI y que la API sirva los datos de C1 y C2;
2. lanzo **D1 (OpenF1 automático)** con el equipo de tres agentes.

## Notas técnicas abiertas

- **DBT-7:** unificar las definiciones de puntos entre la API y dbt (hoy ya coinciden gracias al redondeo).
- **A1/A2:** ninguna página de la web se cachea (todas son dinámicas).
- **API:** si la descarga de la release fechada falla (vimos un 500 puntual de GitHub), podría recurrir a `data-latest`, que tiene el mismo SHA-256.
- **Norma:** los cambios del Dockerfile o de `release.py` no se dan por buenos hasta que pase la CI de la imagen Docker.
- **Entorno:** el Python de la app de Claude está en su carpeta privada (MSIX). En tu terminal usa siempre `uv run …`.
