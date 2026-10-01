# Imagen de la API. Se construye desde la raíz del repositorio:
#   docker build -f api/Dockerfile --build-arg F1_DATA_REPO=usuario/f1-data-platform -t f1-api .
# Al arrancar descarga los datos de la release del pipeline (ver api/app/config.py):
#   docker run -p 8000:8000 -e F1_DATA_REPO=usuario/f1-data-platform f1-api

# Versión fijada de uv (Dependabot la actualiza).
FROM ghcr.io/astral-sh/uv:0.12.21 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias primero (capa reutilizable mientras no cambie uv.lock): solo duckdb y FastAPI.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-default-groups --group api --no-install-project

COPY ingestion/__init__.py ingestion/
COPY api/__init__.py api/
COPY api/app api/app
RUN uv sync --locked --no-default-groups --group api

# Copia de respaldo de los datos: si sigue vigente al arrancar, no hay que descargarla (el disco
# de Render free se borra en cada arranque), y si GitHub no responde, la API arranca con ella.
# Render pasa las variables del servicio como argumentos de construcción. Sin F1_DATA_REPO, o si
# la descarga falla, la imagen se construye igual, sin copia. La copia se renueva cada vez que
# cambia el código de la API (la capa depende de las anteriores); si queda antigua, la API
# descarga la versión publicada al arrancar.
ARG F1_DATA_REPO=""
ARG F1_DATA_TAG=data-latest
RUN mkdir -p /opt/f1-seed \
    && if [ -n "$F1_DATA_REPO" ]; then \
         .venv/bin/python -m api.app.release --repo "$F1_DATA_REPO" --tag "$F1_DATA_TAG" --out /opt/f1-seed \
         || echo "Aviso: no se pudo descargar la copia de respaldo de los datos"; \
       fi \
    && chmod -R a+rX /opt/f1-seed

RUN useradd --create-home --uid 1000 app && mkdir /data && chown app /data
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    F1_API_DATA_DIR=/data \
    F1_API_SEED_DIR=/opt/f1-seed \
    PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"

# PORT lo fijan algunos servicios de despliegue (Render, Railway...).
CMD ["sh", "-c", "uvicorn api.app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
