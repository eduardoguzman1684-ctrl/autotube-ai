from __future__ import annotations

import argparse
from pathlib import Path

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

from youtube_channels import (
    CHANNEL_CHOICES,
    DEFAULT_CHANNEL,
    build_youtube_client,
    channel_profile,
    token_file,
    verify_channel,
)


ROOT = Path(__file__).resolve().parents[1]
CLIENT_SECRET = ROOT / "config" / "youtube" / "client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Autoriza o verifica un canal de YouTube."
    )
    parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Perfil de canal que se autorizara.",
    )
    parser.add_argument(
        "--verificar",
        action="store_true",
        help="Comprueba el token existente sin abrir OAuth.",
    )
    parser.add_argument(
        "--reautorizar",
        action="store_true",
        help="Permite reemplazar el token del perfil indicado.",
    )
    args = parser.parse_args()

    profile = channel_profile(args.canal)
    destination = token_file(args.canal)

    if args.verificar:
        _, identity = build_youtube_client(args.canal, SCOPES)
        print("TOKEN VERIFICADO")
        print(f"Perfil: {profile['display_name']} ({profile['slug']})")
        print(f"Canal real: {identity['channel_title']}")
        print(f"ID: {identity['channel_id']}")
        print(f"Token: {destination}")
        return 0

    if not CLIENT_SECRET.is_file():
        raise FileNotFoundError(f"No existe: {CLIENT_SECRET}")

    if destination.exists() and not args.reautorizar:
        raise FileExistsError(
            f"Ya existe un token para {profile['display_name']}: "
            f"{destination}. Usa --verificar o, si deseas reemplazarlo "
            "intencionalmente, agrega --reautorizar."
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
            "Abriendo Google para autorizar AutoTube AI..."
        ),
        success_message=(
            "Autorizacion completada. Puedes cerrar esta ventana."
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

    print("NUEVO TOKEN CREADO Y VERIFICADO")
    print(f"Perfil: {profile['display_name']} ({profile['slug']})")
    print(f"Canal real: {identity['channel_title']}")
    print(f"ID: {identity['channel_id']}")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
