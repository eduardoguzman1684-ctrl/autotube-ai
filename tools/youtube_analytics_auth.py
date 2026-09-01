from __future__ import annotations

import argparse
from pathlib import Path

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

from youtube_channels import (
    CHANNEL_CHOICES,
    DEFAULT_CHANNEL,
    analytics_token_file,
    build_youtube_client,
    channel_profile,
    verify_channel,
)


ROOT = Path(__file__).resolve().parents[1]
CLIENT_SECRET = ROOT / "config" / "youtube" / "client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Autoriza YouTube Analytics por canal."
    )
    parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
    )
    parser.add_argument(
        "--verificar",
        action="store_true",
    )
    parser.add_argument(
        "--reautorizar",
        action="store_true",
    )
    args = parser.parse_args()

    profile = channel_profile(args.canal)
    destination = analytics_token_file(args.canal)

    if args.verificar:
        _, identity = build_youtube_client(
            args.canal,
            SCOPES,
            analytics=True,
        )
        print("TOKEN DE ANALYTICS VERIFICADO")
        print(f"Perfil: {profile['display_name']}")
        print(f"Canal real: {identity['channel_title']}")
        print(f"ID: {identity['channel_id']}")
        return 0

    if not CLIENT_SECRET.is_file():
        raise FileNotFoundError(
            f"No existe el archivo OAuth: {CLIENT_SECRET}"
        )

    if destination.exists() and not args.reautorizar:
        raise FileExistsError(
            f"Ya existe el token de Analytics: {destination}. "
            "Usa --verificar o agrega --reautorizar."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET),
        SCOPES,
    )
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        prompt="consent",
        access_type="offline",
        authorization_prompt_message=(
            "Abriendo Google para autorizar YouTube Analytics..."
        ),
        success_message=(
            "Autorizacion de Analytics completada. "
            "Puedes cerrar esta ventana."
        ),
    )

    youtube = build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )
    identity = verify_channel(youtube, args.canal)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(credentials.to_json(), encoding="utf-8")

    print("TOKEN DE ANALYTICS CREADO Y VERIFICADO")
    print(f"Perfil: {profile['display_name']}")
    print(f"Canal real: {identity['channel_title']}")
    print(f"ID: {identity['channel_id']}")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
