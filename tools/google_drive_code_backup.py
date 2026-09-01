from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.operations.code_backup import (
    CodeBackupError,
    create_code_backup,
    inspect_repository,
)
from google_drive_backup import (
    cliente_drive,
    formato_tamano,
    limpiar_nombre,
    obtener_o_crear_carpeta,
    subir_archivo,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT_FOLDER = "NEXON IA - AutoTube AI"
DEFAULT_CODE_FOLDER = "Actualizaciones del sistema"


def _folder_url(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _print_plan(plan: dict[str, Any], dry_run: bool) -> None:
    print()
    print("AUTOTUBE AI - RESPALDO VERSIONADO DEL CODIGO")
    print("=" * 68)
    print(f"Version: {plan['version']}")
    print(f"Commit: {plan['commit']}")
    print(f"Rama local: {plan['branch']}")
    print(f"Rama remota: {plan['upstream'] or 'sin configurar'}")
    print(f"Archivos controlados: {plan['tracked_file_count']}")
    print("Origen: commit exacto de Git")
    print("Archivos no controlados: EXCLUIDOS")
    print("Credenciales detectadas: NINGUNA")
    print(f"Modo: {'SIMULACION' if dry_run else 'RESPALDO REAL'}")
    print("=" * 68)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Crea un ZIP del commit actual y lo respalda de forma "
            "versionada en Google Drive."
        )
    )
    parser.add_argument(
        "--version",
        default=None,
        help=(
            "Nombre de la version. Si se omite, usa la etiqueta Git "
            "del commit o commit-<sha>."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida el respaldo sin crear archivos ni usar Google Drive.",
    )
    parser.add_argument(
        "--carpeta-raiz",
        default=DEFAULT_ROOT_FOLDER,
        help="Carpeta raiz existente o nueva en Google Drive.",
    )
    parser.add_argument(
        "--carpeta-codigo",
        default=DEFAULT_CODE_FOLDER,
        help="Subcarpeta para las actualizaciones del sistema.",
    )
    args = parser.parse_args()

    try:
        plan = inspect_repository(ROOT, version=args.version)
    except CodeBackupError as error:
        print()
        print(str(error))
        return 2

    _print_plan(plan, args.dry_run)
    if args.dry_run:
        print("SIMULACION CORRECTA: no se creo ni subio ningun archivo.")
        return 0

    result = create_code_backup(plan)
    print()
    print(f"ZIP: {result['archive_path']}")
    print(f"Tamano: {formato_tamano(result['archive_size_bytes'])}")
    print(f"SHA-256: {result['archive_sha256']}")
    print(f"Manifiesto: {result['manifest_path']}")

    drive = cliente_drive()
    root_folder = obtener_o_crear_carpeta(
        drive,
        limpiar_nombre(args.carpeta_raiz),
        "root",
    )
    code_folder = obtener_o_crear_carpeta(
        drive,
        limpiar_nombre(args.carpeta_codigo),
        str(root_folder["id"]),
    )
    version_folder = obtener_o_crear_carpeta(
        drive,
        limpiar_nombre(f"{plan['version']} - {plan['short_commit']}"),
        str(code_folder["id"]),
    )

    uploaded = [
        subir_archivo(
            drive,
            Path(result["archive_path"]),
            str(version_folder["id"]),
        ),
        subir_archivo(
            drive,
            Path(result["manifest_path"]),
            str(version_folder["id"]),
        ),
    ]

    report_dir = ROOT / "output" / "google_drive" / "code_backups"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / (
        "code_backup_upload_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    )
    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "version": plan["version"],
        "commit": plan["commit"],
        "archive_sha256": result["archive_sha256"],
        "drive_folder": {
            "id": version_folder["id"],
            "name": version_folder["name"],
            "url": _folder_url(str(version_folder["id"])),
        },
        "files": uploaded,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=" * 68)
    print("RESPALDO DEL CODIGO COMPLETADO")
    print(f"Version: {plan['version']}")
    print(f"Commit: {plan['short_commit']}")
    print(f"Carpeta: {_folder_url(str(version_folder['id']))}")
    print(f"Informe local: {report_path}")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
