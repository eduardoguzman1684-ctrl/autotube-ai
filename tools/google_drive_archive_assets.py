from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import ssl
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import google_drive_backup as drive_backup


ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = ROOT / "output" / "assets"
OUTPUT_ROOT = (
    ROOT
    / "output"
    / "google_drive"
    / "archive_assets"
)

DEFAULT_DRIVE_ROOT = (
    "AUTOTUBE AI - ARCHIVO DE RECURSOS"
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


def validate_collection_path(path: Path) -> Path:
    assets_root = ASSETS_ROOT.resolve()
    resolved = path.resolve()

    if resolved.parent != assets_root:
        raise RuntimeError(
            "Bloqueo de seguridad: la coleccion no es hija "
            "directa de output/assets."
        )

    if not COLLECTION_PATTERN.fullmatch(resolved.name):
        raise RuntimeError(
            "Bloqueo de seguridad: nombre de coleccion no valido: "
            f"{resolved.name}"
        )

    if not resolved.is_dir():
        raise FileNotFoundError(
            f"No existe la coleccion: {resolved}"
        )

    return resolved


def resolve_preserved(names: list[str]) -> set[str]:
    if not names:
        raise RuntimeError(
            "Debes indicar al menos una coleccion con --conservar. "
            "Esto evita archivar por accidente la produccion actual."
        )

    preserved: set[str] = set()

    for raw_name in names:
        name = Path(raw_name).name
        path = validate_collection_path(
            ASSETS_ROOT / name
        )
        preserved.add(path.name)

    return preserved


def select_collections(
    preserved: set[str],
) -> list[Path]:
    if not ASSETS_ROOT.is_dir():
        raise FileNotFoundError(
            f"No existe la carpeta de recursos: {ASSETS_ROOT}"
        )

    collections = [
        validate_collection_path(path)
        for path in ASSETS_ROOT.iterdir()
        if (
            path.is_dir()
            and COLLECTION_PATTERN.fullmatch(path.name)
            and path.name not in preserved
        )
    ]

    return sorted(
        collections,
        key=lambda item: item.name,
    )


def newest_collection_name() -> str:
    collections = sorted(
        path.name
        for path in ASSETS_ROOT.iterdir()
        if (
            path.is_dir()
            and COLLECTION_PATTERN.fullmatch(path.name)
        )
    )

    if not collections:
        raise RuntimeError(
            "No existen colecciones de recursos en output/assets."
        )

    return collections[-1]


def files_in(collection: Path) -> list[Path]:
    collection = validate_collection_path(collection)
    files: list[Path] = []

    for path in collection.rglob("*"):
        is_junction = bool(
            getattr(path, "is_junction", lambda: False)()
        )

        if path.is_symlink() or is_junction:
            raise RuntimeError(
                "Bloqueo de seguridad: no se permiten enlaces "
                f"dentro de una coleccion: {path}"
            )

        if not path.is_file():
            continue

        resolved = path.resolve()
        try:
            resolved.relative_to(collection)
        except ValueError as error:
            raise RuntimeError(
                "Bloqueo de seguridad: archivo fuera de la coleccion: "
                f"{path}"
            ) from error

        files.append(resolved)

    return sorted(
        files,
        key=lambda item: item.relative_to(
            collection
        ).as_posix(),
    )


def snapshot(collection: Path) -> list[tuple[str, int, int]]:
    return [
        (
            path.relative_to(collection).as_posix(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in files_in(collection)
    ]


def folder_for_relative_path(
    drive,
    collection_folder_id: str,
    relative_parent: Path,
    cache: dict[str, str],
) -> str:
    if relative_parent == Path("."):
        return collection_folder_id

    parent_id = collection_folder_id
    accumulated = Path()

    for part in relative_parent.parts:
        accumulated /= part
        key = accumulated.as_posix()
        cached = cache.get(key)

        if cached:
            parent_id = cached
            continue

        folder = drive_backup.obtener_o_crear_carpeta(
            drive,
            part,
            parent_id,
        )
        parent_id = str(folder["id"])
        cache[key] = parent_id

    return parent_id


def is_temporary_upload_error(error: Exception) -> bool:
    status = getattr(
        getattr(error, "resp", None),
        "status",
        None,
    )
    if status in {408, 429, 500, 502, 503, 504}:
        return True

    messages: list[str] = []
    current: BaseException | None = error
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        messages.append(str(current))
        current = current.__cause__ or current.__context__

    message = " ".join(messages).lower()
    indicators = (
        "eof occurred in violation of protocol",
        "ssl",
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "remote disconnected",
        "server disconnected",
        "temporary failure in name resolution",
        "name resolution",
        "failed to resolve",
        "getaddrinfo failed",
        "max retries exceeded",
        "transporterror",
        "connectionerror",
        "service unavailable",
        "backend error",
        "rate limit",
    )
    return isinstance(
        error,
        (
            ssl.SSLError,
            ConnectionError,
            TimeoutError,
            OSError,
        ),
    ) or any(
        indicator in message
        for indicator in indicators
    )


def upload_file_with_retries(
    drive,
    path: Path,
    parent_id: str,
    max_retries: int = 8,
) -> dict[str, Any]:
    retry = 0

    while True:
        try:
            return drive_backup.subir_archivo(
                drive,
                path,
                parent_id,
            )
        except Exception as error:
            if (
                not is_temporary_upload_error(error)
                or retry >= max_retries
            ):
                raise

            retry += 1
            delay = min(60, 2 ** retry)
            print(
                "  Conexion interrumpida. "
                f"Reintento {retry}/{max_retries} "
                f"en {delay} segundos..."
            )
            time.sleep(delay)


def upload_collection(
    drive,
    collection: Path,
    archive_root_id: str,
) -> dict[str, Any]:
    collection_folder = (
        drive_backup.obtener_o_crear_carpeta(
            drive,
            collection.name,
            archive_root_id,
        )
    )
    collection_folder_id = str(
        collection_folder["id"]
    )
    folders: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    collection_files = files_in(collection)

    for position, path in enumerate(
        collection_files,
        start=1,
    ):
        relative = path.relative_to(collection)
        print()
        print(
            f"  {position}/{len(collection_files)} "
            f"{relative.as_posix()}"
        )

        parent_id = folder_for_relative_path(
            drive,
            collection_folder_id,
            relative.parent,
            folders,
        )
        local_md5 = md5_file(path)
        uploaded = upload_file_with_retries(
            drive,
            path,
            parent_id,
        )
        remote_md5 = str(
            uploaded.get("md5Checksum", "")
        ).lower()

        if not remote_md5 or remote_md5 != local_md5:
            raise RuntimeError(
                "Verificacion MD5 fallida para: "
                f"{path}"
            )

        results.append(
            {
                "ruta_relativa": relative.as_posix(),
                "tamano_bytes": path.stat().st_size,
                "md5_local": local_md5,
                "md5_drive": remote_md5,
                "drive_file_id": uploaded.get("id", ""),
                "estado": uploaded.get("estado", "verificado"),
                "verificado": True,
            }
        )

    return {
        "nombre": collection.name,
        "ruta_local": str(collection),
        "drive_folder_id": collection_folder_id,
        "drive_url": (
            "https://drive.google.com/drive/folders/"
            f"{collection_folder_id}"
        ),
        "cantidad_archivos": len(results),
        "tamano_bytes": sum(
            item["tamano_bytes"] for item in results
        ),
        "archivos": results,
        "verificado": True,
        "eliminado_localmente": False,
    }


def delete_verified_collection(
    collection: Path,
    original_snapshot: list[tuple[str, int, int]],
) -> None:
    collection = validate_collection_path(collection)

    if snapshot(collection) != original_snapshot:
        raise RuntimeError(
            "Bloqueo de seguridad: la coleccion cambio durante "
            f"la subida y no se eliminara: {collection.name}"
        )

    shutil.rmtree(collection)

    if collection.exists():
        raise RuntimeError(
            "No se pudo confirmar la eliminacion local de: "
            f"{collection}"
        )


def new_manifest_path() -> Path:
    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )
    return OUTPUT_ROOT / (
        "archive_assets_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".json"
    )


def write_manifest(
    path: Path,
    data: dict[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Archiva colecciones antiguas de recursos de "
            "AutoTube AI en Google Drive."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el plan sin conectarse a Google Drive.",
    )
    parser.add_argument(
        "--conservar",
        action="append",
        default=[],
        metavar="COLECCION",
        help=(
            "Coleccion que permanecera local. Puede repetirse."
        ),
    )
    parser.add_argument(
        "--carpeta-raiz",
        default=DEFAULT_DRIVE_ROOT,
        help="Carpeta raiz utilizada en Google Drive.",
    )
    parser.add_argument(
        "--eliminar-locales",
        action="store_true",
        help=(
            "Elimina cada coleccion local solo despues de "
            "verificar todos sus archivos en Drive."
        ),
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Confirma la eliminacion local solicitada.",
    )
    args = parser.parse_args()

    if args.confirmar and not args.eliminar_locales:
        parser.error(
            "--confirmar solo se usa con --eliminar-locales."
        )

    if args.eliminar_locales and not args.confirmar:
        parser.error(
            "Para eliminar copias locales agrega --confirmar."
        )

    preserved = resolve_preserved(args.conservar)
    preserved.add(newest_collection_name())
    collections = select_collections(preserved)

    if not collections:
        print(
            "No hay colecciones antiguas para archivar."
        )
        return 0

    snapshots = {
        path.name: snapshot(path)
        for path in collections
    }
    files_count = sum(
        len(value) for value in snapshots.values()
    )
    total_bytes = sum(
        size
        for value in snapshots.values()
        for _, size, _ in value
    )

    print()
    print("AUTOTUBE AI - ARCHIVO DE RECURSOS EN DRIVE")
    print("=" * 72)
    print(f"Carpeta local: {ASSETS_ROOT}")
    print(f"Carpeta Drive: {args.carpeta_raiz}")
    print(
        "Colecciones conservadas: "
        + ", ".join(sorted(preserved))
    )
    print(f"Colecciones para archivar: {len(collections)}")
    print(f"Archivos: {files_count}")
    print(
        "Tamano total: "
        f"{drive_backup.formato_tamano(total_bytes)}"
    )
    print("=" * 72)

    for position, collection in enumerate(
        collections,
        start=1,
    ):
        collection_bytes = sum(
            size
            for _, size, _ in snapshots[collection.name]
        )
        print(
            f"{position}. {collection.name} | "
            f"{len(snapshots[collection.name])} archivos | "
            f"{drive_backup.formato_tamano(collection_bytes)}"
        )

    if args.dry_run:
        print()
        print("SIMULACION CORRECTA")
        print("No se subio ni elimino ningun archivo.")
        return 0

    drive = drive_backup.cliente_drive()
    archive_root = drive_backup.obtener_o_crear_carpeta(
        drive,
        drive_backup.limpiar_nombre(args.carpeta_raiz),
        "root",
    )
    results: list[dict[str, Any]] = []
    manifest_path = new_manifest_path()
    manifest = {
        "generado_en": (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        ),
        "tipo": "archivo_recursos_antiguos",
        "estado": "en_progreso",
        "carpeta_local": str(ASSETS_ROOT),
        "carpeta_drive": {
            "id": archive_root["id"],
            "nombre": archive_root["name"],
            "url": (
                "https://drive.google.com/drive/folders/"
                f"{archive_root['id']}"
            ),
        },
        "colecciones_conservadas": sorted(preserved),
        "eliminacion_local_solicitada": bool(
            args.eliminar_locales
        ),
        "cantidad_colecciones_objetivo": len(collections),
        "cantidad_archivos_objetivo": files_count,
        "tamano_total_bytes": total_bytes,
        "colecciones": results,
    }
    write_manifest(manifest_path, manifest)

    for position, collection in enumerate(
        collections,
        start=1,
    ):
        print()
        print("=" * 72)
        print(
            f"COLECCION {position}/{len(collections)}: "
            f"{collection.name}"
        )
        result = upload_collection(
            drive,
            collection,
            str(archive_root["id"]),
        )
        results.append(result)
        write_manifest(manifest_path, manifest)

        if args.eliminar_locales:
            delete_verified_collection(
                collection,
                snapshots[collection.name],
            )
            result["eliminado_localmente"] = True
            print(
                "COPIA LOCAL ELIMINADA DESPUES DE "
                f"VERIFICAR DRIVE: {collection.name}"
            )
            write_manifest(manifest_path, manifest)

    manifest["estado"] = "completado"
    manifest["cantidad_colecciones"] = len(results)
    manifest["cantidad_archivos"] = files_count
    manifest["completado_en"] = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )
    write_manifest(manifest_path, manifest)

    print()
    print("=" * 72)
    print("ARCHIVO DE RECURSOS COMPLETADO")
    print(f"Colecciones verificadas: {len(results)}")
    print(f"Archivos verificados: {files_count}")
    print(
        "Copias locales eliminadas: "
        + ("SI" if args.eliminar_locales else "NO")
    )
    print(
        "Drive: "
        f"{manifest['carpeta_drive']['url']}"
    )
    print(f"Manifiesto: {manifest_path}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
