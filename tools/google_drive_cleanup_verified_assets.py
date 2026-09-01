from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = ROOT / "output" / "assets"
MANIFEST_ROOT = (
    ROOT
    / "output"
    / "google_drive"
    / "archive_assets"
)
COLLECTION_PATTERN = re.compile(
    r"^coleccion_\d{8}_\d{6}$"
)


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def format_size(total: int) -> str:
    value = float(total)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(
        path.read_text(encoding="utf-8-sig")
    )
    if not isinstance(data, dict):
        raise RuntimeError(
            "El manifiesto no contiene un objeto JSON valido."
        )
    return data


def resolve_manifest(argument: Path) -> Path:
    candidate = argument.expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    manifest_root = MANIFEST_ROOT.resolve()

    try:
        candidate.relative_to(manifest_root)
    except ValueError as error:
        raise RuntimeError(
            "Bloqueo de seguridad: el manifiesto debe estar dentro de "
            f"{manifest_root}"
        ) from error

    if (
        not candidate.is_file()
        or not candidate.name.startswith("archive_assets_")
        or candidate.suffix.lower() != ".json"
    ):
        raise FileNotFoundError(
            f"No existe un manifiesto valido: {candidate}"
        )

    return candidate


def validate_collection_path(name: str) -> Path:
    if not COLLECTION_PATTERN.fullmatch(name):
        raise RuntimeError(
            "Nombre de coleccion no valido en el manifiesto: "
            f"{name}"
        )

    assets_root = ASSETS_ROOT.resolve()
    collection = (ASSETS_ROOT / name).resolve()
    if collection.parent != assets_root:
        raise RuntimeError(
            "Bloqueo de seguridad: coleccion fuera de output/assets."
        )
    return collection


def safe_relative_path(raw: str) -> Path:
    relative = Path(raw)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise RuntimeError(
            f"Ruta relativa no valida en el manifiesto: {raw}"
        )
    return relative


