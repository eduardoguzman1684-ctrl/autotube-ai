from __future__ import annotations

import hashlib
import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


OPENVERSE_API_URL = "https://api.openverse.org/v1/images/"
CACHE_SEGUNDOS = 24 * 60 * 60
LICENCIAS_PERMITIDAS = frozenset({"pdm", "cc0", "by"})
FORMATOS_PERMITIDOS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class ClienteOpenverse:
    """Busca imágenes abiertas y conserva su atribución completa."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": (
                "AutoTubeAI/10.0 "
                "(documentales educativos; cliente Openverse)"
            ),
            "Accept": "application/json",
        }

    def _ruta_cache(self, consulta: str, cantidad: int) -> Path:
        huella = hashlib.sha256(
            f"{consulta}|{cantidad}|pdm,cc0,by".encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{huella}.json"

    @staticmethod
    def _identificador_estable(valor: str) -> int:
        huella = hashlib.sha256(valor.encode("utf-8")).hexdigest()
        return int(huella[:15], 16)

    @staticmethod
    def _extension(resultado: dict[str, Any], url: str) -> str:
        tipo = str(resultado.get("filetype") or "").lower().strip()
        if tipo:
            if not tipo.startswith("image/"):
                tipo = f"image/{tipo.removeprefix('.')}"
            if tipo in FORMATOS_PERMITIDOS:
                return FORMATOS_PERMITIDOS[tipo]

        extension = Path(
            urllib.parse.urlsplit(url).path
        ).suffix.lower()
        if extension == ".jpeg":
            extension = ".jpg"
        if extension in {".jpg", ".png", ".webp"}:
            return extension

        tipo_estimado, _ = mimetypes.guess_type(url)
        return FORMATOS_PERMITIDOS.get(str(tipo_estimado), "")

    def _solicitar(
        self,
        consulta: str,
        cantidad: int,
    ) -> dict[str, Any]:
        ruta_cache = self._ruta_cache(consulta, cantidad)
        if ruta_cache.is_file():
            antiguedad = time.time() - ruta_cache.stat().st_mtime
            if antiguedad < CACHE_SEGUNDOS:
                try:
                    datos = json.loads(
                        ruta_cache.read_text(encoding="utf-8")
                    )
                    if isinstance(datos, dict):
                        return datos
                except (OSError, json.JSONDecodeError):
                    ruta_cache.unlink(missing_ok=True)

        parametros = {
            "q": consulta,
            "page_size": max(1, min(cantidad, 20)),
            "license": "pdm,cc0,by",
            "mature": "false",
        }
        url = OPENVERSE_API_URL + "?" + urllib.parse.urlencode(parametros)
        ultimo_error: Exception | None = None

        for intento in range(1, 5):
            solicitud = urllib.request.Request(url, headers=self.headers)
            try:
                with urllib.request.urlopen(
                    solicitud,
                    timeout=45,
                ) as respuesta:
                    datos = json.loads(
                        respuesta.read().decode("utf-8")
                    )
                if not isinstance(datos, dict):
                    raise RuntimeError(
                        "Openverse devolvió una respuesta inválida."
                    )
                ruta_cache.write_text(
                    json.dumps(datos, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return datos
            except urllib.error.HTTPError as error:
                ultimo_error = error
                if error.code not in {429, 500, 502, 503, 504}:
                    raise
            except (
                urllib.error.URLError,
                TimeoutError,
                ConnectionError,
                json.JSONDecodeError,
            ) as error:
                ultimo_error = error

            if intento < 4:
                time.sleep(2 ** (intento - 1))

        raise RuntimeError(
            "Openverse no respondió después de cuatro intentos: "
            f"{ultimo_error}"
        )

    def buscar_imagenes(
        self,
        consulta: str,
        cantidad: int = 20,
    ) -> list[dict[str, Any]]:
        consulta = str(consulta).strip()
        if not consulta:
            return []

        datos = self._solicitar(consulta, cantidad)
        resultados_raw = datos.get("results", [])
        if not isinstance(resultados_raw, list):
            return []

        resultados: list[dict[str, Any]] = []
        for resultado in resultados_raw:
            if not isinstance(resultado, dict):
                continue

            licencia = str(resultado.get("license") or "").lower().strip()
            if licencia not in LICENCIAS_PERMITIDAS:
                continue
            if bool(resultado.get("mature", False)):
                continue

            try:
                ancho = int(resultado.get("width") or 0)
                alto = int(resultado.get("height") or 0)
            except (TypeError, ValueError):
                continue
            if ancho < 1000 or alto < 600 or ancho <= alto:
                continue

            url = str(resultado.get("url") or "").strip()
            if not url.startswith(("https://", "http://")):
                continue
            extension = self._extension(resultado, url)
            if not extension:
                continue

            original_id = str(resultado.get("id") or url)
            titulo = str(resultado.get("title") or "Imagen sin título").strip()
            autor_declarado = str(resultado.get("creator") or "").strip()
            autor = autor_declarado or "Autor no indicado"
            pagina = str(
                resultado.get("foreign_landing_url")
                or resultado.get("detail_url")
                or ""
            ).strip()
            licencia_url = str(resultado.get("license_url") or "").strip()
            atribucion = str(resultado.get("attribution") or "").strip()
            if licencia == "by" and (not licencia_url or not autor_declarado):
                continue

            etiquetas_raw = resultado.get("tags", [])
            etiquetas: list[str] = []
            if isinstance(etiquetas_raw, list):
                for etiqueta in etiquetas_raw:
                    if isinstance(etiqueta, dict):
                        nombre = str(etiqueta.get("name") or "").strip()
                    else:
                        nombre = str(etiqueta).strip()
                    if nombre:
                        etiquetas.append(nombre)

            if not atribucion:
                atribucion = (
                    f'"{titulo}" por {autor}; licencia {licencia.upper()}'
                )
                if licencia_url:
                    atribucion += f" ({licencia_url})"
                if pagina:
                    atribucion += f"; vía Openverse: {pagina}"

            resultados.append(
                {
                    "id": self._identificador_estable(original_id),
                    "openverse_id": original_id,
                    "largeImageURL": url,
                    "extension": extension,
                    "imageWidth": ancho,
                    "imageHeight": alto,
                    "pageURL": pagina,
                    "user": autor,
                    "user_id": 0,
                    "tags": ", ".join(etiquetas) or titulo,
                    "licencia": (
                        "CC BY" if licencia == "by" else licencia.upper()
                    ),
                    "licencia_url": licencia_url,
                    "credito": atribucion,
                    "descripcion_original": titulo,
                    "openverse_source": str(resultado.get("source") or ""),
                    "openverse_provider": str(resultado.get("provider") or ""),
                }
            )

        return resultados

    def descargar(self, url: str, destino: Path) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix(destino.suffix + ".part")
        temporal.unlink(missing_ok=True)
        ultimo_error: Exception | None = None

        for intento in range(1, 4):
            solicitud = urllib.request.Request(
                url,
                headers={
                    **self.headers,
                    "Accept": "image/jpeg,image/png,image/webp,*/*;q=0.5",
                },
            )
            try:
                with urllib.request.urlopen(
                    solicitud,
                    timeout=120,
                ) as respuesta:
                    tipo = str(
                        respuesta.headers.get("Content-Type", "")
                    ).split(";", 1)[0].lower()
                    if tipo and tipo not in FORMATOS_PERMITIDOS:
                        raise RuntimeError(
                            f"Openverse devolvió contenido no visual: {tipo}"
                        )
                    with temporal.open("wb") as archivo:
                        while True:
                            bloque = respuesta.read(1024 * 1024)
                            if not bloque:
                                break
                            archivo.write(bloque)

                if not temporal.is_file() or temporal.stat().st_size < 1024:
                    raise RuntimeError(
                        "Openverse devolvió un archivo vacío o incompleto."
                    )
                temporal.replace(destino)
                return
            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                TimeoutError,
                ConnectionError,
                RuntimeError,
            ) as error:
                ultimo_error = error
                temporal.unlink(missing_ok=True)
                if intento < 3:
                    time.sleep(2 * intento)

        raise RuntimeError(
            "No se pudo descargar el recurso de Openverse: "
            f"{ultimo_error}"
        )
