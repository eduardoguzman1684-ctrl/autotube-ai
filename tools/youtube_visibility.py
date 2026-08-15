from pathlib import Path
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT / "config" / "youtube" / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

VALID = {"private", "unlisted", "public"}


def credentials():
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

    return creds


def main():
    if len(sys.argv) != 3:
        print(
            "Uso: python youtube_visibility.py "
            "VIDEO_ID public|private|unlisted"
        )
        return 1

    video_id = sys.argv[1]
    new_privacy = sys.argv[2].lower()

    if new_privacy not in VALID:
        raise ValueError(
            "Usa public, private o unlisted."
        )

    youtube = build(
        "youtube",
        "v3",
        credentials=credentials(),
        cache_discovery=False,
    )

    result = youtube.videos().list(
        part="status,snippet",
        id=video_id,
    ).execute()

    items = result.get("items", [])

    if not items:
        raise RuntimeError(
            "No se encontró el video o no pertenece a esta cuenta."
        )

    video = items[0]
    old_status = video["status"]
    title = video["snippet"]["title"]

    print("Video:", title)
    print(
        "Visibilidad actual:",
        old_status.get("privacyStatus")
    )

    status = {
        "privacyStatus": new_privacy,
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

    response = youtube.videos().update(
        part="status",
        body={
            "id": video_id,
            "status": status,
        },
    ).execute()

    print()
    print("VISIBILIDAD ACTUALIZADA")
    print("Video ID:", video_id)
    print(
        "Nueva visibilidad:",
        response["status"]["privacyStatus"],
    )
    print(
        "Dirección:",
        f"https://youtu.be/{video_id}",
    )

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
