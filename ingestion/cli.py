"""Punto de entrada: `uv run f1-ingest <fuente> [opciones]`."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from ingestion.config import FASTF1_FIRST_SEASON, LEGACY_CSV_DIR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="f1-ingest", description=__doc__)
    sub = parser.add_subparsers(dest="source", required=True)

    f1db = sub.add_parser("f1db", help="Última release de F1DB (GitHub)")
    f1db.add_argument("--force", action="store_true", help="Recargar aunque no haya release nueva")

    ff1 = sub.add_parser("fastf1", help="Vueltas, neumáticos y telemetría (2018+)")
    ff1.add_argument(
        "--season",
        type=int,
        nargs="+",
        required=True,
        help=f"Temporada(s) a cargar (>= {FASTF1_FIRST_SEASON})",
    )
    ff1.add_argument("--round", type=int, nargs="+", dest="rounds", help="Solo estas rondas")
    ff1.add_argument("--telemetry", action="store_true", help="Incluir telemetría de clasificación")
    ff1.add_argument("--force", action="store_true", help="Recargar carreras ya existentes")

    publish = sub.add_parser(
        "fastf1-publish",
        help="Cargar FastF1 en este equipo y publicarlo para el pipeline (release bronze-fastf1)",
        description="GitHub Actions no puede descargar el cronometraje de la F1 (403): FastF1 se "
        "carga aquí, se empaqueta en dist/bronze-fastf1.tar.gz y se sube con la CLI gh.",
    )
    publish.add_argument(
        "--season",
        type=int,
        nargs="+",
        help="Temporada(s) a cargar (por defecto, la en curso; en enero, también la anterior)",
    )
    publish.add_argument(
        "--skip-ingest", action="store_true", help="No cargar nada: empaquetar lo que ya hay"
    )
    publish.add_argument(
        "--dry-run",
        action="store_true",
        help="Cargar y empaquetar, pero no subir nada ni consultar GitHub",
    )
    publish.add_argument(
        "--run-pipeline", action="store_true", help="Lanzar el pipeline tras subir la copia"
    )
    publish.add_argument("--out", type=Path, default=Path("dist"), help="Directorio de salida")
    publish.add_argument("--repo", help="Repositorio (usuario/nombre); por defecto, el del remoto")

    legacy = sub.add_parser("legacy", help="CSV históricos de formula1db.com (carga única)")
    legacy.add_argument("--path", type=Path, default=LEGACY_CSV_DIR)

    ergast = sub.add_parser("ergast", help="Volcado CSV de Ergast (solo validación, carga única)")
    ergast.add_argument("--path", type=Path, help="Ruta a f1db_csv.zip")

    snap = sub.add_parser("snapshot", help="Empaquetar o restaurar los datos del pipeline")
    snap_sub = snap.add_subparsers(dest="action", required=True)
    pack = snap_sub.add_parser("pack", help="Generar el snapshot (bronze, f1.duckdb, Parquet)")
    pack.add_argument("--out", type=Path, default=Path("dist"), help="Directorio de salida")
    pack.add_argument("--tag", help="Release fechada donde se publicará (p. ej. data-2026-10-05)")
    pack.add_argument(
        "--fastf1-manifest",
        type=Path,
        help="bronze-fastf1.json de la copia de FastF1 superpuesta (se anota en el manifiesto)",
    )
    static = snap_sub.add_parser(
        "pack-static", help="Copia inmutable de las fuentes estáticas (formula1db.com y Ergast)"
    )
    static.add_argument("--out", type=Path, default=Path("dist"), help="Directorio de salida")
    restore = snap_sub.add_parser(
        "restore", help="Restaurar bronze desde bronze.tar.gz o bronze-static.tar.gz"
    )
    restore.add_argument("archive", type=Path)
    restore.add_argument(
        "--replace", action="store_true", help="Vaciar antes las carpetas de las fuentes que trae"
    )
    ff1_restore = snap_sub.add_parser(
        "restore-fastf1", help="Superponer la copia de FastF1 (bronze-fastf1.tar.gz)"
    )
    ff1_restore.add_argument("archive", type=Path)
    ff1_restore.add_argument(
        "--previous",
        type=Path,
        help="manifest.json del snapshot: avisa si la copia trae menos carreras que él",
    )
    ff1_restore.add_argument(
        "--copy-manifest",
        type=Path,
        help="bronze-fastf1.json de la copia: avisa si es más antigua que la ya usada",
    )
    notes = snap_sub.add_parser("notes", help="Texto de la release a partir de manifest.json")
    notes.add_argument("manifest", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # La consola de Windows usa cp1252; los mensajes y las notas de la release llevan tildes.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    # Importaciones diferidas: fastf1 tarda en importarse y no hace falta para f1db.
    if args.source == "f1db":
        from ingestion import f1db_loader

        print(json.dumps(f1db_loader.load(force=args.force), indent=2))
        return 0

    if args.source == "fastf1":
        from ingestion.fastf1_publish import ingest

        failed = ingest(args.season, args.rounds, telemetry=args.telemetry, force=args.force)
        for label in failed:
            print(f"  ERROR: {label}", file=sys.stderr)
        return 1 if failed else 0

    if args.source == "fastf1-publish":
        from ingestion import fastf1_publish

        return fastf1_publish.publish(
            args.season,
            out_dir=args.out,
            do_ingest=not args.skip_ingest,
            do_upload=not args.dry_run,
            run_pipeline=args.run_pipeline,
            repo=args.repo,
        )

    if args.source == "legacy":
        from ingestion import legacy_loader

        print(json.dumps(legacy_loader.load(args.path), indent=2))
        return 0

    if args.source == "ergast":
        from ingestion import ergast_loader

        stats = ergast_loader.load(args.path) if args.path else ergast_loader.load()
        print(json.dumps(stats, indent=2))
        return 0

    if args.source == "snapshot":
        from ingestion import snapshot

        if args.action == "pack":
            fastf1_copy = (
                json.loads(args.fastf1_manifest.read_text(encoding="utf-8"))
                if args.fastf1_manifest
                else None
            )
            manifest = snapshot.pack(args.out, release_tag=args.tag, fastf1_copy=fastf1_copy)
            print(json.dumps(manifest["files"], indent=2))
        elif args.action == "pack-static":
            from ingestion.config import BRONZE_DIR

            out = snapshot.pack_static(BRONZE_DIR, args.out / snapshot.STATIC_ARCHIVE)
            print(f"{out} ({out.stat().st_size} bytes, sha256 {snapshot.sha256(out)})")
        elif args.action == "restore":
            print(
                "Fuentes restauradas: "
                + ", ".join(snapshot.restore_bronze(args.archive, replace=args.replace))
            )
        elif args.action == "restore-fastf1":
            copy = snapshot.restore_fastf1(args.archive)
            print("Copia de FastF1 superpuesta: " + ", ".join(f"{s}: {n}" for s, n in copy.items()))
            previous = (
                json.loads(args.previous.read_text(encoding="utf-8"))
                if args.previous and args.previous.exists()
                else {}
            )
            copy_manifest = (
                json.loads(args.copy_manifest.read_text(encoding="utf-8"))
                if args.copy_manifest
                else {}
            )
            # No son errores: se superpone igualmente y el snapshot conserva lo que no trae.
            prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") == "true" else "Aviso: "
            for warning in snapshot.fastf1_copy_warnings(previous, copy, copy_manifest):
                print(prefix + warning)
        else:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            sys.stdout.write(snapshot.release_notes(manifest))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
