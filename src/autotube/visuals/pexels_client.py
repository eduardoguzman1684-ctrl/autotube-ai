from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PEXELS_PHOTO_API_URL = "https://api.pexels.com/v1/search"
PEXELS_VIDEO_API_URL = "https://api.pexels.com/videos/search"


class ClientePexels:
    """Busca y descarga fotografías y videos desde Pexels."""

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        load_dotenv(
            Path(".env"),
            override=False,
        )

        self.api_key = (
            api_key
            or os.getenv("PEXELS_API_KEY")
            or ""
        ).strip()

        if not self.api_key:
            raise RuntimeError(
                "PEXELS_API_KEY está vacía en el archivo .env."
            )

        self.headers = {
            "Authorization": self.api_key,
            "User-Agent": "AutoTubeIA/1.0",
        }

    def _solicitar(
        self,
        endpoint: str,
        parametros: dict[str, Any],
    ) -> dict[str, Any]:
        url = (
            endpoint
            + "?"
            + urllib.parse.urlencode(parametros)
        )

        solicitud = urllib.request.Request(
            url,
            headers=self.headers,
        )

        with urllib.request.urlopen(
            solicitud,
            timeout=45,
        ) as respuesta:
            contenido = json.load(respuesta)

        if not isinstance(contenido, dict):
            raise RuntimeError(
                "Pexels devolvió una respuesta inválida."
            )

        return contenido

    def buscar_imagenes(
        self,
        consulta: str,
        cantidad: int = 20,
    ) -> list[dict[str, Any]]:
        """Busca fotografías horizontales."""
        contenido = self._solicitar(
            endpoint=PEXELS_PHOTO_API_URL,
            parametros={
                "query": consulta,
                "orientation": "landscape",
                "size": "large",
                "locale": "en-US",
                "per_page": max(
                    1,
                    min(cantidad, 80),
                ),
            },
        )

        resultados: list[dict[str, Any]] = []

        for foto in contenido.get("photos", []):
            if not isinstance(foto, dict):
                continue

            fuentes = foto.get("src", {})

            if not isinstance(fuentes, dict):
                continue

            url = (
                fuentes.get("large2x")
                or fuentes.get("large")
                or fuentes.get("original")
            )

            if not url:
                continue

            ancho = int(foto.get("width", 0) or 0)
            alto = int(foto.get("height", 0) or 0)

            if ancho <= alto:
                continue

            resultados.append(
                {
                    "id": int(foto.get("id", 0)),
                    "largeImageURL": str(url),
                    "webformatURL": str(url),
                    "imageWidth": ancho,
                    "imageHeight": alto,
                    "pageURL": str(
                        foto.get("url", "")
                    ),
                    "user": str(
                        foto.get(
                            "photographer",
                            "Pexels",
                        )
                    ),
                    "user_id": foto.get(
                        "photographer_id",
                        0,
                    ),
                    "tags": str(
                        foto.get("alt", "")
                    ),
                    "descripcion_original": str(
                        foto.get("alt", "")
                    ),
                    "extension": ".jpg",
                    "licencia": "Pexels License",
                    "licencia_url": (
                        "https://www.pexels.com/license/"
                    ),
                    "credito": (
                        f"Foto de "
                        f"{foto.get('photographer', 'Pexels')} "
                        f"en Pexels"
                    ),
                }
            )

        return resultados

    def buscar_videos(
        self,
        consulta: str,
        cantidad: int = 15,
    ) -> list[dict[str, Any]]:
        """Busca videos horizontales."""
        contenido = self._solicitar(
            endpoint=PEXELS_VIDEO_API_URL,
            parametros={
                "query": consulta,
                "orientation": "landscape",
                "size": "medium",
                "locale": "en-US",
                "per_page": max(
                    1,
                    min(cantidad, 80),
                ),
            },
        )

        resultados: list[dict[str, Any]] = []

        for video in contenido.get("videos", []):
            if not isinstance(video, dict):
                continue

            archivos = video.get(
                "video_files",
                [],
            )

            if not isinstance(archivos, list):
                continue

            compatibles = [
                archivo
                for archivo in archivos
                if (
                    isinstance(archivo, dict)
                    and archivo.get("link")
                    and archivo.get("file_type")
                    == "video/mp4"
                    and int(
                        archivo.get("width", 0) or 0
                    )
                    >= int(
                        archivo.get("height", 0) or 0
                    )
                )
            ]

            if not compatibles:
                continue

            compatibles.sort(
                key=lambda archivo: abs(
                    int(archivo.get("width", 0) or 0)
                    - 1920
                )
            )

            archivo = compatibles[0]
            autor = video.get("user", {})

            if not isinstance(autor, dict):
                autor = {}

            resultados.append(
                {
                    "id": int(video.get("id", 0)),
                    "url": str(
                        archivo.get("link", "")
                    ),
                    "width": int(
                        archivo.get("width", 0) or 0
                    ),
                    "height": int(
                        archivo.get("height", 0) or 0
                    ),
                    "size": int(
                        archivo.get("file_size", 0) or 0
                    ),
                    "duration": int(
                        video.get("duration", 0) or 0
                    ),
                    "pageURL": str(
                        video.get("url", "")
                    ),
                    "user": str(
                        autor.get("name", "Pexels")
                    ),
                    "user_id": autor.get("id", 0),
                    "tags": consulta,
                    "extension": ".mp4",
                    "licencia": "Pexels License",
                    "licencia_url": (
                        "https://www.pexels.com/license/"
                    ),
                }
            )

        return resultados

    def descargar(
        self,
        url: str,
        destino: Path,
    ) -> None:
        """Descarga un archivo sin exponer la clave."""
        destino.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporal = destino.with_suffix(
            destino.suffix + ".part"
        )

        solicitud = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AutoTubeIA/1.0",
            },
        )

        try:
            with urllib.request.urlopen(
                solicitud,
                timeout=90,
            ) as respuesta:
                with temporal.open("wb") as archivo:
                    while True:
                        bloque = respuesta.read(
                            1024 * 1024
                        )

                        if not bloque:
                            break

                        archivo.write(bloque)

            if (
                not temporal.is_file()
                or temporal.stat().st_size == 0
            ):
                raise RuntimeError(
                    "Pexels devolvió un archivo vacío."
                )

            temporal.replace(destino)

        finally:
            if temporal.exists():
                temporal.unlink()
