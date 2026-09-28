"""Punto de entrada: `uv run f1-ingest <fuente> [opciones]`."""

import argparse
import json
import logging
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

    legacy = sub.add_parser("legacy", help="CSV históricos de formula1db.com (carga única)")
    legacy.add_argument("--path", type=Path, default=LEGACY_CSV_DIR)

    ergast = sub.add_parser("ergast", help="Volcado CSV de Ergast (solo validación, carga única)")
    ergast.add_argument("--path", type=Path, help="Ruta a f1db_csv.zip")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    # Importaciones diferidas: fastf1 tarda en importarse y no hace falta para f1db.
    if args.source == "f1db":
        from ingestion import f1db_loader

        print(json.dumps(f1db_loader.load(force=args.force), indent=2))
        return 0

    if args.source == "fastf1":
        from ingestion import fastf1_loader

        failed = []
        for season in args.season:
            summary = fastf1_loader.load_season(
                season, rounds=args.rounds, telemetry=args.telemetry, force=args.force
            )
            print(
                f"{season}: {len(summary.loaded)} cargadas, "
                f"{len(summary.skipped)} ya existentes, {len(summary.failed)} con error"
            )
            failed += summary.failed
            if summary.rate_limited:
                # La carga es incremental: no es un error, se completa en la próxima ejecución.
                print(
                    "Límite de 500 peticiones/hora de la API alcanzado; "
                    "vuelve a ejecutar el comando más tarde para continuar."
                )
                break
        for label in failed:
            print(f"  ERROR: {label}", file=sys.stderr)
        return 1 if failed else 0

    if args.source == "legacy":
        from ingestion import legacy_loader

        print(json.dumps(legacy_loader.load(args.path), indent=2))
        return 0

    if args.source == "ergast":
        from ingestion import ergast_loader

        stats = ergast_loader.load(args.path) if args.path else ergast_loader.load()
        print(json.dumps(stats, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
