from __future__ import annotations

import argparse

from autotube.core.health import ejecutar_diagnostico


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autotube",
        description="Sistema automatizado de producción para YouTube.",
    )

    subcomandos = parser.add_subparsers(dest="comando")

    subcomandos.add_parser(
        "doctor",
        help="Comprueba Python, Git, FFmpeg y la estructura del proyecto.",
    )

    return parser


def main() -> None:
    parser = crear_parser()
    argumentos = parser.parse_args()

    if argumentos.comando == "doctor":
        correcto = ejecutar_diagnostico()
        raise SystemExit(0 if correcto else 1)

    print("AutoTube AI está funcionando correctamente.")
    print("Usa 'autotube doctor' para comprobar el sistema.")


if __name__ == "__main__":
    main()