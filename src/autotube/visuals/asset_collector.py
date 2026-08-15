from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


PIXABAY_API_URL = "https://pixabay.com/api/"
PIXABAY_VIDEO_API_URL = "https://pixabay.com/api/videos/"
CACHE_SEGUNDOS = 24 * 60 * 60

TIPOS_PIXABAY = {
    "video_stock",
    "imagen_stock",
}


def localizar_plan_visual(
    data_dir: Path,
    archivo: Path | None = None,
) -> Path:
    """Localiza el plan visual indicado o el más reciente."""
    if archivo is not None:
        ruta = archivo.expanduser().resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe el plan visual indicado: {ruta}"
            )

        return ruta

    archivos = sorted(
        (data_dir / "visual_plans").glob(
            "plan_visual_*.json"
        ),
        key=lambda elemento: elemento.stat().st_mtime,
        reverse=True,
    )

    if not archivos:
        raise FileNotFoundError(
            "No se encontró ningún plan visual."
        )

    return archivos[0]


def cargar_plan_visual(
    data_dir: Path,
    archivo: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Carga un plan visual válido."""
    ruta = localizar_plan_visual(
        data_dir=data_dir,
        archivo=archivo,
    )

    contenido = json.loads(
        ruta.read_text(encoding="utf-8")
    )

    plan = contenido.get("plan_visual")

    if not isinstance(plan, dict):
        raise RuntimeError(
            "El archivo no contiene un plan visual válido."
        )

    segmentos = plan.get("segmentos")

    if not isinstance(segmentos, list) or not segmentos:
        raise RuntimeError(
            "El plan visual no contiene segmentos."
        )

    return contenido, ruta


def limpiar_consulta(texto: str) -> str:
    """Prepara una consulta breve para Pixabay."""
    texto = re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()

    palabras = texto.split()

    return " ".join(palabras[:12])[:100]


def nombre_seguro(texto: str) -> str:
    """Crea un nombre seguro para carpetas."""
    texto = texto.lower().strip()

    texto = re.sub(
        r"[^\w\s-]",
        "",
        texto,
        flags=re.UNICODE,
    )

    texto = re.sub(
        r"[\s_-]+",
        "_",
        texto,
    )

    return texto.strip("_")[:45] or "segmento"


class ClientePixabay:
    """Cliente de Pixabay con caché local de 24 horas."""

    def __init__(
        self,
        cache_dir: Path,
        api_key: str | None = None,
        timeout: int = 45,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("PIXABAY_API_KEY")
            or ""
        ).strip()

        if not self.api_key:
            raise RuntimeError(
                "PIXABAY_API_KEY está vacía en el archivo .env."
            )

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.timeout = timeout

    def _ruta_cache(
        self,
        tipo: str,
        consulta: str,
        cantidad: int,
    ) -> Path:
        contenido = (
            f"{tipo}|{consulta.lower()}|{cantidad}"
        )

        identificador = hashlib.sha256(
            contenido.encode("utf-8")
        ).hexdigest()

        return (
            self.cache_dir
            / f"{tipo}_{identificador}.json"
        )

    def _leer_cache(
        self,
        ruta: Path,
    ) -> dict[str, Any] | None:
        if not ruta.is_file():
            return None

        antiguedad = (
            time.time()
            - ruta.stat().st_mtime
        )

        if antiguedad > CACHE_SEGUNDOS:
            return None

        try:
            return json.loads(
                ruta.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return None

    def _solicitar(
        self,
        tipo: str,
        endpoint: str,
        parametros: dict[str, Any],
        consulta: str,
        cantidad: int,
    ) -> dict[str, Any]:
        ruta_cache = self._ruta_cache(
            tipo=tipo,
            consulta=consulta,
            cantidad=cantidad,
        )

        cache = self._leer_cache(
            ruta_cache
        )

        if cache is not None:
            return cache

        parametros_finales = {
            "key": self.api_key,
            **parametros,
        }

        url = (
            endpoint
            + "?"
            + urllib.parse.urlencode(
                parametros_finales
            )
        )

        solicitud = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AutoTubeAI/0.1",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                solicitud,
                timeout=self.timeout,
            ) as respuesta:
                datos = json.load(respuesta)

        except urllib.error.HTTPError as error:
            mensaje = error.read().decode(
                "utf-8",
                errors="replace",
            )

            raise RuntimeError(
                f"Pixabay respondió HTTP {error.code}: "
                f"{mensaje[:500]}"
            ) from error

        except urllib.error.URLError as error:
            raise RuntimeError(
                f"No fue posible conectar con Pixabay: "
                f"{error.reason}"
            ) from error

        ruta_cache.write_text(
            json.dumps(
                datos,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return datos

    def buscar_videos(
        self,
        consulta: str,
        cantidad: int = 20,
    ) -> list[dict[str, Any]]:
        consulta = limpiar_consulta(
            consulta
        )

        if not consulta:
            return []

        datos = self._solicitar(
            tipo="videos",
            endpoint=PIXABAY_VIDEO_API_URL,
            parametros={
                "q": consulta,
                "lang": "en",
                "safesearch": "true",
                "order": "popular",
                "per_page": cantidad,
            },
            consulta=consulta,
            cantidad=cantidad,
        )

        resultados = datos.get("hits", [])

        return (
            resultados
            if isinstance(resultados, list)
            else []
        )

    def buscar_imagenes(
        self,
        consulta: str,
        cantidad: int = 20,
    ) -> list[dict[str, Any]]:
        consulta = limpiar_consulta(
            consulta
        )

        if not consulta:
            return []

        datos = self._solicitar(
            tipo="imagenes",
            endpoint=PIXABAY_API_URL,
            parametros={
                "q": consulta,
                "lang": "en",
                "image_type": "photo",
                "orientation": "horizontal",
                "min_width": 1280,
                "min_height": 720,
                "safesearch": "true",
                "order": "popular",
                "per_page": cantidad,
            },
            consulta=consulta,
            cantidad=cantidad,
        )

        resultados = datos.get("hits", [])

        return (
            resultados
            if isinstance(resultados, list)
            else []
        )

    def descargar(
        self,
        url: str,
        destino: Path,
    ) -> None:
        """Descarga un archivo de forma segura."""
        destino.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporal = destino.with_suffix(
            destino.suffix + ".part"
        )

        temporal.unlink(
            missing_ok=True
        )

        solicitud = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AutoTubeAI/0.1",
            },
        )

        try:
            with urllib.request.urlopen(
                solicitud,
                timeout=120,
            ) as respuesta:
                with temporal.open("wb") as archivo:
                    while True:
                        bloque = respuesta.read(
                            1024 * 1024
                        )

                        if not bloque:
                            break

                        archivo.write(bloque)

        except Exception:
            temporal.unlink(
                missing_ok=True
            )
            raise

        if (
            not temporal.is_file()
            or temporal.stat().st_size == 0
        ):
            temporal.unlink(
                missing_ok=True
            )

            raise RuntimeError(
                "Pixabay devolvió un archivo vacío."
            )

        temporal.replace(destino)


class RecolectorRecursos:
    """Descarga los recursos de stock de un plan visual."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
    ) -> None:
        self.data_dir = data_dir
        self.output_dir = output_dir

        self.cliente = ClientePixabay(
            cache_dir=(
                data_dir
                / "cache"
                / "pixabay"
            )
        )

        self.recursos_usados: set[
            tuple[str, int]
        ] = set()

    def _consultas_clip(
        self,
        clip: dict[str, Any],
    ) -> list[str]:
        valores = [
            str(
                clip.get(
                    "busqueda_en",
                    "",
                )
            ),
            str(
                clip.get(
                    "busqueda_es",
                    "",
                )
            ),
            str(
                clip.get(
                    "descripcion",
                    "",
                )
            ),
        ]

        consultas: list[str] = []

        for valor in valores:
            consulta = limpiar_consulta(
                valor
            )

            if (
                consulta
                and consulta.lower()
                not in {
                    item.lower()
                    for item in consultas
                }
            ):
                consultas.append(
                    consulta
                )

        return consultas

    def _seleccionar_video(
        self,
        resultados: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        for resultado in resultados:
            try:
                identificador = int(
                    resultado.get("id")
                )
            except (TypeError, ValueError):
                continue

            clave = (
                "video",
                identificador,
            )

            if clave in self.recursos_usados:
                continue

            videos = resultado.get(
                "videos",
                {},
            )

            if not isinstance(videos, dict):
                continue

            variante_elegida = None

            for nombre_variante in (
                "medium",
                "small",
                "large",
                "tiny",
            ):
                variante = videos.get(
                    nombre_variante
                )

                if (
                    isinstance(variante, dict)
                    and variante.get("url")
                ):
                    variante_elegida = {
                        "calidad": nombre_variante,
                        **variante,
                    }
                    break

            if variante_elegida is None:
                continue

            self.recursos_usados.add(
                clave
            )

            return {
                "id": identificador,
                "url": variante_elegida["url"],
                "ancho": variante_elegida.get(
                    "width",
                    0,
                ),
                "alto": variante_elegida.get(
                    "height",
                    0,
                ),
                "tamano_bytes": variante_elegida.get(
                    "size",
                    0,
                ),
                "calidad": variante_elegida.get(
                    "calidad",
                    "",
                ),
                "duracion_original": resultado.get(
                    "duration",
                    0,
                ),
                "pagina": resultado.get(
                    "pageURL",
                    "",
                ),
                "autor": resultado.get(
                    "user",
                    "",
                ),
                "autor_id": resultado.get(
                    "user_id",
                    0,
                ),
                "etiquetas": resultado.get(
                    "tags",
                    "",
                ),
            }

        return None

    def _seleccionar_imagen(
        self,
        resultados: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        for resultado in resultados:
            try:
                identificador = int(
                    resultado.get("id")
                )
            except (TypeError, ValueError):
                continue

            clave = (
                "imagen",
                identificador,
            )

            if clave in self.recursos_usados:
                continue

            url = (
                resultado.get("largeImageURL")
                or resultado.get("webformatURL")
            )

            if not url:
                continue

            self.recursos_usados.add(
                clave
            )

            return {
                "id": identificador,
                "url": url,
                "ancho": resultado.get(
                    "imageWidth",
                    resultado.get(
                        "webformatWidth",
                        0,
                    ),
                ),
                "alto": resultado.get(
                    "imageHeight",
                    resultado.get(
                        "webformatHeight",
                        0,
                    ),
                ),
                "pagina": resultado.get(
                    "pageURL",
                    "",
                ),
                "autor": resultado.get(
                    "user",
                    "",
                ),
                "autor_id": resultado.get(
                    "user_id",
                    0,
                ),
                "etiquetas": resultado.get(
                    "tags",
                    "",
                ),
            }

        return None

    def buscar_recurso(
        self,
        tipo: str,
        clip: dict[str, Any],
    ) -> tuple[
        dict[str, Any] | None,
        str,
    ]:
        """Busca un recurso usando varias consultas."""
        consultas = self._consultas_clip(
            clip
        )

        for consulta in consultas:
            if tipo == "video_stock":
                resultados = (
                    self.cliente.buscar_videos(
                        consulta=consulta,
                    )
                )

                recurso = self._seleccionar_video(
                    resultados
                )

            else:
                resultados = (
                    self.cliente.buscar_imagenes(
                        consulta=consulta,
                    )
                )

                recurso = self._seleccionar_imagen(
                    resultados
                )

            if recurso is not None:
                return recurso, consulta

        return None, ""

    def recolectar(
        self,
        contenido_plan: dict[str, Any],
        ruta_plan: Path,
        limite: int = 6,
    ) -> dict[str, Any]:
        """Descarga recursos del plan visual."""
        plan = contenido_plan["plan_visual"]
        segmentos = plan["segmentos"]

        marca_tiempo = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        carpeta_salida = (
            self.output_dir
            / "assets"
            / f"coleccion_{marca_tiempo}"
        )

        carpeta_salida.mkdir(
            parents=True,
            exist_ok=True,
        )

        elementos: list[dict[str, Any]] = []

        descargados = 0
        pendientes = 0
        omitidos = 0
        errores = 0

        for indice_segmento, segmento in enumerate(
            segmentos,
            start=1,
        ):
            if not isinstance(segmento, dict):
                continue

            titulo_segmento = str(
                segmento.get(
                    "titulo",
                    f"Segmento {indice_segmento}",
                )
            )

            carpeta_segmento = (
                carpeta_salida
                / (
                    f"{indice_segmento:02d}_"
                    f"{nombre_seguro(titulo_segmento)}"
                )
            )

            clips = segmento.get(
                "clips",
                [],
            )

            if not isinstance(clips, list):
                continue

            for posicion_clip, clip in enumerate(
                clips,
                start=1,
            ):
                if not isinstance(clip, dict):
                    continue

                tipo = str(
                    clip.get(
                        "tipo_recurso",
                        "",
                    )
                )

                base = {
                    "segmento_indice": indice_segmento,
                    "segmento_numero": segmento.get(
                        "numero",
                        indice_segmento,
                    ),
                    "segmento_titulo": titulo_segmento,
                    "clip_orden": clip.get(
                        "orden",
                        posicion_clip,
                    ),
                    "tipo_recurso": tipo,
                    "duracion_objetivo_segundos": clip.get(
                        "duracion_segundos",
                        0,
                    ),
                    "descripcion": clip.get(
                        "descripcion",
                        "",
                    ),
                    "movimiento": clip.get(
                        "movimiento",
                        "",
                    ),
                    "texto_pantalla": clip.get(
                        "texto_pantalla",
                        "",
                    ),
                    "texto_narrado": clip.get(
                        "texto_narrado",
                        "",
                    ),
                    "inicio_segundos": clip.get(
                        "inicio_segundos",
                        0,
                    ),
                    "final_segundos": clip.get(
                        "final_segundos",
                        0,
                    ),
                    "plataforma": clip.get(
                        "plataforma",
                        "",
                    ),
                    "url_oficial": clip.get(
                        "url_oficial",
                        "",
                    ),
                    "pantalla_objetivo": clip.get(
                        "pantalla_objetivo",
                        "",
                    ),
                    "accion_visual": clip.get(
                        "accion_visual",
                        "",
                    ),
                    "requiere_login": clip.get(
                        "requiere_login",
                        False,
                    ),
                }

                if tipo not in TIPOS_PIXABAY:
                    pendientes += 1

                    elementos.append(
                        {
                            **base,
                            "estado": "pendiente_generacion",
                            "motivo": (
                                "Este tipo se generará localmente "
                                "en el módulo gráfico."
                            ),
                        }
                    )

                    continue

                if limite > 0 and descargados >= limite:
                    omitidos += 1

                    elementos.append(
                        {
                            **base,
                            "estado": "omitido_por_limite",
                        }
                    )

                    continue

                print(
                    f"Buscando recurso "
                    f"{descargados + 1}"
                    f"{f'/{limite}' if limite > 0 else ''}: "
                    f"{titulo_segmento}"
                )

                try:
                    recurso, consulta = self.buscar_recurso(
                        tipo=tipo,
                        clip=clip,
                    )

                    if recurso is None:
                        raise RuntimeError(
                            "No se encontró un resultado adecuado."
                        )

                    extension = (
                        ".mp4"
                        if tipo == "video_stock"
                        else ".jpg"
                    )

                    nombre_archivo = (
                        f"clip_{posicion_clip:02d}_"
                        f"pixabay_{recurso['id']}"
                        f"{extension}"
                    )

                    destino = (
                        carpeta_segmento
                        / nombre_archivo
                    )

                    self.cliente.descargar(
                        url=str(recurso["url"]),
                        destino=destino,
                    )

                    descargados += 1

                    elementos.append(
                        {
                            **base,
                            "estado": "descargado",
                            "fuente": "pixabay",
                            "consulta": consulta,
                            "archivo": str(
                                destino.resolve()
                            ),
                            "pixabay": {
                                clave: valor
                                for clave, valor
                                in recurso.items()
                                if clave != "url"
                            },
                        }
                    )

                    print(
                        f"  OK: {nombre_archivo}"
                    )

                    time.sleep(0.25)

                except Exception as error:
                    errores += 1

                    elementos.append(
                        {
                            **base,
                            "estado": "error",
                            "error": str(error),
                        }
                    )

                    print(
                        f"  ERROR: {error}"
                    )

        manifiesto = {
            "generado_en": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "titulo": plan.get(
                "titulo",
                "Sin título",
            ),
            "plan_visual_origen": str(
                ruta_plan.resolve()
            ),
            "carpeta_recursos": str(
                carpeta_salida.resolve()
            ),
            "resumen": {
                "descargados": descargados,
                "pendientes_generacion": pendientes,
                "omitidos_por_limite": omitidos,
                "errores": errores,
                "total_elementos": len(elementos),
            },
            "elementos": elementos,
        }

        ruta_manifiesto = (
            carpeta_salida
            / "assets_manifest.json"
        )

        ruta_manifiesto.write_text(
            json.dumps(
                manifiesto,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "carpeta": carpeta_salida,
            "manifiesto": ruta_manifiesto,
            "resumen": manifiesto["resumen"],
        }