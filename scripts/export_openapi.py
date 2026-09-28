"""Exporta el contrato OpenAPI de la API a `web/src/lib/api/openapi.json`.

La web genera sus tipos TypeScript a partir de este fichero (`npm run gen:api`), así que un
cambio en la API que rompa la web se detecta al compilar. Uso, desde la raíz del proyecto:

    uv run python scripts/export_openapi.py
"""

import json
from pathlib import Path

from api.app.main import create_app

TARGET = Path("web/src/lib/api/openapi.json")
TARGET.parent.mkdir(parents=True, exist_ok=True)
TARGET.write_text(
    json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(f"{TARGET} actualizado")
