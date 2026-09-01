from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from googleapiclient.http import MediaIoBaseDownload

import google_drive_backup as drive_backup
from autotube.content.channel_profiles import (
    CHANNEL_CHOICES,
    DEFAULT_CHANNEL,
    channel_profile,
    normalize_channel_slug,
)


ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = ROOT / "output" / "assets"
INDEX_ROOT = ROOT / "data" / "visual_cache"
REPORT_ROOT = ROOT / "output" / "google_drive" / "visual_cache"
COLLECTION_PATTERN = re.compile(r"^coleccion_\d{8}_\d{6}$")
LOCAL_STATES = {"descargado", "generado_local"}
ARCHIVED_STATE = "archivado_drive"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No se pudo leer el manifiesto: {path}") from error

    if not isinstance(data, dict):
        raise RuntimeError(f"El manifiesto no contiene un objeto JSON: {path}")

    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        while True:
            block = source.read(4 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            block = source.read(4 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def visual_fingerprint(channel_slug: str, item: dict[str, Any]) -> str:
    payload = {
        "channel_slug": channel_slug,
        "segmento": item.get("segmento_numero"),
        "clip": item.get("clip_orden"),
        "tipo": item.get("tipo_recurso"),
        "narracion": " ".join(str(item.get("texto_narrado", "")).split()),
        "descripcion": " ".join(str(item.get("descripcion", "")).split()),
        "consulta": " ".join(str(item.get("consulta", "")).split()),
        "fuente": item.get("fuente", "local"),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_collection(path: Path, require_exists: bool = True) -> Path:
    assets_root = ASSETS_ROOT.resolve()
    resolved = path.expanduser().resolve()

    if resolved.parent != assets_root:
        raise RuntimeError(
            "BLOQUEO DE SEGURIDAD: la coleccion visual debe ser hija "
            "directa de output/assets."
        )

    if not COLLECTION_PATTERN.fullmatch(resolved.name):
        raise RuntimeError(
            "BLOQUEO DE SEGURIDAD: nombre de coleccion no valido: "
            f"{resolved.name}"
        )

    if require_exists and not resolved.is_dir():
        raise FileNotFoundError(f"No existe la coleccion visual: {resolved}")

    return resolved


def manifest_candidates() -> list[Path]:
    return sorted(
        ASSETS_ROOT.glob("coleccion_*/assets_manifest.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def index_candidates(channel_slug: str) -> list[Path]:
    directory = INDEX_ROOT / channel_slug
    if not directory.is_dir():
        return []
    return sorted(
        directory.glob("coleccion_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def manifest_channel(data: dict[str, Any]) -> str:
    raw = data.get("channel_slug")
    cache = data.get("visual_cache")
    if not raw and isinstance(cache, dict):
        raw = cache.get("channel_slug")
    return normalize_channel_slug(str(raw or DEFAULT_CHANNEL))


def resolve_manifest(
    channel_slug: str,
    manifest_path: Path | None,
    allow_index: bool,
) -> tuple[dict[str, Any], Path, Path, bool]:
    candidates: list[Path]
    from_index = False

    if manifest_path is not None:
        candidate = manifest_path.expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        candidates = [candidate.resolve()]
    else:
        candidates = manifest_candidates()

    for candidate in candidates:
        if not candidate.is_file():
            continue
        data = load_json(candidate)
        raw_channel = data.get("channel_slug")
        if raw_channel and manifest_channel(data) != channel_slug:
            if manifest_path is not None:
                raise RuntimeError(
                    "BLOQUEO MULTICANAL: el manifiesto visual pertenece a "
                    f"{manifest_channel(data)}, no a {channel_slug}."
                )
            continue
        collection = validate_collection(candidate.parent)
        return data, candidate, collection, from_index

    if allow_index:
        for candidate in index_candidates(channel_slug):
            data = load_json(candidate)
            if manifest_channel(data) != channel_slug:
                continue
            collection_name = str(
                data.get("visual_cache", {}).get("collection", candidate.stem)
            )
            collection = validate_collection(
                ASSETS_ROOT / collection_name,
                require_exists=False,
            )
            local_manifest = collection / "assets_manifest.json"
            from_index = True
            return data, local_manifest, collection, from_index

    raise FileNotFoundError(
        "No se encontro un manifiesto visual del canal "
        f"{channel_slug}."
    )


def assert_channel(data: dict[str, Any], channel_slug: str) -> None:
    raw = data.get("channel_slug")
    if raw and manifest_channel(data) != channel_slug:
        raise RuntimeError(
            "BLOQUEO MULTICANAL: el manifiesto visual pertenece a "
            f"{manifest_channel(data)}, no a {channel_slug}."
        )
    data["channel_slug"] = channel_slug


def safe_relative_path(collection: Path, raw_path: str) -> tuple[Path, str]:
    candidate = Path(str(raw_path)).expanduser()
    if not candidate.is_absolute():
        candidate = collection / candidate
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(collection.resolve())
    except ValueError as error:
        raise RuntimeError(
            "BLOQUEO DE SEGURIDAD: recurso visual fuera de su coleccion: "
            f"{resolved}"
        ) from error

    if relative.name == "assets_manifest.json":
        raise RuntimeError(
            "BLOQUEO DE SEGURIDAD: el manifiesto no puede ser un recurso."
        )

    return resolved, relative.as_posix()


def visual_items(
    data: dict[str, Any],
    collection: Path,
    require_local: bool,
) -> list[tuple[dict[str, Any], Path, str]]:
    elements = data.get("elementos")
    if not isinstance(elements, list) or not elements:
        raise RuntimeError("El manifiesto no contiene recursos visuales.")

    result: list[tuple[dict[str, Any], Path, str]] = []
    seen: set[str] = set()

    for item in elements:
        if not isinstance(item, dict):
            raise RuntimeError("El manifiesto contiene un recurso no valido.")

        state = str(item.get("estado", ""))
        remote = item.get("drive_cache")
        raw_path = str(item.get("archivo", ""))

        if not raw_path and isinstance(remote, dict):
            raw_path = str(remote.get("relative_path", ""))

        if not raw_path:
            raise RuntimeError(
                "El recurso no contiene una ruta local ni una ruta remota."
            )

        local_path, relative = safe_relative_path(collection, raw_path)

        if relative in seen:
            raise RuntimeError(f"Ruta visual duplicada: {relative}")
        seen.add(relative)

        if require_local:
            if state not in LOCAL_STATES:
                raise RuntimeError(
                    "No se archivara una coleccion incompleta. Estado: "
                    f"{state or 'vacio'} | {relative}"
                )
            if not local_path.is_file() or local_path.stat().st_size <= 0:
                raise FileNotFoundError(f"Falta el recurso visual: {local_path}")

        item["archivo"] = str(local_path)
        result.append((item, local_path, relative))

    return result


def folder_for_relative_path(
    drive: Any,
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
        if key in cache:
            parent_id = cache[key]
            continue
        folder = drive_backup.obtener_o_crear_carpeta(
            drive,
            drive_backup.limpiar_nombre(part),
            parent_id,
        )
        parent_id = str(folder["id"])
        cache[key] = parent_id
    return parent_id


def temporary_error(error: Exception) -> bool:
    status = getattr(getattr(error, "resp", None), "status", None)
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
        "ssl",
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "remote disconnected",
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
        (ssl.SSLError, ConnectionError, TimeoutError, OSError),
    ) or any(indicator in message for indicator in indicators)


def with_retries(operation, label: str, maximum: int = 8):
    retry = 0
    while True:
        try:
            return operation()
        except Exception as error:
            if not temporary_error(error) or retry >= maximum:
                raise
            retry += 1
            delay = min(60, 2**retry)
            print(
                f"  Conexion interrumpida en {label}. "
                f"Reintento {retry}/{maximum} en {delay} segundos..."
            )
            time.sleep(delay)


def upload_verified(
    drive: Any,
    path: Path,
    parent_id: str,
    channel_slug: str,
    collection_name: str,
    fingerprint: str,
) -> dict[str, Any]:
    local_md5 = md5_file(path)
    uploaded = with_retries(
        lambda: drive_backup.subir_archivo(drive, path, parent_id),
        path.name,
    )
    remote_md5 = str(uploaded.get("md5Checksum", "")).lower()
    remote_size = int(uploaded.get("size", 0) or 0)

    if remote_md5 != local_md5 or remote_size != path.stat().st_size:
        raise RuntimeError(
            "Verificacion remota fallida para el recurso visual: "
            f"{path}"
        )

    properties = {
        "autotube": "1",
        "tipo": "cache_visual",
        "channel_slug": channel_slug,
        "collection": collection_name,
        "fingerprint": fingerprint,
    }
    with_retries(
        lambda: drive.files()
        .update(
            fileId=str(uploaded["id"]),
            body={"appProperties": properties},
            fields=(
                "id,name,md5Checksum,size,webViewLink,appProperties,trashed"
            ),
        )
        .execute(num_retries=5),
        f"metadatos de {path.name}",
    )

    return {
        "file_id": str(uploaded["id"]),
        "relative_path": "",
        "md5": local_md5,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "fingerprint": fingerprint,
        "channel_slug": channel_slug,
        "collection": collection_name,
        "verified": True,
        "verified_at": now(),
    }


def remote_metadata(drive: Any, remote: dict[str, Any]) -> dict[str, Any]:
    file_id = str(remote.get("file_id", ""))
    if not file_id:
        raise RuntimeError("El recurso no contiene drive_file_id.")
    return with_retries(
        lambda: drive.files()
        .get(
            fileId=file_id,
            fields="id,name,md5Checksum,size,appProperties,trashed",
        )
        .execute(num_retries=5),
        f"verificacion de {file_id}",
    )


def assert_remote(
    metadata: dict[str, Any],
    remote: dict[str, Any],
    channel_slug: str,
    collection_name: str,
) -> None:
    properties = metadata.get("appProperties", {})
    if metadata.get("trashed"):
        raise RuntimeError("El recurso visual remoto esta en la papelera.")
    if str(metadata.get("md5Checksum", "")).lower() != str(
        remote.get("md5", "")
    ).lower():
        raise RuntimeError("La huella MD5 remota no coincide.")
    if int(metadata.get("size", 0) or 0) != int(
        remote.get("size_bytes", 0) or 0
    ):
        raise RuntimeError("El tamano remoto no coincide.")
    if str(properties.get("channel_slug", "")) != channel_slug:
        raise RuntimeError(
            "BLOQUEO MULTICANAL: el recurso remoto pertenece a otro canal."
        )
    if str(properties.get("collection", "")) != collection_name:
        raise RuntimeError(
            "BLOQUEO DE COLECCION: el recurso remoto pertenece a otra produccion."
        )


def index_path(channel_slug: str, collection_name: str) -> Path:
    return INDEX_ROOT / channel_slug / f"{collection_name}.json"


def report_path(channel_slug: str, action: str) -> Path:
    directory = REPORT_ROOT / channel_slug
    directory.mkdir(parents=True, exist_ok=True)
    return directory / (
        f"visual_cache_{action}_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".json"
    )


def store(
    channel_slug: str,
    manifest_path: Path | None,
    dry_run: bool,
) -> int:
    data, local_manifest, collection, _ = resolve_manifest(
        channel_slug,
        manifest_path,
        allow_index=False,
    )
    assert_channel(data, channel_slug)
    items = visual_items(data, collection, require_local=True)
    total_bytes = sum(path.stat().st_size for _, path, _ in items)
    plan_path = Path(str(data.get("plan_visual_origen", ""))).expanduser()
    if not plan_path.is_absolute():
        plan_path = ROOT / plan_path
    plan_path = plan_path.resolve()
    if not plan_path.is_file():
        raise FileNotFoundError(f"No existe el plan visual: {plan_path}")

    profile = channel_profile(channel_slug)
    root_name = f"{profile['brand_label']} - BIBLIOTECA VISUAL"

    print()
    print("CACHE VISUAL AUTOMATICO EN GOOGLE DRIVE")
    print("=" * 72)
    print(f"Canal: {profile['display_name']} ({channel_slug})")
    print(f"Coleccion: {collection.name}")
    print(f"Plan visual: {plan_path.name}")
    print(f"Recursos: {len(items)}")
    print(f"Tamano: {drive_backup.formato_tamano(total_bytes)}")
    print(f"Carpeta Drive: {root_name}")
    print("=" * 72)

    if dry_run:
        print("SIMULACION CORRECTA: no se subio ningun archivo.")
        return 0

    drive = drive_backup.cliente_drive()
    root_folder = drive_backup.obtener_o_crear_carpeta(
        drive,
        drive_backup.limpiar_nombre(root_name),
        "root",
    )
    collection_folder = drive_backup.obtener_o_crear_carpeta(
        drive,
        collection.name,
        str(root_folder["id"]),
    )
    folder_cache: dict[str, str] = {}

    for position, (item, path, relative) in enumerate(items, start=1):
        print()
        print(f"{position}/{len(items)} {relative}")
        parent_id = folder_for_relative_path(
            drive,
            str(collection_folder["id"]),
            Path(relative).parent,
            folder_cache,
        )
        fingerprint = visual_fingerprint(channel_slug, item)
        remote = upload_verified(
            drive,
            path,
            parent_id,
            channel_slug,
            collection.name,
            fingerprint,
        )
        remote["relative_path"] = relative
        remote["local_state"] = str(item.get("estado", ""))
        item["drive_cache"] = remote

    plan_folder = drive_backup.obtener_o_crear_carpeta(
        drive,
        "plan_visual",
        str(collection_folder["id"]),
    )
    plan_remote = upload_verified(
        drive,
        plan_path,
        str(plan_folder["id"]),
        channel_slug,
        collection.name,
        sha256_file(plan_path),
    )
    plan_remote["relative_path"] = f"plan_visual/{plan_path.name}"
    plan_remote["local_path"] = str(plan_path)

    cache = {
        "version": 1,
        "state": "verified",
        "channel_slug": channel_slug,
        "collection": collection.name,
        "drive_root_id": str(root_folder["id"]),
        "drive_collection_id": str(collection_folder["id"]),
        "drive_url": (
            "https://drive.google.com/drive/folders/"
            f"{collection_folder['id']}"
        ),
        "verified_at": now(),
        "local_state": "materialized",
        "resource_count": len(items),
        "size_bytes": total_bytes,
        "plan": plan_remote,
    }
    data["visual_cache"] = cache
    data["channel_slug"] = channel_slug
    write_json(local_manifest, data)

    manifest_remote = upload_verified(
        drive,
        local_manifest,
        str(collection_folder["id"]),
        channel_slug,
        collection.name,
        sha256_file(local_manifest),
    )
    manifest_remote["relative_path"] = "assets_manifest.json"
    data["visual_cache"]["manifest"] = manifest_remote
    write_json(local_manifest, data)
    write_json(index_path(channel_slug, collection.name), data)

    report = {
        "action": "store",
        "state": "completed",
        "channel_slug": channel_slug,
        "collection": collection.name,
        "completed_at": now(),
        "resource_count": len(items),
        "size_bytes": total_bytes,
        "drive_url": cache["drive_url"],
        "manifest": str(local_manifest),
    }
    output = report_path(channel_slug, "store")
    write_json(output, report)

    print()
    print("=" * 72)
    print("CACHE VISUAL VERIFICADO EN GOOGLE DRIVE")
    print(f"Recursos verificados: {len(items)}")
    print(f"Drive: {cache['drive_url']}")
    print(f"Indice local: {index_path(channel_slug, collection.name)}")
    print(f"Informe: {output}")
    print("=" * 72)
    return 0


def download_verified(
    drive: Any,
    remote: dict[str, Any],
    target: Path,
    channel_slug: str,
    collection_name: str,
) -> None:
    metadata = remote_metadata(drive, remote)
    assert_remote(metadata, remote, channel_slug, collection_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".drive.tmp")
    temporary.unlink(missing_ok=True)

    def transfer() -> None:
        temporary.unlink(missing_ok=True)
        request = drive.files().get_media(fileId=str(remote["file_id"]))
        with temporary.open("wb") as destination:
            downloader = MediaIoBaseDownload(
                destination,
                request,
                chunksize=16 * 1024 * 1024,
            )
            done = False
            while not done:
                status, done = downloader.next_chunk(num_retries=5)
                if status:
                    print(f"  Progreso: {int(status.progress() * 100)}%")

    try:
        with_retries(transfer, target.name)
        if temporary.stat().st_size != int(remote["size_bytes"]):
            raise RuntimeError(f"Tamano restaurado incorrecto: {target}")
        if md5_file(temporary) != str(remote["md5"]).lower():
            raise RuntimeError(f"Huella restaurada incorrecta: {target}")
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def restore(
    channel_slug: str,
    manifest_path: Path | None,
    dry_run: bool,
) -> int:
    data, local_manifest, collection, from_index = resolve_manifest(
        channel_slug,
        manifest_path,
        allow_index=True,
    )
    assert_channel(data, channel_slug)
    cache = data.get("visual_cache")
    if not isinstance(cache, dict) or cache.get("state") != "verified":
        items = visual_items(data, collection, require_local=False)
        missing = [path for _, path, _ in items if not path.is_file()]
        if missing:
            raise RuntimeError(
                "Faltan recursos locales y el manifiesto no contiene "
                "un cache visual verificado en Drive."
            )
        print("Los recursos visuales ya estan disponibles localmente.")
        return 0

    if str(cache.get("channel_slug", "")) != channel_slug:
        raise RuntimeError("BLOQUEO MULTICANAL: cache visual de otro canal.")
    if str(cache.get("collection", "")) != collection.name:
        raise RuntimeError("BLOQUEO DE COLECCION: indice visual inconsistente.")

    collection.mkdir(parents=True, exist_ok=True)
    items = visual_items(data, collection, require_local=False)
    missing: list[tuple[dict[str, Any], Path, str]] = []
    reused = 0

    for item, path, relative in items:
        remote = item.get("drive_cache")
        if not isinstance(remote, dict) or not remote.get("verified"):
            raise RuntimeError(f"Recurso sin copia verificada en Drive: {relative}")
        if str(remote.get("channel_slug", "")) != channel_slug:
            raise RuntimeError(f"Recurso remoto de otro canal: {relative}")
        if str(remote.get("collection", "")) != collection.name:
            raise RuntimeError(f"Recurso remoto de otra coleccion: {relative}")

        if (
            path.is_file()
            and path.stat().st_size == int(remote.get("size_bytes", 0) or 0)
            and md5_file(path) == str(remote.get("md5", "")).lower()
        ):
            reused += 1
            item["estado"] = str(remote.get("local_state", "descargado"))
        else:
            missing.append((item, path, relative))

    print()
    print("RESTAURACION DEL CACHE VISUAL")
    print("=" * 72)
    print(f"Canal: {channel_profile(channel_slug)['display_name']}")
    print(f"Coleccion: {collection.name}")
    print(f"Recursos reutilizados localmente: {reused}")
    print(f"Recursos para descargar: {len(missing)}")
    print("=" * 72)

    if dry_run:
        print("SIMULACION CORRECTA: no se descargo ningun archivo.")
        return 0

    drive = drive_backup.cliente_drive() if missing else None
    for position, (item, path, relative) in enumerate(missing, start=1):
        print()
        print(f"{position}/{len(missing)} RESTAURANDO: {relative}")
        remote = item["drive_cache"]
        download_verified(
            drive,
            remote,
            path,
            channel_slug,
            collection.name,
        )
        item["estado"] = str(remote.get("local_state", "descargado"))
        item["archivo"] = str(path.resolve())

    plan = cache.get("plan")
    if isinstance(plan, dict) and plan.get("verified"):
        plan_path = Path(str(plan.get("local_path", ""))).expanduser()
        if not plan_path.is_absolute():
            plan_path = ROOT / "data" / "visual_plans" / Path(
                str(plan.get("relative_path", "plan_visual.json"))
            ).name
        plan_path = plan_path.resolve()
        visual_plans_root = (ROOT / "data" / "visual_plans").resolve()
        try:
            plan_path.relative_to(visual_plans_root)
        except ValueError as error:
            raise RuntimeError(
                "BLOQUEO DE SEGURIDAD: ruta del plan visual fuera de data/visual_plans."
            ) from error
        if not plan_path.is_file():
            if drive is None:
                drive = drive_backup.cliente_drive()
            print(f"RESTAURANDO PLAN VISUAL: {plan_path.name}")
            download_verified(
                drive,
                plan,
                plan_path,
                channel_slug,
                collection.name,
            )

    cache["local_state"] = "materialized"
    cache["restored_at"] = now()
    data["visual_cache"] = cache
    write_json(local_manifest, data)
    write_json(index_path(channel_slug, collection.name), data)

    print()
    print("CACHE VISUAL DISPONIBLE PARA EL RENDER")
    print(f"Restaurados desde Drive: {len(missing)}")
    print(f"Manifiesto: {local_manifest}")
    if from_index:
        print("El manifiesto local fue reconstruido desde su indice seguro.")
    return 0


def cleanup(
    channel_slug: str,
    manifest_path: Path | None,
    dry_run: bool,
    confirmed: bool,
) -> int:
    data, local_manifest, collection, _ = resolve_manifest(
        channel_slug,
        manifest_path,
        allow_index=True,
    )
    assert_channel(data, channel_slug)
    cache = data.get("visual_cache")
    if not isinstance(cache, dict) or cache.get("state") != "verified":
        raise RuntimeError(
            "No se eliminaran recursos sin un cache visual verificado en Drive."
        )
    if str(cache.get("channel_slug", "")) != channel_slug:
        raise RuntimeError("BLOQUEO MULTICANAL: cache visual de otro canal.")
    if str(cache.get("collection", "")) != collection.name:
        raise RuntimeError("BLOQUEO DE COLECCION: cache visual inconsistente.")

    items = visual_items(data, collection, require_local=False)
    local_items = [(item, path, rel) for item, path, rel in items if path.is_file()]
    total_bytes = sum(path.stat().st_size for _, path, _ in local_items)

    print()
    print("LIMPIEZA DEL CACHE VISUAL LOCAL")
    print("=" * 72)
    print(f"Canal: {channel_profile(channel_slug)['display_name']}")
    print(f"Coleccion: {collection.name}")
    print(f"Archivos locales: {len(local_items)}")
    print(f"Espacio recuperable: {drive_backup.formato_tamano(total_bytes)}")
    print("=" * 72)

    if dry_run:
        print("SIMULACION CORRECTA: no se elimino ningun recurso.")
        return 0
    if not confirmed:
        raise RuntimeError("Agrega --confirmar para eliminar copias locales.")

    drive = drive_backup.cliente_drive()
    snapshots: list[tuple[dict[str, Any], Path, str, int, int, str]] = []
    for position, (item, path, relative) in enumerate(local_items, start=1):
        remote = item.get("drive_cache")
        if not isinstance(remote, dict) or not remote.get("verified"):
            raise RuntimeError(f"Recurso sin copia verificada: {relative}")
        print(f"VERIFICANDO DRIVE {position}/{len(local_items)}: {relative}")
        metadata = remote_metadata(drive, remote)
        assert_remote(metadata, remote, channel_slug, collection.name)
        current_md5 = md5_file(path)
        if current_md5 != str(remote.get("md5", "")).lower():
            raise RuntimeError(
                "El archivo local cambio despues de archivarse y no se eliminara: "
                f"{relative}"
            )
        stat = path.stat()
        snapshots.append((item, path, relative, stat.st_size, stat.st_mtime_ns, current_md5))

    for item, path, relative, size, mtime_ns, expected_md5 in snapshots:
        stat = path.stat()
        if stat.st_size != size or stat.st_mtime_ns != mtime_ns:
            raise RuntimeError(
                "La coleccion cambio durante la verificacion y no se eliminara: "
                f"{relative}"
            )
        if md5_file(path) != expected_md5:
            raise RuntimeError(f"La huella local cambio: {relative}")

    for item, path, relative, _, _, _ in snapshots:
        path.unlink()
        item["estado"] = ARCHIVED_STATE
        print(f"ELIMINADO LOCAL: {relative}")

    for directory in sorted(
        (path for path in collection.rglob("*") if path.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass

    cache["local_state"] = "archived"
    cache["cleaned_at"] = now()
    cache["freed_bytes"] = total_bytes
    data["visual_cache"] = cache
    write_json(local_manifest, data)
    write_json(index_path(channel_slug, collection.name), data)

    output = report_path(channel_slug, "cleanup")
    write_json(
        output,
        {
            "action": "cleanup",
            "state": "completed",
            "channel_slug": channel_slug,
            "collection": collection.name,
            "completed_at": now(),
            "deleted_files": len(snapshots),
            "freed_bytes": total_bytes,
            "manifest": str(local_manifest),
        },
    )

    print()
    print("=" * 72)
    print("CACHE VISUAL LOCAL LIBERADO")
    print(f"Archivos eliminados: {len(snapshots)}")
    print(f"Espacio recuperado: {drive_backup.formato_tamano(total_bytes)}")
    print("Los recursos permanecen verificados en Google Drive.")
    print(f"Informe: {output}")
    print("=" * 72)
    return 0


def status(channel_slug: str, manifest_path: Path | None) -> int:
    data, local_manifest, collection, from_index = resolve_manifest(
        channel_slug,
        manifest_path,
        allow_index=True,
    )
    assert_channel(data, channel_slug)
    items = visual_items(data, collection, require_local=False)
    local = sum(1 for _, path, _ in items if path.is_file())
    verified = sum(
        1
        for item, _, _ in items
        if isinstance(item.get("drive_cache"), dict)
        and item["drive_cache"].get("verified")
    )
    print()
    print("ESTADO DEL CACHE VISUAL")
    print("=" * 72)
    print(f"Canal: {channel_profile(channel_slug)['display_name']}")
    print(f"Coleccion: {collection.name}")
    print(f"Recursos locales: {local}/{len(items)}")
    print(f"Recursos verificados en Drive: {verified}/{len(items)}")
    print(f"Manifiesto: {local_manifest}")
    print(f"Origen del estado: {'indice seguro' if from_index else 'coleccion local'}")
    print("=" * 72)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Guarda, restaura y libera recursos visuales verificados "
            "de AutoTube AI en Google Drive."
        )
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    for action in ("store", "restore", "cleanup", "status"):
        action_parser = subparsers.add_parser(action)
        action_parser.add_argument(
            "--canal",
            choices=CHANNEL_CHOICES,
            default=DEFAULT_CHANNEL,
        )
        action_parser.add_argument("--manifiesto", type=Path, default=None)
        if action in {"store", "restore", "cleanup"}:
            action_parser.add_argument("--dry-run", action="store_true")
        if action == "cleanup":
            action_parser.add_argument("--confirmar", action="store_true")

    args = parser.parse_args()
    channel_slug = normalize_channel_slug(args.canal)

    if args.action == "store":
        return store(channel_slug, args.manifiesto, args.dry_run)
    if args.action == "restore":
        return restore(channel_slug, args.manifiesto, args.dry_run)
    if args.action == "cleanup":
        return cleanup(
            channel_slug,
            args.manifiesto,
            args.dry_run,
            args.confirmar,
        )
    return status(channel_slug, args.manifiesto)


if __name__ == "__main__":
    raise SystemExit(main())
