from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


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
    raiz = Path.cwd()

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
    ]

    print("\nDIAGNÓSTICO DE AUTOTUBE AI")
    print("=" * 60)

    todo_correcto = True

    for nombre, correcto, detalle in comprobaciones:
        estado = "OK" if correcto else "ERROR"
        print(f"[{estado:<5}] {nombre}: {detalle}")

        if not correcto:
            todo_correcto = False

    print("=" * 60)

    if todo_correcto:
        print("El sistema base está listo para continuar.")
    else:
        print("Hay requisitos pendientes que deben corregirse.")

    return todo_correcto