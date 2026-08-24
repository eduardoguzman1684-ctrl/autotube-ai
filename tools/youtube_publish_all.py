from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
import time
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


ROOT = Path(__file__).resolve().parents[1]

TOKEN_FILE = ROOT / "config" / "youtube" / "token.json"
METADATA_FILE = ROOT / "data" / "publish" / "metadata.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def latest(pattern: str) -> Path:
    files = list(ROOT.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"No se encontró ningún archivo para: {pattern}"
        )

    return max(files, key=lambda p: p.stat().st_mtime)


def load_metadata() -> dict:
    if not METADATA_FILE.exists():
        raise FileNotFoundError(
            f"No existe metadata.json: {METADATA_FILE}"
        )

    return json.loads(
        METADATA_FILE.read_text(encoding="utf-8-sig")
    )


def credentials() -> Credentials:
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "No existe token.json. Ejecuta youtube_auth.py."
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
            "Las credenciales de YouTube no son válidas."
        )

    return creds


def youtube_client():
    return build(
        "youtube",
        "v3",
        credentials=credentials(),
        cache_discovery=False,
    )


def upload_video(
    youtube,
    video: Path,
    metadata: dict,
) -> str:

    body = {
        "snippet": {
            "title": metadata["title"][:100],
            "description": metadata["description"][:5000],
            "tags": metadata.get("tags", []),
            "categoryId": metadata.get(
                "category_id",
                "28",
            ),
            "defaultLanguage": metadata.get(
                "language",
                "es",
            ),
            "defaultAudioLanguage": metadata.get(
                "language",
                "es",
            ),
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video),
        mimetype="video/mp4",
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=False,
    )

    response = None
    reintentos = 0
    max_reintentos = 8

    while response is None:
        try:
            status, response = request.next_chunk()
            reintentos = 0

        except HttpError as error:
            codigo = getattr(
                error.resp,
                "status",
                None,
            )

            if codigo not in {
                500,
                502,
                503,
                504,
            }:
                raise

            reintentos += 1

            if reintentos > max_reintentos:
                raise

            espera = min(
                60,
                2 ** reintentos,
            )

            print(
                "YouTube temporalmente no disponible. "
                f"Reintento {reintentos}/"
                f"{max_reintentos} en "
                f"{espera} segundos..."
            )

            time.sleep(espera)
            continue

        except (
            ssl.SSLError,
            ConnectionError,
            TimeoutError,
            OSError,
        ) as error:
            reintentos += 1

            if reintentos > max_reintentos:
                raise

            espera = min(
                60,
                2 ** reintentos,
            )

            print(
                "Conexion interrumpida durante la subida "
                f"({type(error).__name__}). "
                f"Reintento {reintentos}/"
                f"{max_reintentos} en "
                f"{espera} segundos..."
            )

            time.sleep(espera)
            continue

        if status:
            print(
                f"Subiendo video: "
                f"{int(status.progress() * 100)}%"
            )

    video_id = response.get("id")

    if not video_id:
        raise RuntimeError(
            "YouTube no devolvió un ID."
        )

    return video_id


def set_thumbnail(
    youtube,
    video_id: str,
    thumbnail: Path,
):
    media = MediaFileUpload(
        str(thumbnail),
        mimetype="image/jpeg",
        resumable=False,
    )

    youtube.thumbnails().set(
        videoId=video_id,
        media_body=media,
    ).execute()


def upload_captions(
    youtube,
    video_id: str,
    srt: Path,
):
    body = {
        "snippet": {
            "videoId": video_id,
            "language": "es",
            "name": "Español",
            "isDraft": False,
        }
    }

    media = MediaFileUpload(
        str(srt),
        mimetype="application/octet-stream",
        resumable=False,
    )

    youtube.captions().insert(
        part="snippet",
        body=body,
        media_body=media,
    ).execute()


def change_visibility(
    youtube,
    video_id: str,
    privacy: str,
):
    result = youtube.videos().list(
        part="status",
        id=video_id,
    ).execute()

    items = result.get("items", [])

    if not items:
        raise RuntimeError(
            "No se pudo recuperar el video."
        )

    old_status = items[0]["status"]

    status = {
        "privacyStatus": privacy,
    }

    for field in (
        "embeddable",
        "license",
        "publicStatsViewable",
        "selfDeclaredMadeForKids",
        "containsSyntheticMedia",
    ):
        if field in old_status:
            status[field] = old_status[field]

    youtube.videos().update(
        part="status",
        body={
            "id": video_id,
            "status": status,
        },
    ).execute()


def calcular_sha256(
    archivo: Path,
) -> str:
    """Calcula una huella estable para evitar subidas duplicadas."""
    resumen = hashlib.sha256()

    with archivo.open("rb") as entrada:
        while True:
            bloque = entrada.read(
                4 * 1024 * 1024
            )

            if not bloque:
                break

            resumen.update(bloque)

    return resumen.hexdigest()