def local_files(collection: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in collection.rglob("*"):
        is_junction = bool(
            getattr(path, "is_junction", lambda: False)()
        )
        if path.is_symlink() or is_junction:
            raise RuntimeError(
                "Bloqueo de seguridad: enlace detectado dentro de "
                f"{collection.name}: {path}"
            )
        if not path.is_file():
            continue
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(collection)
        except ValueError as error:
            raise RuntimeError(
                f"Archivo fuera de la coleccion: {path}"
            ) from error
        files[relative.as_posix()] = resolved
    return files


def validate_manifest_header(
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    if data.get("tipo") != "archivo_recursos_antiguos":
        raise RuntimeError(
            "El archivo no es un manifiesto de recursos antiguos."
        )
    if data.get("estado") != "completado":
        raise RuntimeError(
            "El manifiesto no tiene estado completado."
        )

    collections = data.get("colecciones")
    if not isinstance(collections, list) or not collections:
        raise RuntimeError(
            "El manifiesto no contiene colecciones verificadas."
        )
    if len(collections) != int(
        data.get("cantidad_colecciones", -1)
    ):
        raise RuntimeError(
            "La cantidad de colecciones no coincide con el manifiesto."
        )
    return [
        item for item in collections if isinstance(item, dict)
    ]


def validate_collection(
    item: dict[str, Any],
    preserved: set[str],
) -> tuple[Path, int, int]:
    name = str(item.get("nombre", "")).strip()
    collection = validate_collection_path(name)

    if name in preserved:
        raise RuntimeError(
            "Bloqueo de seguridad: el manifiesto intenta eliminar una "
            f"coleccion protegida: {name}"
        )
    if not item.get("verificado"):
        raise RuntimeError(
            f"La coleccion no esta verificada en Drive: {name}"
        )
    if not collection.is_dir():
        raise FileNotFoundError(
            f"No existe la copia local esperada: {collection}"
        )

    manifest_files = item.get("archivos")
    if not isinstance(manifest_files, list):
        raise RuntimeError(
            f"Lista de archivos invalida: {name}"
        )
    if len(manifest_files) != int(
        item.get("cantidad_archivos", -1)
    ):
        raise RuntimeError(
            f"Cantidad de archivos inconsistente: {name}"
        )

    actual = local_files(collection)
    expected_names: set[str] = set()
    total_bytes = 0

    for file_item in manifest_files:
        if not isinstance(file_item, dict):
            raise RuntimeError(
                f"Registro de archivo invalido: {name}"
            )
        relative = safe_relative_path(
            str(file_item.get("ruta_relativa", ""))
        )
        relative_name = relative.as_posix()
        if relative_name in expected_names:
            raise RuntimeError(
                f"Archivo duplicado en el manifiesto: {relative_name}"
            )
        expected_names.add(relative_name)

        local_path = actual.get(relative_name)
        if local_path is None:
            raise FileNotFoundError(
                f"Falta el archivo local: {collection / relative}"
            )

        expected_size = int(file_item.get("tamano_bytes", -1))
        if local_path.stat().st_size != expected_size:
            raise RuntimeError(
                f"El tamano cambio: {local_path}"
            )

        local_md5 = str(file_item.get("md5_local", "")).lower()
        drive_md5 = str(file_item.get("md5_drive", "")).lower()
        if (
            not file_item.get("verificado")
            or not local_md5
            or local_md5 != drive_md5
        ):
            raise RuntimeError(
                f"La verificacion de Drive no es valida: {local_path}"
            )
        if md5_file(local_path) != local_md5:
            raise RuntimeError(
                f"El contenido local cambio: {local_path}"
            )
        total_bytes += expected_size

    if set(actual) != expected_names:
        extras = sorted(set(actual) - expected_names)
        missing = sorted(expected_names - set(actual))
        raise RuntimeError(
            f"La coleccion cambio desde el respaldo: {name}. "
            f"Extras: {extras[:3]}; faltantes: {missing[:3]}"
        )
    if total_bytes != int(item.get("tamano_bytes", -1)):
        raise RuntimeError(
            f"El tamano total no coincide: {name}"
        )
    return collection, len(manifest_files), total_bytes


def report_path() -> Path:
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    return MANIFEST_ROOT / (
        "cleanup_assets_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".json"
    )


def write_report(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Elimina recursos locales usando un manifiesto de Drive "
            "previamente completado y verificado."
        )
    )
    parser.add_argument(
        "--manifiesto",
        required=True,
        type=Path,
        help="Manifiesto archive_assets completado.",
    )
    parser.add_argument(
        "--conservar",
        action="append",
        default=[],
        metavar="COLECCION",
        help="Coleccion que no debe eliminarse.",
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Confirma la eliminacion local permanente.",
    )
    args = parser.parse_args()

    if not args.conservar:
        parser.error(
            "Debes indicar al menos una coleccion con --conservar."
        )

    manifest_path = resolve_manifest(args.manifiesto)
    manifest = read_json(manifest_path)
    manifest_sha256 = sha256_file(manifest_path)
    preserved = {Path(name).name for name in args.conservar}

    newest = max(
        (
            path.name
            for path in ASSETS_ROOT.iterdir()
            if (
                path.is_dir()
                and COLLECTION_PATTERN.fullmatch(path.name)
            )
        ),
        default="",
    )
    if newest:
        preserved.add(newest)

    manifest_collections = validate_manifest_header(manifest)
    verified: list[tuple[Path, int, int]] = []

    print()
    print("VERIFICACION LOCAL DESDE MANIFIESTO DE DRIVE")
    print("=" * 72)
    print(f"Manifiesto: {manifest_path}")
    print("Internet requerido: NO")
    print(
        "Colecciones protegidas: "
        + ", ".join(sorted(preserved))
    )
    print("Verificando archivos y MD5 locales...")

    for position, item in enumerate(
        manifest_collections,
        start=1,
    ):
        name = str(item.get("nombre", ""))
        print(
            f"{position}/{len(manifest_collections)} {name}"
        )
        verified.append(
            validate_collection(item, preserved)
        )

    files_count = sum(item[1] for item in verified)
    total_bytes = sum(item[2] for item in verified)
    expected_files = int(
        manifest.get("cantidad_archivos", -1)
    )
    expected_bytes = int(
        manifest.get("tamano_total_bytes", -1)
    )
    if files_count != expected_files or total_bytes != expected_bytes:
        raise RuntimeError(
            "Los totales locales no coinciden con el manifiesto."
        )

    print("=" * 72)
    print("VERIFICACION LOCAL APROBADA")
    print(f"Colecciones: {len(verified)}")
    print(f"Archivos: {files_count}")
    print(f"Espacio recuperable: {format_size(total_bytes)}")

    if not args.confirmar:
        print()
        print("SIMULACION: no se elimino ninguna carpeta.")
        print("Agrega --confirmar solo despues de revisar este resultado.")
        return 0

    report = {
        "iniciado_en": (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        ),
        "estado": "en_progreso",
        "manifiesto_origen": str(manifest_path),
        "manifiesto_sha256": manifest_sha256,
        "colecciones_protegidas": sorted(preserved),
        "colecciones_eliminadas": [],
        "archivos_eliminados": 0,
        "bytes_recuperados": 0,
    }
    output_report = report_path()
    write_report(output_report, report)

    for position, (collection, count, size) in enumerate(
        verified,
        start=1,
    ):
        print(
            f"ELIMINANDO {position}/{len(verified)}: "
            f"{collection.name}"
        )
        shutil.rmtree(collection)
        if collection.exists():
            raise RuntimeError(
                f"No se pudo eliminar: {collection}"
            )
        report["colecciones_eliminadas"].append(
            collection.name
        )
        report["archivos_eliminados"] += count
        report["bytes_recuperados"] += size
        write_report(output_report, report)

    report["estado"] = "completado"
    report["completado_en"] = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )
    write_report(output_report, report)

    print()
    print("=" * 72)
    print("LIMPIEZA DE RECURSOS COMPLETADA")
    print(f"Colecciones eliminadas: {len(verified)}")
    print(f"Archivos eliminados: {files_count}")
    print(f"Espacio recuperado: {format_size(total_bytes)}")
    print(f"Colecciones protegidas: {', '.join(sorted(preserved))}")
    print(f"Informe: {output_report}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
