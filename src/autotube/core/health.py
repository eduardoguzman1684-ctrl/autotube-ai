from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

from autotube.core.config import load_settings


def obtener_version(comando: list[str]) -> str | None:
    """Ejecuta un comando y devuelve su primera línea."""
    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        salida = resultado.stdout.strip() or resultado.stderr.strip()
        return salida.splitlines()[0] if salida else "Disponible"

    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def ejecutar_diagnostico() -> bool:
    """Comprueba los requisitos fundamentales de AutoTube AI."""
    settings = load_settings()
    raiz = settings.project_root

    comprobaciones = [
        (
            "Python 3.12",
            sys.version_info[:2] == (3, 12),
            platform.python_version(),
        ),
        (
            "Entorno virtual",
            sys.prefix != sys.base_prefix,
            sys.prefix,
        ),
        (
            "Git",
            shutil.which("git") is not None,
            obtener_version(["git", "--version"]) or "No encontrado",
        ),
        (
            "FFmpeg",
            shutil.which("ffmpeg") is not None,
            obtener_version(["ffmpeg", "-version"]) or "No encontrado",
        ),
        (
            "Carpeta src",
            (raiz / "src").is_dir(),
            str(raiz / "src"),
        ),
        (
            "Archivo pyproject.toml",
            (raiz / "pyproject.toml").is_file(),
            str(raiz / "pyproject.toml"),
        ),
        (
            "Archivo .env",
            (raiz / ".env").is_file(),
            str(raiz / ".env"),
        ),
        (
            "Carpeta data",
            settings.data_dir.is_dir(),
            str(settings.data_dir),
        ),
        (
            "Carpeta output",
            settings.output_dir.is_dir(),
            str(settings.output_dir),
        ),
        (
            "Carpeta logs",
            settings.logs_dir.is_dir(),
            str(settings.logs_dir),
        ),
        (
            "Carpeta config",
            settings.config_dir.is_dir(),
            str(settings.config_dir),
        ),
    ]

    print("\nDIAGNÓSTICO DE AUTOTUBE AI")
    print("=" * 70)

    todo_correcto = True

    for nombre, correcto, detalle in comprobaciones:
        estado = "OK" if correcto else "ERROR"
        print(f"[{estado:<5}] {nombre}: {detalle}")

        if not correcto:
            todo_correcto = False

    print("=" * 70)

    claves = [
        ("Gemini API", bool(settings.gemini_api_key)),
        ("Pixabay API", bool(settings.pixabay_api_key)),
        (
            "YouTube Client Secret",
            bool(settings.youtube_client_secret_file),
        ),
    ]

    print("\nSERVICIOS OPCIONALES")
    print("=" * 70)

    for nombre, configurado in claves:
        estado = "CONFIGURADO" if configurado else "PENDIENTE"
        print(f"[{estado:<11}] {nombre}")

    print("=" * 70)

    if todo_correcto:
        print("El sistema base está listo para continuar.")
    else:
        print("Hay requisitos fundamentales que deben corregirse.")

    return todo_correcto