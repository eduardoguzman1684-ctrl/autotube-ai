from __future__ import annotations

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


ROOT = Path(__file__).resolve().parents[1]
CLIENT_SECRET = (
    ROOT
    / "config"
    / "youtube"
    / "client_secret.json"
)
TOKEN_FILE = (
    ROOT
    / "config"
    / "google_drive"
    / "token.json"
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]


def main() -> None:
    if not CLIENT_SECRET.exists():
        raise FileNotFoundError(
            f"No existe el archivo OAuth: {CLIENT_SECRET}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET),
        SCOPES,
    )

    credenciales = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        prompt="consent",
        access_type="offline",
        authorization_prompt_message=(
            "Abriendo Google para autorizar "
            "el respaldo de AutoTube AI..."
        ),
        success_message=(
            "Autorizacion de Google Drive completada. "
            "Puedes cerrar esta ventana."
        ),
    )

    TOKEN_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    TOKEN_FILE.write_text(
        credenciales.to_json(),
        encoding="utf-8",
    )

    print("TOKEN DE GOOGLE DRIVE CREADO")
    print(TOKEN_FILE)


if __name__ == "__main__":
    main()
