from __future__ import annotations

import argparse
import sys
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from youtube_channels import (
    CHANNEL_CHOICES,
    DEFAULT_CHANNEL,
    build_youtube_client,
)


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id")
    parser.add_argument("ruta_miniatura", type=Path)
    parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
    )
    args = parser.parse_args()

    thumbnail_path = args.ruta_miniatura.expanduser().resolve()

    if not thumbnail_path.is_file():
        raise FileNotFoundError(
            f"No existe la miniatura: {thumbnail_path}"
        )

    if thumbnail_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("La miniatura supera el limite de 2 MB.")

    youtube, identity = build_youtube_client(args.canal, SCOPES)
    print(f"Canal verificado: {identity['channel_title']}")

    media = MediaFileUpload(
        str(thumbnail_path),
        mimetype="image/jpeg",
        resumable=False,
    )
    youtube.thumbnails().set(
        videoId=args.video_id,
        media_body=media,
    ).execute()

    print("MINIATURA COLOCADA CORRECTAMENTE")
    print(f"Video ID: {args.video_id}")
    print(f"Archivo: {thumbnail_path}")
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
