from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"
CACHE_SEGUNDOS = 24 * 60 * 60


def _limpiar_html(texto: str) -> str:
    return re.sub(r"<[^>]+>", "", texto or "").strip()


class ClienteWikimedia:
    """Busca y descarga imágenes de Wikimedia Commons."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.headers = {
            "User-Agent": (
                "NexonIA-AutoTube/1.0 "
                "(documentales educativos)"
            )
        }

    def _ruta_cache(self, consulta: str) -> Path:
        clave = hashlib.sha256(
            consulta.encode("utf-8")
        ).hexdigest()

        return self.cache_dir / f"{clave}.json"

    def _solicitar(
        self,
        consulta: str,
        cantidad: int = 20,
    ) -> dict[str, Any]:
        ruta_cache = self._ruta_cache(consulta)

        if ruta_cache.is_file():
            antiguedad = time.time() - ruta_cache.stat().st_mtime

            if antiguedad < CACHE_SEGUNDOS:
                return json.loads(
                    ruta_cache.read_text(encoding="utf-8")
                )

        parametros = {
            "action": "query",
            "generator": "search",
            "gsrsearch": consulta,
            "gsrnamespace": 6,
            "gsrlimit": max(1, min(cantidad, 30)),
            "prop": "imageinfo|info",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1920,
            "inprop": "url",
            "format": "json",
            "formatversion": 2,
            "origin": "*",
        }

        url = (
            WIKIMEDIA_API_URL
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
            contenido = json.loads(
                respuesta.read().decode("utf-8")
            )

        ruta_cache.write_text(
            json.dumps(
                contenido,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return contenido

    def buscar_imagenes(
        self,
        consulta: str,
        cantidad: int = 20,
    ) -> list[dict[str, Any]]:
        contenido = self._solicitar(
            consulta=consulta,
            cantidad=cantidad,
        )

        paginas = contenido.get(
            "query",
            {},
        ).get(
            "pages",
            [],
        )

        resultados: list[dict[str, Any]] = []

        for pagina in paginas:
            informacion = pagina.get("imageinfo", [])

            if not informacion:
                continue

            imagen = informacion[0]
            mime = str(imagen.get("mime", ""))
            ancho = int(imagen.get("width", 0) or 0)
            alto = int(imagen.get("height", 0) or 0)

            formatos_permitidos = {
                "image/jpeg",
                "image/png",
                "image/webp",
                "image/svg+xml",
            }

            if mime not in formatos_permitidos:
                continue

            es_svg = mime == "image/svg+xml"

            if (
                not es_svg
                and (
                    ancho < 1000
                    or alto < 600
                )
            ):
                continue

            if ancho <= alto:
                continue

            if es_svg:
                url = str(
                    imagen.get("thumburl", "")
                )
            else:
                url = str(
                    imagen.get("thumburl")
                    or imagen.get("url", "")
                )

            if not url:
                continue

            ancho_salida = int(
                imagen.get("thumbwidth", 0)
                or ancho
            )

            alto_salida = int(
                imagen.get("thumbheight", 0)
                or alto
            )

            metadatos = imagen.get("extmetadata", {})

            def valor(nombre: str) -> str:
                dato = metadatos.get(nombre, {})

                if not isinstance(dato, dict):
                    return ""

                return _limpiar_html(
                    str(dato.get("value", ""))
                )

            resultados.append(
                {
                    "id": int(pagina.get("pageid", 0)),
                    "largeImageURL": url,
                    "extension": {
                        "image/jpeg": ".jpg",
                        "image/png": ".png",
                        "image/webp": ".webp",
                        "image/svg+xml": ".png",
                    }.get(mime, ".jpg"),
                    "imageWidth": ancho_salida,
                    "imageHeight": alto_salida,
                    "pageURL": pagina.get(
                        "canonicalurl",
                        "",
                    ),
                    "user": (
                        valor("Artist")
                        or valor("Credit")
                        or "Wikimedia Commons"
                    ),
                    "user_id": 0,
                    "tags": str(
                        pagina.get("title", "")
                    ).removeprefix("File:"),
                    "licencia": valor("LicenseShortName"),
                    "licencia_url": valor("LicenseUrl"),
                    "credito": valor("Credit"),
                    "descripcion_original": valor(
                        "ImageDescription"
                    ),
                }
            )

        return resultados

    def descargar(
        self,
        url: str,
        destino: Path,
    ) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix(
            destino.suffix + ".part"
        )

        solicitud = urllib.request.Request(
            url,
            headers=self.headers,
        )

        try:
            with urllib.request.urlopen(
                solicitud,
                timeout=90,
            ) as respuesta:
                with temporal.open("wb") as archivo:
                    while True:
                        bloque = respuesta.read(1024 * 1024)

                        if not bloque:
                            break

                        archivo.write(bloque)

            if not temporal.is_file() or temporal.stat().st_size == 0:
                raise RuntimeError(
                    "Wikimedia devolvió un archivo vacío."
                )

            temporal.replace(destino)

        finally:
            if temporal.exists():
                temporal.unlink()
