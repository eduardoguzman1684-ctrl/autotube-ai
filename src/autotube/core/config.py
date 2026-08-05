from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Configuración central de AutoTube AI."""

    project_root: Path
    data_dir: Path
    output_dir: Path
    logs_dir: Path
    config_dir: Path

    environment: str
    log_level: str

    gemini_api_key: str | None
    pixabay_api_key: str | None
    youtube_client_secret_file: str | None

    @property
    def youtube_client_secret_path(self) -> Path | None:
        """Devuelve la ruta absoluta del archivo de credenciales de YouTube."""
        if not self.youtube_client_secret_file:
            return None

        path = Path(self.youtube_client_secret_file).expanduser()

        if not path.is_absolute():
            path = self.project_root / path

        return path.resolve()

    @property
    def youtube_is_configured(self) -> bool:
        """Indica si el archivo real de credenciales de YouTube existe."""
        path = self.youtube_client_secret_path
        return path is not None and path.is_file()

    def create_directories(self) -> None:
        """Crea las carpetas de trabajo cuando no existen."""
        for directory in (
            self.data_dir,
            self.output_dir,
            self.logs_dir,
            self.config_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def find_project_root() -> Path:
    """Localiza la raíz del proyecto a partir de este archivo."""
    return Path(__file__).resolve().parents[3]


def load_settings() -> Settings:
    """Carga la configuración desde variables del sistema y .env."""
    project_root = find_project_root()
    env_file = project_root / ".env"

    load_dotenv(env_file, override=False)

    settings = Settings(
        project_root=project_root,
        data_dir=project_root / "data",
        output_dir=project_root / "output",
        logs_dir=project_root / "logs",
        config_dir=project_root / "config",
        environment=os.getenv("AUTOTUBE_ENV", "development"),
        log_level=os.getenv("AUTOTUBE_LOG_LEVEL", "INFO").upper(),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        pixabay_api_key=os.getenv("PIXABAY_API_KEY"),
        youtube_client_secret_file=os.getenv(
            "YOUTUBE_CLIENT_SECRET_FILE"
        ),
    )

    settings.create_directories()
    return settings