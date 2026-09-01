from __future__ import annotations

import json
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANNEL = "nexon_ia"

CHANNELS: dict[str, dict[str, Any]] = {
    "nexon_ia": {
        "display_name": "Nexon IA",
        "expected_titles": ("Nexon IA",),
        "short_description": "Contenido de Nexon IA.",
        "short_tags": [
            "Inteligencia Artificial",
            "Tecnologia",
            "Ciencia",
            "Nexon IA",
            "Shorts",
        ],
    },
    "cogniviva": {
        "display_name": "CogniViva",
        "expected_titles": ("CogniViva",),
        "short_description": (
            "Psicologia practica para entender lo que piensas, "
            "sientes y haces."
        ),
        "short_tags": [
            "Psicologia",
            "Habitos",
            "Emociones",
            "Relaciones",
            "CogniViva",
            "Shorts",
        ],
    },
}

CHANNEL_CHOICES = tuple(CHANNELS)


def normalize_channel_slug(value: str | None) -> str:
    slug = str(value or DEFAULT_CHANNEL).strip().lower().replace("-", "_")

    if slug not in CHANNELS:
        valid = ", ".join(CHANNEL_CHOICES)
        raise ValueError(f"Canal no valido: {value!r}. Opciones: {valid}")

    return slug


def channel_profile(value: str | None) -> dict[str, Any]:
    slug = normalize_channel_slug(value)
    return {"slug": slug, **CHANNELS[slug]}


def channel_directory(value: str | None) -> Path:
    return (
        ROOT
        / "config"
        / "youtube"
        / "channels"
        / normalize_channel_slug(value)
    )


def token_file(value: str | None) -> Path:
    return channel_directory(value) / "token.json"


def analytics_token_file(value: str | None) -> Path:
    return channel_directory(value) / "analytics_token.json"


def identity_file(value: str | None) -> Path:
    return channel_directory(value) / "channel.json"


def load_credentials(
    value: str | None,
    scopes: Iterable[str],
    *,
    analytics: bool = False,
) -> Credentials:
    slug = normalize_channel_slug(value)
    path = analytics_token_file(slug) if analytics else token_file(slug)

    if not path.is_file():
        script = "youtube_analytics_auth.py" if analytics else "youtube_auth.py"
        raise FileNotFoundError(
            f"No existe el token del canal {slug}: {path}. "
            f"Ejecuta: python tools/{script} --canal {slug}"
        )

    credentials = Credentials.from_authorized_user_file(
        str(path),
        list(scopes),
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        path.write_text(credentials.to_json(), encoding="utf-8")

    if not credentials.valid:
        raise RuntimeError(
            f"El token de YouTube para {slug} no es valido. "
            "Vuelve a autorizar ese canal."
        )

    return credentials


def _normalized_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return " ".join(without_marks.casefold().split())


def authorized_channel(youtube) -> dict[str, str]:
    response = youtube.channels().list(
        part="id,snippet",
        mine=True,
        maxResults=1,
    ).execute()
    items = response.get("items", [])

    if not items:
        raise RuntimeError(
            "YouTube no devolvio ningun canal para estas credenciales."
        )

    item = items[0]
    return {
        "channel_id": str(item.get("id", "")).strip(),
        "channel_title": str(
            item.get("snippet", {}).get("title", "")
        ).strip(),
    }


def verify_channel(
    youtube,
    value: str | None,
    *,
    save: bool = True,
) -> dict[str, str]:
    profile = channel_profile(value)
    slug = profile["slug"]
    current = authorized_channel(youtube)
    current_id = current["channel_id"]
    current_title = current["channel_title"]

    if not current_id:
        raise RuntimeError("YouTube devolvio un canal sin ID.")

    path = identity_file(slug)
    saved: dict[str, Any] = {}

    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                saved = loaded
        except (OSError, json.JSONDecodeError):
            saved = {}

    saved_id = str(saved.get("channel_id", "")).strip()

    if saved_id and saved_id != current_id:
        raise RuntimeError(
            "BLOQUEO DE SEGURIDAD: el token seleccionado pertenece a "
            f"'{current_title}' ({current_id}), pero el perfil {slug} "
            f"esta vinculado a otro canal ({saved_id})."
        )

    if not saved_id:
        expected = {
            _normalized_title(str(title))
            for title in profile["expected_titles"]
        }

        if _normalized_title(current_title) not in expected:
            raise RuntimeError(
                "BLOQUEO DE SEGURIDAD: autorizaste el canal "
                f"'{current_title}', pero elegiste el perfil "
                f"'{profile['display_name']}'. Repite la autorizacion "
                "y selecciona el canal correcto."
            )

    identity = {
        "channel_slug": slug,
        "expected_name": profile["display_name"],
        "channel_id": current_id,
        "channel_title": current_title,
        "verified_at": (
            datetime.now().astimezone().isoformat(timespec="seconds")
        ),
    }

    if save:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(identity, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return identity


def build_youtube_client(
    value: str | None,
    scopes: Iterable[str],
    *,
    analytics: bool = False,
):
    credentials = load_credentials(value, scopes, analytics=analytics)
    youtube = build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )
    identity = verify_channel(youtube, value)
    return youtube, identity