def buscar_publicacion_existente(
    video: Path,
    sha256_video: str,
) -> tuple[Path | None, dict]:
    """Busca un manifiesto que confirme la subida del mismo video."""
    manifiestos = sorted(
        (
            ruta
            for ruta in (
                ROOT
                / "output"
                / "youtube"
            ).glob("publish_*.json")
            if ruta.is_file()
        ),
        key=lambda ruta: ruta.stat().st_mtime,
        reverse=True,
    )

    video_resuelto = video.resolve()
    video_mtime = video.stat().st_mtime

    for manifiesto in manifiestos:
        try:
            datos = json.loads(
                manifiesto.read_text(
                    encoding="utf-8-sig"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            continue

        if not isinstance(datos, dict):
            continue

        video_id = str(
            datos.get(
                "video_id",
                "",
            )
        ).strip()

        if not video_id:
            continue

        huella_guardada = str(
            datos.get(
                "sha256",
                "",
            )
        ).strip()

        misma_huella = (
            bool(huella_guardada)
            and huella_guardada == sha256_video
        )

        misma_ruta = False
        ruta_guardada = datos.get(
            "video"
        )

        if ruta_guardada:
            try:
                misma_ruta = (
                    Path(
                        str(ruta_guardada)
                    ).resolve()
                    == video_resuelto
                    and manifiesto.stat().st_mtime
                    >= video_mtime
                )
            except OSError:
                misma_ruta = False

        if misma_huella or misma_ruta:
            return manifiesto, datos

    return None, {}


def save_manifest(
    video_id: str,
    video: Path,
    thumbnail: Path,
    srt: Path,
    metadata: dict,
    sha256_video: str,
):
    output = ROOT / "output" / "youtube"
    output.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    manifest = {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "video": str(video),
        "thumbnail": str(thumbnail),
        "subtitles": str(srt),
        "title": metadata["title"],
        "sha256": sha256_video,
        "size_bytes": video.stat().st_size,
        "privacy": metadata.get(
            "privacy",
            "private",
        ),
    }

    path = output / f"publish_{timestamp}.json"

    path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    metadata = load_metadata()

    video = latest(
        "output/videos/render_*/"
        "video_final_subtitulado_musica.mp4"
    )

    srt = latest(
        "output/subtitles/subtitulos_*/"
        "subtitulos.srt"
    )

    thumbnail = latest(
        "output/thumbnails/*.jpg"
    )

    sha256_video = calcular_sha256(
        video
    )

    manifiesto_existente, publicacion_existente = (
        buscar_publicacion_existente(
            video=video,
            sha256_video=sha256_video,
        )
    )

    print()
    print("NEXON IA - PUBLICACIÓN")
    print("=" * 50)
    print("Video:", video)
    print("Miniatura:", thumbnail)
    print("Subtítulos:", srt)
    print("Título:", metadata["title"])
    print(
        "Visibilidad final:",
        metadata.get("privacy", "private"),
    )
    print("=" * 50)

    if publicacion_existente:
        video_id_existente = str(
            publicacion_existente["video_id"]
        )

        print()
        print(
            "VIDEO YA PUBLICADO: subida omitida."
        )
        print(
            f"https://youtu.be/{video_id_existente}"
        )
        print(
            "Manifest:",
            manifiesto_existente,
        )
        return 0

    if args.dry_run:
        print()
        print("SIMULACIÓN CORRECTA")
        print(
            "No se ha subido nada a YouTube."
        )
        return 0

    youtube = youtube_client()

    print()
    print("1/4 Subiendo video...")
    video_id = upload_video(
        youtube,
        video,
        metadata,
    )

    print("2/4 Colocando miniatura...")
    set_thumbnail(
        youtube,
        video_id,
        thumbnail,
    )

    print("3/4 Subiendo subtítulos...")
    upload_captions(
        youtube,
        video_id,
        srt,
    )

    privacy = metadata.get(
        "privacy",
        "private",
    )

    print(
        f"4/4 Estableciendo visibilidad: "
        f"{privacy}"
    )

    change_visibility(
        youtube,
        video_id,
        privacy,
    )

    manifest = save_manifest(
        video_id,
        video,
        thumbnail,
        srt,
        metadata,
        sha256_video,
    )

    print()
    print("=" * 50)
    print("PUBLICACIÓN COMPLETADA")
    print(
        f"https://youtu.be/{video_id}"
    )
    print("Manifest:", manifest)
    print("=" * 50)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())

    except HttpError as exc:
        print(
            f"Error de YouTube API: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    except Exception as exc:
        print(
            f"Error: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
