from __future__ import annotations

import subprocess
from pathlib import Path

from autotube.core.config import load_settings


def ejecutar_git(argumentos: list[str], raiz: Path) -> subprocess.CompletedProcess[str]:
    """Ejecuta un comando de Git dentro del proyecto."""
    return subprocess.run(
        ["git", *argumentos],
        cwd=raiz,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def esta_ignorado(ruta: str, raiz: Path) -> bool:
    """Comprueba si una ruta está protegida por .gitignore."""
    resultado = ejecutar_git(
        ["check-ignore", "--quiet", "--no-index", ruta],
        raiz,
    )
    return resultado.returncode == 0


def es_archivo_sensible(ruta: str) -> bool:
    """Identifica posibles credenciales registradas accidentalmente."""
    ruta_normalizada = Path(ruta).as_posix().lower()
    nombre = Path(ruta_normalizada).name

    if ruta_normalizada == ".env":
        return True

    if nombre.startswith(".env.") and nombre != ".env.example":
        return True

    if ruta_normalizada.startswith("secrets/"):
        return True

    if "client_secret" in nombre:
        return True

    if nombre.endswith(".json") and (
        "token" in nombre or "credential" in nombre
    ):
        return True

    return nombre.endswith((".pem", ".key"))


def ejecutar_revision_seguridad() -> bool:
    """Revisa la protección de claves y credenciales."""
    settings = load_settings()
    raiz = settings.project_root

    rutas_protegidas = [
        ".env",
        "config/client_secret.json",
        "config/token.json",
        "config/credentials.json",
        "config/youtube/client_secret.json",
        "config/youtube/token.json",
        "config/youtube/analytics_token.json",
        "config/youtube/channels/nexon_ia/token.json",
        "config/youtube/channels/nexon_ia/channel.json",
        "config/youtube/channels/nexon_ia/analytics_token.json",
        "config/youtube/channels/cogniviva/token.json",
        "config/youtube/channels/cogniviva/channel.json",
        "config/youtube/channels/cogniviva/analytics_token.json",
        "secrets/example.txt",
        "private.pem",
        "private.key",
    ]

    print("\nREVISIÓN DE SEGURIDAD DE AUTOTUBE AI")
    print("=" * 70)

    todo_correcto = True

    for ruta in rutas_protegidas:
        protegido = esta_ignorado(ruta, raiz)
        estado = "PROTEGIDO" if protegido else "RIESGO"

        print(f"[{estado:<9}] {ruta}")

        if not protegido:
            todo_correcto = False

    archivos_registrados = ejecutar_git(
        ["ls-files"],
        raiz,
    ).stdout.splitlines()

    archivos_sensibles = [
        ruta
        for ruta in archivos_registrados
        if es_archivo_sensible(ruta)
    ]

    print("=" * 70)

    if archivos_sensibles:
        todo_correcto = False
        print("Se encontraron archivos sensibles registrados en Git:")

        for ruta in archivos_sensibles:
            print(f"  - {ruta}")
    else:
        print("No existen credenciales privadas registradas en Git.")

    print("=" * 70)

    if todo_correcto:
        print("La protección de credenciales está funcionando.")
    else:
        print("Hay riesgos de seguridad que deben corregirse.")

    return todo_correcto
