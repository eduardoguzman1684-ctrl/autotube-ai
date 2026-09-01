from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from autotube.content.channel_profiles import (
    CHANNEL_CHOICES,
    DEFAULT_CHANNEL,
    channel_profile,
    normalize_channel_slug,
)


ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = (
    ROOT
    / "config"
    / "google_drive"
    / "token.json"
)
OUTPUT_DIR = (
    ROOT
    / "output"
    / "google_drive"
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]

MIME_CARPETA = (
    "application/vnd.google-apps.folder"
)


def credenciales() -> Credentials:
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "No existe config/google_drive/token.json. "
            "Ejecuta tools/google_drive_auth.py."
        )

    creds = Credentials.from_authorized_user_file(
        str(TOKEN_FILE),
        SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

        TOKEN_FILE.write_text(
            creds.to_json(),
            encoding="utf-8",
        )

    if not creds.valid:
        raise RuntimeError(
            "Las credenciales de Google Drive "
            "no son validas."
        )

    return creds


def cliente_drive():
    return build(
        "drive",
        "v3",
        credentials=credenciales(),
        cache_discovery=False,
    )


def ultimo(
    patron: str,
) -> Path | None:
    archivos = [
        ruta
        for ruta in ROOT.glob(patron)
        if ruta.is_file()
    ]

    if not archivos:
        return None

    return max(
        archivos,
        key=lambda ruta: ruta.stat().st_mtime,
    )


def cargar_json(
    ruta: Path | None,
) -> dict[str, Any]:
    if ruta is None or not ruta.is_file():
        return {}

    try:
        contenido = json.loads(
            ruta.read_text(
                encoding="utf-8-sig"
            )
        )

        return (
            contenido
            if isinstance(contenido, dict)
            else {}
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return {}


def limpiar_nombre(
    texto: str,
    limite: int = 90,
) -> str:
    limpio = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        " ",
        str(texto),
    )

    limpio = " ".join(
        limpio.split()
    ).strip(" .")

    if not limpio:
        limpio = "produccion_autotube"

    return limpio[:limite].rstrip()


def agregar_archivo(
    archivos: list[Path],
    vistos: set[Path],
    ruta: Path | None,
) -> None:
    if ruta is None:
        return

    try:
        ruta_resuelta = ruta.resolve()
    except OSError:
        return

    if (
        ruta_resuelta.is_file()
        and ruta_resuelta.stat().st_size > 0
        and ruta_resuelta not in vistos
    ):
        vistos.add(ruta_resuelta)
        archivos.append(ruta_resuelta)


def resolver_ruta(
    ruta: Path | None,
    patron: str,
    etiqueta: str,
) -> Path:
    candidata = ruta

    if candidata is not None:
        candidata = candidata.expanduser()
        if not candidata.is_absolute():
            candidata = ROOT / candidata
    else:
        candidata = ultimo(patron)

    if candidata is None or not candidata.is_file():
        raise FileNotFoundError(
            f"No se encontro {etiqueta}: {candidata or patron}"
        )

    return candidata.resolve()


def canal_json(
    datos: dict[str, Any],
) -> str:
    return normalize_channel_slug(
        str(
            datos.get(
                "channel_slug",
                DEFAULT_CHANNEL,
            )
        )
    )


def buscar_publicacion_del_video(
    video: Path,
    channel_slug: str,
) -> tuple[Path | None, dict[str, Any]]:
    for ruta in sorted(
        ROOT.glob(
            "output/youtube/publish_*.json"
        ),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        datos = cargar_json(ruta)

        try:
            canal = canal_json(datos)
        except ValueError:
            continue

        if canal != channel_slug:
            continue

        ruta_video = datos.get("video")
        if not ruta_video:
            continue

        try:
            coincide = (
                Path(str(ruta_video)).resolve()
                == video.resolve()
            )
        except OSError:
            coincide = False

        if coincide:
            return ruta, datos

    return None, {}


def seleccionar_archivos(
    incluir_video: bool,
    channel_slug: str = DEFAULT_CHANNEL,
    video_path: Path | None = None,
    thumbnail_path: Path | None = None,
    subtitles_path: Path | None = None,
    metadata_path: Path | None = None,
    shorts_manifest_path: Path | None = None,
) -> tuple[
    list[Path],
    str,
    dict[str, Any],
]:
    channel_slug = normalize_channel_slug(
        channel_slug
    )
    profile = channel_profile(channel_slug)
    archivos: list[Path] = []
    vistos: set[Path] = set()

    video = resolver_ruta(
        video_path,
        (
            "output/videos/render_*/"
            "video_final_subtitulado_musica.mp4"
        ),
        "el video final",
    )
    miniatura = resolver_ruta(
        thumbnail_path,
        (
            "output/thumbnails/"
            "miniatura_youtube_autotube.jpg"
        ),
        "la miniatura",
    )
    subtitulos = resolver_ruta(
        subtitles_path,
        (
            "output/subtitles/"
            "subtitulos_*/subtitulos.srt"
        ),
        "los subtitulos",
    )
    metadata = resolver_ruta(
        metadata_path,
        "data/publish/metadata.json",
        "la metadata",
    )
    datos_metadata = cargar_json(metadata)

    if canal_json(datos_metadata) != channel_slug:
        raise RuntimeError(
            "BLOQUEO MULTICANAL: la metadata pertenece a "
            f"{canal_json(datos_metadata)}, no a {channel_slug}."
        )

    manifiesto_publicacion, publicacion = (
        buscar_publicacion_del_video(
            video,
            channel_slug,
        )
    )

    agregar_archivo(
        archivos,
        vistos,
        manifiesto_publicacion,
    )

    if incluir_video:
        agregar_archivo(
            archivos,
            vistos,
            video,
        )

    for ruta in (
        miniatura,
        subtitulos,
        metadata,
    ):
        agregar_archivo(
            archivos,
            vistos,
            ruta,
        )

    manifiesto_shorts = None

    if shorts_manifest_path is not None:
        manifiesto_shorts = resolver_ruta(
            shorts_manifest_path,
            "",
            "el manifiesto de Shorts",
        )
        datos_shorts = cargar_json(
            manifiesto_shorts
        )

        if canal_json(datos_shorts) != channel_slug:
            raise RuntimeError(
                "BLOQUEO MULTICANAL: los Shorts pertenecen a "
                f"{canal_json(datos_shorts)}, no a {channel_slug}."
            )

        agregar_archivo(
            archivos,
            vistos,
            manifiesto_shorts,
        )

        shorts = datos_shorts.get(
            "shorts",
            [],
        )

        if isinstance(shorts, list):
            for elemento in shorts:
                if not isinstance(elemento, dict):
                    continue
                archivo = elemento.get("archivo")
                if archivo:
                    agregar_archivo(
                        archivos,
                        vistos,
                        Path(str(archivo)),
                    )

        estado_shorts = (
            manifiesto_shorts.parent
            / f"youtube_publish_{channel_slug}.json"
        )
        if (
            channel_slug == DEFAULT_CHANNEL
            and not estado_shorts.is_file()
        ):
            estado_shorts = (
                manifiesto_shorts.parent
                / "youtube_publish.json"
            )
        agregar_archivo(
            archivos,
            vistos,
            estado_shorts,
        )

    titulo = str(
        datos_metadata.get(
            "title",
            f"Produccion {profile['display_name']}",
        )
    ).strip()
    identificador = ""
    coincidencia = re.search(
        r"render_(\d{8}_\d{6})",
        str(video),
    )

    if coincidencia:
        identificador = coincidencia.group(1)

    if not identificador:
        identificador = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

    nombre_carpeta = limpiar_nombre(
        f"{identificador} - {titulo}",
        limite=110,
    )
    contexto = {
        "channel_slug": channel_slug,
        "channel_name": profile["display_name"],
        "titulo": titulo,
        "video": str(video),
        "metadata": str(metadata),
        "video_id": str(
            publicacion.get("video_id", "")
        ),
        "youtube_url": str(
            publicacion.get("url", "")
        ),
        "manifiesto_publicacion": (
            str(manifiesto_publicacion)
            if manifiesto_publicacion
            else ""
        ),
        "manifiesto_shorts": (
            str(manifiesto_shorts)
            if manifiesto_shorts
            else ""
        ),
    }

    return archivos, nombre_carpeta, contexto


def escapar_consulta(
    texto: str,
) -> str:
    return (
        str(texto)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
    )


def buscar_elemento(
    drive,
    nombre: str,
    padre_id: str,
    mime_type: str | None = None,
) -> dict[str, Any] | None:
    condiciones = [
        f"name = '{escapar_consulta(nombre)}'",
        f"'{padre_id}' in parents",
        "trashed = false",
    ]

    if mime_type:
        condiciones.append(
            f"mimeType = '{mime_type}'"
        )

    respuesta = (
        drive.files()
        .list(
            q=" and ".join(
                condiciones
            ),
            spaces="drive",
            pageSize=10,
            fields=(
                "files("
                "id,name,mimeType,"
                "md5Checksum,size,webViewLink"
                ")"
            ),
        )
        .execute(
            num_retries=5
        )
    )

    elementos = respuesta.get(
        "files",
        [],
    )

    if not elementos:
        return None

    return elementos[0]


def obtener_o_crear_carpeta(
    drive,
    nombre: str,
    padre_id: str,
) -> dict[str, Any]:
    existente = buscar_elemento(
        drive,
        nombre,
        padre_id,
        MIME_CARPETA,
    )

    if existente:
        print(
            f"CARPETA REUTILIZADA: {nombre}"
        )
        return existente

    cuerpo = {
        "name": nombre,
        "mimeType": MIME_CARPETA,
        "parents": [padre_id],
        "appProperties": {
            "autotube": "1",
            "tipo": "respaldo",
        },
    }

    carpeta = (
        drive.files()
        .create(
            body=cuerpo,
            fields="id,name,webViewLink",
        )
        .execute(
            num_retries=5
        )
    )

    print(
        f"CARPETA CREADA: {nombre}"
    )

    return carpeta


def md5_archivo(
    ruta: Path,
) -> str:
    resumen = hashlib.md5()

    with ruta.open("rb") as entrada:
        while True:
            bloque = entrada.read(
                1024 * 1024
            )

            if not bloque:
                break

            resumen.update(bloque)

    return resumen.hexdigest()


def subir_archivo(
    drive,
    ruta: Path,
    carpeta_id: str,
) -> dict[str, Any]:
    existente = buscar_elemento(
        drive,
        ruta.name,
        carpeta_id,
    )

    md5_local = md5_archivo(
        ruta
    )

    if (
        existente
        and existente.get(
            "md5Checksum"
        ) == md5_local
    ):
        print(
            f"REUTILIZADO: {ruta.name}"
        )

        return {
            **existente,
            "estado": "reutilizado",
            "ruta_local": str(ruta),
        }

    mime_type = (
        mimetypes.guess_type(
            ruta.name
        )[0]
        or "application/octet-stream"
    )

    media = MediaFileUpload(
        str(ruta),
        mimetype=mime_type,
        chunksize=16 * 1024 * 1024,
        resumable=True,
    )

    campos = (
        "id,name,mimeType,"
        "md5Checksum,size,webViewLink"
    )

    if existente:
        solicitud = (
            drive.files()
            .update(
                fileId=existente["id"],
                media_body=media,
                fields=campos,
            )
        )
        accion = "ACTUALIZANDO"

    else:
        cuerpo = {
            "name": ruta.name,
            "parents": [
                carpeta_id
            ],
            "appProperties": {
                "autotube": "1",
                "tipo": "archivo_respaldo",
            },
        }

        solicitud = (
            drive.files()
            .create(
                body=cuerpo,
                media_body=media,
                fields=campos,
            )
        )
        accion = "SUBIENDO"

    print(
        f"{accion}: {ruta.name}"
    )

    respuesta = None

    while respuesta is None:
        estado, respuesta = (
            solicitud.next_chunk(
                num_retries=5
            )
        )

        if estado:
            porcentaje = int(
                estado.progress()
                * 100
            )

            print(
                f"  Progreso: "
                f"{porcentaje}%"
            )

    return {
        **respuesta,
        "estado": (
            "actualizado"
            if existente
            else "subido"
        ),
        "ruta_local": str(ruta),
    }


def formato_tamano(
    bytes_totales: int,
) -> str:
    valor = float(bytes_totales)

    for unidad in (
        "B",
        "KB",
        "MB",
        "GB",
    ):
        if valor < 1024:
            return (
                f"{valor:.1f} {unidad}"
            )

        valor /= 1024

    return f"{valor:.1f} TB"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Respalda la produccion mas reciente "
            "de AutoTube AI en Google Drive."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Muestra los archivos sin "
            "crear carpetas ni subirlos."
        ),
    )

    parser.add_argument(
        "--sin-video",
        action="store_true",
        help=(
            "Respalda documentos y Shorts, "
            "pero omite el video principal."
        ),
    )

    parser.add_argument(
        "--carpeta-raiz",
        default=None,
        help=(
            "Nombre de la carpeta raiz "
            "en Google Drive. Por defecto usa la del canal."
        ),
    )

    parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal propietario de la produccion.",
    )

    parser.add_argument("--video", type=Path)
    parser.add_argument("--miniatura", type=Path)
    parser.add_argument("--subtitulos", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument(
        "--manifiesto-shorts",
        type=Path,
        default=None,
    )

    args = parser.parse_args()
    channel_slug = normalize_channel_slug(
        args.canal
    )
    profile = channel_profile(channel_slug)
    root_folder_name = limpiar_nombre(
        args.carpeta_raiz
        or str(
            profile[
                "drive_root_folder"
            ]
        )
    )

    archivos, nombre_produccion, contexto = (
        seleccionar_archivos(
            incluir_video=(
                not args.sin_video
            ),
            channel_slug=channel_slug,
            video_path=args.video,
            thumbnail_path=args.miniatura,
            subtitles_path=args.subtitulos,
            metadata_path=args.metadata,
            shorts_manifest_path=(
                args.manifiesto_shorts
            ),
        )
    )

    if not archivos:
        raise RuntimeError(
            "No se encontraron archivos "
            "para respaldar."
        )

    total_bytes = sum(
        archivo.stat().st_size
        for archivo in archivos
    )

    print()
    print(
        f"{str(profile['brand_label']).upper()} "
        "- RESPALDO EN GOOGLE DRIVE"
    )
    print("=" * 64)
    print(
        f"Produccion: {nombre_produccion}"
    )
    print(
        f"Canal: {profile['display_name']} "
        f"({channel_slug})"
    )
    print(
        f"Carpeta raiz: {root_folder_name}"
    )
    print(
        f"Archivos: {len(archivos)}"
    )
    print(
        "Tamano total: "
        f"{formato_tamano(total_bytes)}"
    )
    print("=" * 64)

    for posicion, archivo in enumerate(
        archivos,
        start=1,
    ):
        print(
            f"{posicion}. "
            f"{archivo.name} | "
            f"{formato_tamano(archivo.stat().st_size)}"
        )

    if args.dry_run:
        print()
        print("SIMULACION CORRECTA")
        print(
            "No se creo ni subio "
            "ningun archivo."
        )
        return 0

    drive = cliente_drive()

    carpeta_raiz = (
        obtener_o_crear_carpeta(
            drive,
            root_folder_name,
            "root",
        )
    )

    carpeta_produccion = (
        obtener_o_crear_carpeta(
            drive,
            nombre_produccion,
            str(
                carpeta_raiz["id"]
            ),
        )
    )

    resultados: list[
        dict[str, Any]
    ] = []

    print()
    print("INICIANDO RESPALDO")
    print("-" * 64)

    for posicion, archivo in enumerate(
        archivos,
        start=1,
    ):
        print()
        print(
            f"{posicion}/{len(archivos)}"
        )

        resultado = subir_archivo(
            drive,
            archivo,
            str(
                carpeta_produccion["id"]
            ),
        )

        resultados.append(
            resultado
        )

    output_channel_dir = (
        OUTPUT_DIR
        / channel_slug
    )
    output_channel_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifiesto = {
        "channel_slug": channel_slug,
        "channel_name": profile["display_name"],
        "generado_en": (
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            )
        ),
        "carpeta_raiz": {
            "id": carpeta_raiz["id"],
            "nombre": (
                carpeta_raiz["name"]
            ),
            "url": (
                "https://drive.google.com/"
                "drive/folders/"
                f"{carpeta_raiz['id']}"
            ),
        },
        "carpeta_produccion": {
            "id": (
                carpeta_produccion["id"]
            ),
            "nombre": (
                carpeta_produccion["name"]
            ),
            "url": (
                "https://drive.google.com/"
                "drive/folders/"
                f"{carpeta_produccion['id']}"
            ),
        },
        "contexto": contexto,
        "cantidad_archivos": len(
            resultados
        ),
        "tamano_total_bytes": total_bytes,
        "archivos": resultados,
    }

    salida = (
        output_channel_dir
        / (
            "backup_"
            + datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
            + ".json"
        )
    )

    salida.write_text(
        json.dumps(
            manifiesto,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 64)
    print("RESPALDO COMPLETADO")
    print(
        "Carpeta: "
        f"{manifiesto['carpeta_produccion']['url']}"
    )
    print(
        f"Manifiesto local: {salida}"
    )
    print("=" * 64)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
