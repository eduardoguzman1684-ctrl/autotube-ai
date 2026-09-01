from __future__ import annotations

import argparse
import sys

from googleapiclient.errors import HttpError

from youtube_channels import (
    CHANNEL_CHOICES,
    DEFAULT_CHANNEL,
    build_youtube_client,
)


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id")
    parser.add_argument(
        "privacy",
        choices=("private", "unlisted", "public"),
    )
    parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
    )
    args = parser.parse_args()

    youtube, identity = build_youtube_client(args.canal, SCOPES)
    print(f"Canal verificado: {identity['channel_title']}")

    result = youtube.videos().list(
        part="status,snippet",
        id=args.video_id,
    ).execute()
    items = result.get("items", [])

    if not items:
        raise RuntimeError(
            "No se encontro el video o no pertenece al canal seleccionado."
        )

    video = items[0]
    old_status = video["status"]
    print("Video:", video["snippet"]["title"])
    print("Visibilidad actual:", old_status.get("privacyStatus"))

    status = {"privacyStatus": args.privacy}
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
        body={"id": args.video_id, "status": status},
    ).execute()

    print("VISIBILIDAD ACTUALIZADA")
    print("Video ID:", args.video_id)
    print("Nueva visibilidad:", response["status"]["privacyStatus"])
    print("Direccion:", f"https://youtu.be/{args.video_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HttpError as exc:
        print(f"Error de YouTube API: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
