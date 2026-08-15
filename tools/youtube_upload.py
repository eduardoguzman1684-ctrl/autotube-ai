from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT / "config" / "youtube" / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def get_credentials() -> Credentials:
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "No existe token.json. Ejecuta primero la autenticación."
        )

    credentials = Credentials.from_authorized_user_file(
        str(TOKEN_FILE),
        SCOPES,
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        TOKEN_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    if not credentials.valid:
        raise RuntimeError(
            "El token de YouTube no es válido. "
            "Vuelve a ejecutar la autenticación."
        )

    return credentials


def get_latest_video() -> Path:
    candidates = list(
        (ROOT / "output" / "videos").glob(
            "render_*/video_final_subtitulado_musica.mp4"
        )
    )

    if not candidates:
        raise FileNotFoundError(
            "No se encontró video_final_subtitulado_musica.mp4."
        )

    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy: str,
) -> str:
    youtube = build(
        "youtube",
        "v3",
        credentials=get_credentials(),
        cache_discovery=False,
    )

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": "28",
            "defaultLanguage": "es",
            "defaultAudioLanguage": "es",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
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

    while response is None:
        status, response = request.next_chunk()

        if status:
            progress = int(status.progress() * 100)
            print(f"Subiendo video: {progress}%")

    video_id = response.get("id")

    if not video_id:
        raise RuntimeError(
            f"YouTube no devolvió el ID del video: {response}"
        )

    return video_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path)
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        default="private",
    )
    args = parser.parse_args()

    video_path = (
        args.file.resolve()
        if args.file
        else get_latest_video()
    )

    title = (
        "Cómo Crear un Sistema de Automatización con "
        "Make y OpenAI desde Cero"
    )

    description = """Aprende cómo crear un sistema de automatización utilizando Make y OpenAI desde cero.

En esta guía práctica conocerás cómo conectar diferentes herramientas, automatizar tareas repetitivas y aprovechar la inteligencia artificial para ahorrar tiempo y mejorar la productividad.

Contenido del video:
- Qué es la automatización
- Cómo funciona Make
- Cómo integrar OpenAI
- Creación de un flujo automatizado
- Recomendaciones y errores que debes evitar

Suscríbete al canal para aprender más sobre inteligencia artificial, automatización y herramientas digitales.

#Automatización #Make #OpenAI #InteligenciaArtificial
"""

    tags = [
        "automatización",
        "Make",
        "OpenAI",
        "inteligencia artificial",
        "automatización con IA",
        "Make desde cero",
        "tutorial Make",
        "productividad",
        "herramientas digitales",
        "AutoTube AI",
    ]

    print(f"Video seleccionado: {video_path}")
    print(f"Privacidad: {args.privacy}")

    video_id = upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy=args.privacy,
    )

    print()
    print("VIDEO SUBIDO CORRECTAMENTE")
    print(f"ID: {video_id}")
    print(f"Dirección: https://youtu.be/{video_id}")
    print(f"Privacidad: {args.privacy}")
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
