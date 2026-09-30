# Siguientes pasos (para retomar el 01/10/2026)

## Dónde estamos

**Hecho y en `main`:**
- Informe de situación (`informe.pdf`), plan de acción (`plan_accion.pdf`) y decisiones (`DECISIONES.md`).
- Tronco común del camino A:
  - T1: licencia, Dependabot, acciones y cabeceras de seguridad (`debe1eb`, `16ee391`).
  - T2: releases fechadas, `bronze-static-v1`, prueba de humo y copia de respaldo de la API (`96274f3`, `0276bcc`).
  - T3: sprints de 2021–2023, bandera roja, tiempos por sectores, compuestos, tipos e Italia 2018 en local (`bc2f2f9`).
- Producción:
  - Render ya sirve la API de T2.
  - La release `data-2026-09-29` y `data-latest` llevan los arreglos de datos de T3.
  - Existe `bronze-static-v1`.

**Hecho, pendiente de tu `git push`:**
- `aed0460`: FastF1 cargado en tu PC y publicado para el pipeline.
- El diagnóstico de acceso (`38d913d`) ya está subido.

**Descubrimiento importante:** `livetiming.formula1.com` responde **403** a GitHub Actions (CloudFront bloquea las IP de centros de datos), así que el pipeline no puede descargar FastF1. La decisión fue:
- ahora, cargar FastF1 en tu PC y publicarlo en la release `bronze-fastf1`;
- más adelante, OpenF1 como fuente automática.

## Qué tienes que hacer (en este orden)

1. **Subir el commit:** `git push`.
2. **Instalar la CLI de GitHub** (una sola vez):
   - `winget install GitHub.cli`
   - Abre una terminal **nueva** y ejecuta `gh auth login` (GitHub.com → HTTPS → navegador).
   - Compruébalo con `gh auth status`.
3. **Publicar lo que ya hay en tu PC** (incluida Italia 2018) y lanzar el pipeline. Desde la raíz del repo:
   - **Solo la primera vez:** instala uv en tu Windows y reconstruye el entorno. El Python que usaba `.venv` estaba en la carpeta privada de la app de Claude (MSIX) y tu terminal no lo ve; de ahí el error «No Python at …».
     1. `winget install --id=astral-sh.uv -e`
     2. Abre una terminal nueva y ejecuta `uv sync --all-groups`.
   - Después:
     ```
     uv run f1-ingest fastf1-publish --skip-ingest --run-pipeline
     ```

   Qué debe pasar:
   - empaqueta unos 31 MB;
   - crea la release `bronze-fastf1`;
   - muestra «Publicada la release bronze-fastf1.» y «Pipeline lanzado».
4. **Revisar la ejecución del pipeline** (Actions → «Pipeline de datos»). Pásame:
   - la salida del paso «Acceso al cronometraje de la F1 (diagnóstico)»: códigos de livetiming, OpenF1 y Jolpica;
   - la línea del resumen «Copia de FastF1: …».
5. **PR de Dependabot:**
   - **#2 (React 19.3.0):**
     - Su CI falló en «Lint, tipos y compilación», pero en local los tres pasos pasan con React 19.3.0.
     - En el PR: *Checks* → **Re-run failed jobs**.
     - Si sale en verde, fusiónalo. Si vuelve a fallar, pásame las últimas líneas de ese paso.
   - **#6 (uv 0.12.21 en el Dockerfile):** fusiónalo solo si pasa el trabajo «Imagen Docker de la API».
6. **Rutina tras cada GP** (a partir de ahora): `uv run f1-ingest fastf1-publish --run-pipeline`
   - Sin `--run-pipeline`, los datos se publican el lunes a las 06:00 UTC.

   Códigos de salida de la orden:
   - 0: publicada.
   - 1: alguna carrera aún sin datos; se reintenta la semana siguiente.
   - 3: falta `gh` o no hay sesión; la copia queda en `dist/`.
   - 4: la copia local tiene menos carreras que la publicada.
   - 5: no se pudo consultar la release.
   - 6: falló la subida; repetir con `--skip-ingest`.
   - 7: publicada, pero hay que lanzar el pipeline a mano.

## Qué decirme para seguir

«Retoma: he hecho los pasos 1–5» y pégame lo del paso 4. Con eso:
1. compruebo que la API cargue los datos nuevos (Italia 2018);
2. decidimos la fuente automática según el diagnóstico (OpenF1 o Jolpica);
3. seguimos con el camino A: **C1** (coches compartidos, abreviaturas y dorsales) y **C2** (unit tests de la fusión de vueltas), con el equipo de tres agentes (un implementador y dos revisores).

## Notas abiertas para bloques posteriores

- **C2:** probar la regla de bandera roja cuando hay menos de 3 pilotos.
- **C3:** etiqueta con coordenada NaN en «Evolución del campeonato» (`/es/seasons/2021`).
- **D1:**
  - 2025 no tiene ninguna bandera roja marcada.
  - Elegir la fuente automática (OpenF1) según el diagnóstico.
- **A1/A2:** ninguna página de la web se cachea (todas dinámicas); región `fra1` en Vercel (decidido, más adelante).
- **Norma nueva:** los cambios del Dockerfile o de `release.py` no se dan por buenos hasta que pase la CI de la imagen Docker.
