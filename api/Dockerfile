# Imagen de la API. Se construye desde la raíz del repositorio:
#   docker build -f api/Dockerfile -t f1-api .
# Al arrancar descarga los datos de la release del pipeline (ver api/app/config.py):
#   docker run -p 8000:8000 -e F1_DATA_REPO=usuario/f1-data-platform -e F1_GITHUB_TOKEN=... f1-api
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
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

RUN useradd --create-home --uid 1000 app && mkdir /data && chown app /data
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    F1_API_DATA_DIR=/data \
    PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"

# PORT lo fijan algunos servicios de despliegue (Render, Railway...).
CMD ["sh", "-c", "uvicorn api.app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
