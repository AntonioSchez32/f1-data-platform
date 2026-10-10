#!/usr/bin/env bash
# Descarga el último snapshot de datos verificado: `bronze.tar.gz` y `manifest.json` de la release
# indicada (normalmente `data-latest`) o, si falta algún fichero o el SHA-256 de `bronze.tar.gz` no
# coincide con el del manifiesto, de las releases fechadas (`data-AAAA-MM-DD`), de la más reciente
# a la más antigua (como mucho `MAX_FECHADAS`). Lo usan el pipeline y la CI (auditoría ING-01).
#
# `gh release download` termina con 0 aunque uno de los patrones no encuentre nada, y
# `gh release upload --clobber` borra el fichero antes de subir el nuevo: `data-latest` puede
# quedar con el manifiesto y sin `bronze.tar.gz` (o con el de otra ejecución) si una subida falla.
#
# Uso: scripts/descargar_snapshot.sh <directorio> [release]
# Escribe en la salida estándar la release usada; los avisos van a la salida de errores. Termina
# con 1 si no hay ningún snapshot válido. Necesita `gh` (con GH_TOKEN y GH_REPO), `jq` y `sha256sum`.
set -uo pipefail

DIR="${1:?Uso: descargar_snapshot.sh <directorio> [release]}"
LATEST="${2:-data-latest}"
MAX_FECHADAS="${MAX_FECHADAS:-3}"

# Descarga y verifica una release en $DIR (vaciado antes: nunca se mezclan ficheros de dos).
descargar() {
  local tag="$1" expected actual
  rm -rf "$DIR"
  mkdir -p "$DIR"
  if ! gh release download "$tag" --pattern bronze.tar.gz --pattern manifest.json --dir "$DIR" > /dev/null 2>&1; then
    echo "No se pudo descargar la release $tag." >&2
    return 1
  fi
  if [ ! -f "$DIR/bronze.tar.gz" ] || [ ! -f "$DIR/manifest.json" ]; then
    echo "A la release $tag le falta bronze.tar.gz o manifest.json." >&2
    return 1
  fi
  expected="$(jq -r '.files["bronze.tar.gz"].sha256 // empty' "$DIR/manifest.json" 2> /dev/null || true)"
  actual="$(sha256sum "$DIR/bronze.tar.gz" | cut -d' ' -f1)"
  if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then
    echo "En la release $tag, bronze.tar.gz no coincide con el SHA-256 de manifest.json." >&2
    return 1
  fi
}

if descargar "$LATEST"; then
  echo "$LATEST"
  exit 0
fi

fechadas="$(gh release list --limit 200 --json tagName,createdAt \
  | jq -r --argjson n "$MAX_FECHADAS" \
      '[.[] | select(.tagName | test("^data-[0-9]{4}-[0-9]{2}-[0-9]{2}"))] | sort_by(.createdAt) | reverse | .[:$n] | .[].tagName' \
  || true)"
for tag in $fechadas; do
  if descargar "$tag"; then
    echo "No se pudo usar $LATEST; se parte de la release fechada $tag." >&2
    echo "$tag"
    exit 0
  fi
done
rm -rf "$DIR"
echo "No hay ningún snapshot válido ($LATEST ni las $MAX_FECHADAS releases fechadas más recientes)." >&2
exit 1
