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
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_credentials():
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

    return credentials


def main():
    if len(sys.argv) != 3:
        print(
            "Uso: python youtube_captions.py VIDEO_ID ARCHIVO_SRT"
        )
        return 1

    video_id = sys.argv[1]
    srt_path = Path(sys.argv[2]).resolve()

    if not srt_path.exists():
        raise FileNotFoundError(
            f"No existe el SRT: {srt_path}"
        )

    youtube = build(
        "youtube",
        "v3",
        credentials=get_credentials(),
        cache_discovery=False,
    )

    existing = youtube.captions().list(
        part="snippet",
        videoId=video_id,
    ).execute()

    for track in existing.get("items", []):
        snippet = track.get("snippet", {})

        if (
            snippet.get("language") == "es"
            and snippet.get("name") == "Español"
        ):
            print(
                "Eliminando pista anterior:",
                track["id"],
            )

            youtube.captions().delete(
                id=track["id"],
            ).execute()

    body = {
        "snippet": {
            "videoId": video_id,
            "language": "es",
            "name": "Español",
            "isDraft": False,
        }
    }

    media = MediaFileUpload(
        str(srt_path),
        mimetype="application/octet-stream",
        resumable=False,
    )

    response = youtube.captions().insert(
        part="snippet",
        body=body,
        media_body=media,
    ).execute()

    print()
    print("SUBTÍTULOS SUBIDOS CORRECTAMENTE")
    print("Video ID:", video_id)
    print("Caption ID:", response.get("id"))
    print("Idioma: Español")
    print("Archivo:", srt_path)

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
