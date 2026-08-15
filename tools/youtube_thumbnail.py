from pathlib import Path
import sys

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
            f"No se encontró el token: {TOKEN_FILE}"
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
        raise RuntimeError("El token de YouTube no es válido.")

    return credentials


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Uso: python youtube_thumbnail.py "
            "VIDEO_ID RUTA_MINIATURA"
        )
        return 1

    video_id = sys.argv[1]
    thumbnail_path = Path(sys.argv[2]).resolve()

    if not thumbnail_path.exists():
        raise FileNotFoundError(
            f"No existe la miniatura: {thumbnail_path}"
        )

    if thumbnail_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError(
            "La miniatura supera el límite de 2 MB."
        )

    youtube = build(
        "youtube",
        "v3",
        credentials=get_credentials(),
        cache_discovery=False,
    )

    media = MediaFileUpload(
        str(thumbnail_path),
        mimetype="image/jpeg",
        resumable=False,
    )

    youtube.thumbnails().set(
        videoId=video_id,
        media_body=media,
    ).execute()

    print("MINIATURA COLOCADA CORRECTAMENTE")
    print(f"Video ID: {video_id}")
    print(f"Archivo: {thumbnail_path}")
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
