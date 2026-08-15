from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


ROOT = Path(__file__).resolve().parents[1]
CLIENT_SECRET = ROOT / "config" / "youtube" / "client_secret.json"
TOKEN_FILE = ROOT / "config" / "youtube" / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main():
    if not CLIENT_SECRET.exists():
        raise FileNotFoundError(
            f"No existe: {CLIENT_SECRET}"
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
            "Autorización completada. Puedes cerrar esta ventana."
        ),
    )

    TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    print("NUEVO TOKEN CREADO")
    print(TOKEN_FILE)


if __name__ == "__main__":
    main()
