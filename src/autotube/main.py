from __future__ import annotations

import argparse

from autotube.core.config import load_settings
from autotube.core.health import ejecutar_diagnostico
from autotube.core.logging_config import configure_logging


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autotube",
        description="Sistema automatizado de producción para YouTube.",
    )

    subcomandos = parser.add_subparsers(dest="comando")

    subcomandos.add_parser(
        "doctor",
        help="Comprueba los requisitos y la estructura del proyecto.",
    )

    subcomandos.add_parser(
        "info",
        help="Muestra la configuración general sin revelar claves privadas.",
    )

    return parser


def mostrar_informacion() -> None:
    """Muestra un resumen seguro de la configuración."""
    settings = load_settings()

    print("\nINFORMACIÓN DE AUTOTUBE AI")
    print("=" * 60)
    print(f"Proyecto: {settings.project_root}")
    print(f"Entorno: {settings.environment}")
    print(f"Nivel de logs: {settings.log_level}")
    print(f"Datos: {settings.data_dir}")
    print(f"Salidas: {settings.output_dir}")
    print(f"Registros: {settings.logs_dir}")
    print(
        "Gemini API: "
        + ("Configurada" if settings.gemini_api_key else "Pendiente")
    )
    print(
        "Pixabay API: "
        + ("Configurada" if settings.pixabay_api_key else "Pendiente")
    )
    print(
        "YouTube: "
        + (
            "Ruta configurada"
            if settings.youtube_client_secret_file
            else "Pendiente"
        )
    )
    print("=" * 60)


def main() -> None:
    parser = crear_parser()
    argumentos = parser.parse_args()

    settings = load_settings()
    logger = configure_logging(settings)

    logger.debug("AutoTube AI iniciado con comando: %s", argumentos.comando)

    if argumentos.comando == "doctor":
        correcto = ejecutar_diagnostico()
        raise SystemExit(0 if correcto else 1)

    if argumentos.comando == "info":
        mostrar_informacion()
        return

    print("AutoTube AI está funcionando correctamente.")
    print("Usa 'autotube doctor' para comprobar el sistema.")
    print("Usa 'autotube info' para ver la configuración.")


if __name__ == "__main__":
    main()