from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import unicodedata

import httpx
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.visuals.wikimedia_client import ClienteWikimedia
from autotube.visuals.pexels_client import ClientePexels
from autotube.visuals.openverse_client import ClienteOpenverse
from autotube.visuals.visual_verifier import VerificadorVisualGemini
from autotube.visuals.local_clip_verifier import VerificadorVisualCLIP
from autotube.visuals.cloudflare_image_generator import (
    CuotaImagenIAAgotada,
    GeneradorImagenCloudflare,
)


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

        self.cliente_wikimedia = ClienteWikimedia(
            cache_dir=(
                data_dir
                / "cache"
                / "wikimedia"
            )
        )

        self.cliente_openverse = ClienteOpenverse(
            cache_dir=(
                data_dir
                / "cache"
                / "openverse"
            )
        )

        self.cliente_pexels = ClientePexels()

        self.verificador_visual = VerificadorVisualGemini(
            umbral=88,
        )

        self.verificador_visual_local = VerificadorVisualCLIP(
            umbral=self.verificador_visual.umbral,
        )

        self.detener_recoleccion = False
        self.motivo_detencion = ""

        self.modo_lote_activo = False
        self.selecciones_lote: dict[
            str,
            dict[str, Any] | None,
        ] = {}
        self.consultas_lote: dict[str, str] = {}

        self.recursos_usados: set[
            tuple[str, int]
        ] = set()

        self.generador_imagen_ia: (
            GeneradorImagenCloudflare | None
        ) = None

        self.recursos_aprobados_segmento: dict[
            int,
            list[dict[str, Any]],
        ] = {}
        self.recursos_historicos_por_titulo: dict[
            str,
            list[dict[str, Any]],
        ] = {}
        self.reutilizaciones_por_archivo: dict[str, int] = {}
        self.maximo_reutilizaciones = 2
        self.maximo_imagenes_ia = max(
            0,
            int(os.getenv("AUTOTUBE_MAX_AI_IMAGES", "8")),
        )
        self.cuota_imagen_ia_agotada = False

    def _clave_segmento(self, titulo: str) -> str:
        return nombre_seguro(titulo).lower()

    def _cargar_recursos_historicos(
        self,
        channel_slug: str,
        titulo_video: str,
    ) -> None:
        """Indexa imagenes aprobadas de ejecuciones anteriores del video."""
        self.recursos_historicos_por_titulo.clear()
        manifiestos = sorted(
            (self.output_dir / "assets").glob(
                "coleccion_*/assets_manifest.json"
            ),
            key=lambda ruta: ruta.stat().st_mtime,
            reverse=True,
        )[:12]

        vistos: set[str] = set()
        for manifiesto in manifiestos:
            try:
                datos = json.loads(
                    manifiesto.read_text(encoding="utf-8-sig")
                )
            except (OSError, ValueError, TypeError):
                continue

            if str(datos.get("channel_slug", "")) != channel_slug:
                continue
            if str(datos.get("titulo", "")).strip() != titulo_video.strip():
                continue

            elementos = datos.get("elementos", [])
            if not isinstance(elementos, list):
                continue

            for elemento in elementos:
                if not isinstance(elemento, dict):
                    continue
                if str(elemento.get("estado", "")) != "descargado":
                    continue

                archivo = Path(str(elemento.get("archivo", "")))
                if (
                    not archivo.is_file()
                    or archivo.suffix.lower()
                    not in {".jpg", ".jpeg", ".png", ".webp"}
                ):
                    continue

                identidad = str(archivo.resolve()).lower()
                if identidad in vistos:
                    continue
                vistos.add(identidad)

                titulo_segmento = str(
                    elemento.get("segmento_titulo", "")
                )
                clave = self._clave_segmento(titulo_segmento)
                if not clave:
                    continue

                self.recursos_historicos_por_titulo.setdefault(
                    clave,
                    [],
                ).append(
                    {
                        "archivo": archivo,
                        "fuente": str(elemento.get("fuente", "historico")),
                        "historico": True,
                        "manifiesto": manifiesto,
                    }
                )

    def _registrar_recurso_reutilizable(
        self,
        segmento_indice: int,
        archivo: Path,
        fuente: str,
    ) -> None:
        """Conserva imagenes aprobadas del segmento para usos cercanos."""
        if archivo.suffix.lower() not in {
            ".jpg", ".jpeg", ".png", ".webp",
        }:
            return

        self.recursos_aprobados_segmento.setdefault(
            segmento_indice,
            [],
        ).append(
            {
                "archivo": archivo,
                "fuente": fuente,
            }
        )

    def _reutilizar_recurso_aprobado(
        self,
        clip: dict[str, Any],
        segmento_indice: int,
        titulo_segmento: str,
        carpeta_segmento: Path,
        posicion_clip: int,
    ) -> tuple[Path, dict[str, Any]] | None:
        """Reutiliza solo una imagen del mismo segmento aprobada por CLIP."""
        candidatos_actuales = self.recursos_aprobados_segmento.get(
            segmento_indice,
            [],
        )
        candidatos_historicos = self.recursos_historicos_por_titulo.get(
            self._clave_segmento(titulo_segmento),
            [],
        )[:24]
        candidatos = []
        for registro in [*candidatos_actuales, *candidatos_historicos]:
            archivo = Path(registro["archivo"])
            usos = self.reutilizaciones_por_archivo.get(str(archivo), 0)
            limite_usos = (
                1 if bool(registro.get("historico", False))
                else self.maximo_reutilizaciones
            )
            if archivo.is_file() and usos < limite_usos:
                candidatos.append(registro)

        if not candidatos:
            return None

        requisito = self._requisito_visual(clip)
        mejor: tuple[dict[str, Any], dict[str, Any]] | None = None

        for registro in candidatos:
            archivo = Path(registro["archivo"])
            verificacion = self.verificador_visual_local.seleccionar(
                imagenes=[archivo],
                requisito_visual=requisito,
            )
            if (
                bool(verificacion.get("aprobada", False))
                and int(verificacion.get("puntaje", 0)) >= 94
                and (
                    mejor is None
                    or int(verificacion.get("puntaje", 0))
                    > int(mejor[1].get("puntaje", 0))
                )
            ):
                mejor = (registro, verificacion)

        if mejor is None:
            return None

        registro, verificacion = mejor
        origen = Path(registro["archivo"])
        destino = carpeta_segmento / (
            f"clip_{posicion_clip:02d}_reutilizado_clip_local"
            f"{origen.suffix.lower()}"
        )
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
        self.reutilizaciones_por_archivo[str(origen)] = (
            self.reutilizaciones_por_archivo.get(str(origen), 0) + 1
        )

        return destino, {
            "fuente_original": str(registro["fuente"]),
            "archivo_original": str(origen.resolve()),
            "coleccion_historica": bool(
                registro.get("historico", False)
            ),
            "manifiesto_original": str(
                registro.get("manifiesto", "")
            ),
            "verificacion_visual": verificacion,
            "regla": (
                "Mismo segmento, pixeles verificados por CLIP, "
                "puntaje minimo 94 y maximo dos reutilizaciones."
            ),
        }

    def _completar_cobertura_segmentos(
        self,
        elementos: list[dict[str, Any]],
    ) -> int:
        """Cubre huecos con el recurso aprobado mas cercano del segmento."""
        estados_pendientes = {
            "pendiente_cuota_imagen_ia",
            "pendiente_sin_recurso",
        }
        disponibles_por_segmento: dict[int, list[dict[str, Any]]] = {}

        for elemento in elementos:
            if str(elemento.get("estado", "")) != "descargado":
                continue
            archivo = Path(str(elemento.get("archivo", "")))
            if not archivo.is_file():
                continue
            segmento = int(elemento.get("segmento_indice", 0) or 0)
            disponibles_por_segmento.setdefault(segmento, []).append(elemento)

        usos: dict[str, int] = {}
        completados = 0

        for elemento in elementos:
            estado_anterior = str(elemento.get("estado", ""))
            if estado_anterior not in estados_pendientes:
                continue

            segmento = int(elemento.get("segmento_indice", 0) or 0)
            orden = int(elemento.get("clip_orden", 0) or 0)
            candidatos = sorted(
                disponibles_por_segmento.get(segmento, []),
                key=lambda candidato: (
                    usos.get(str(candidato.get("archivo", "")), 0),
                    abs(int(candidato.get("clip_orden", 0) or 0) - orden),
                ),
            )
            candidato = next(
                (
                    opcion
                    for opcion in candidatos
                    if usos.get(str(opcion.get("archivo", "")), 0) < 3
                ),
                None,
            )
            if candidato is None:
                continue

            origen = Path(str(candidato["archivo"]))
            requisito = self._requisito_visual(elemento)
            lamina = (
                self.data_dir
                / "cache"
                / "verificacion_visual"
                / (
                    f"continuidad_s{segmento:02d}_"
                    f"c{orden:03d}.jpg"
                )
            )
            try:
                verificacion = self.verificador_visual.seleccionar(
                    imagenes=[origen],
                    requisito_visual=requisito,
                    lamina_temporal=lamina,
                )
            except Exception as error_remoto:
                try:
                    verificacion = self.verificador_visual_local.seleccionar(
                        imagenes=[origen],
                        requisito_visual=requisito,
                    )
                except Exception as error_local:
                    print(
                        "  COBERTURA RECHAZADA: no fue posible verificar "
                        f"segmento {segmento}, clip {orden}: "
                        f"{error_remoto}; {error_local}"
                    )
                    continue

            if (
                not bool(verificacion.get("aprobada", False))
                or int(verificacion.get("seleccion", 0)) != 1
                or int(verificacion.get("puntaje", 0)) < 94
                or not bool(verificacion.get("cumple_concepto", False))
                or not bool(verificacion.get("cumple_obligatorios", False))
                or bool(verificacion.get("viola_prohibidos", True))
            ):
                print(
                    "  COBERTURA RECHAZADA POR PIXELES: "
                    f"segmento {segmento}, clip {orden}; "
                    f"{verificacion.get('motivo', 'sin coincidencia directa')}"
                )
                continue

            carpeta = origen.parent
            destino = carpeta / (
                f"clip_{orden:02d}_continuidad_segmento{origen.suffix.lower()}"
            )
            shutil.copy2(origen, destino)
            usos[str(origen)] = usos.get(str(origen), 0) + 1

            elemento["estado"] = "descargado"
            elemento["fuente"] = "continuidad_segmento_aprobada"
            elemento["archivo"] = str(destino.resolve())
            elemento["continuidad_visual"] = {
                "estado_original": estado_anterior,
                "archivo_original": str(origen.resolve()),
                "fuente_original": str(candidato.get("fuente", "")),
                "segmento": segmento,
                "verificacion_visual": verificacion,
                "regla": (
                    "Recurso del mismo segmento aprobado nuevamente contra "
                    "el contrato visual exacto del clip y sus pixeles reales."
                ),
            }
            elemento.pop("motivo", None)
            completados += 1
            print(
                "  COBERTURA CONTEXTUAL: "
                f"segmento {segmento}, clip {orden}, origen {origen.name}"
            )

        return completados

    def _obtener_generador_imagen_ia(
        self,
    ) -> GeneradorImagenCloudflare:
        """Crea el cliente de Workers AI solo cuando hace falta."""
        if self.generador_imagen_ia is None:
            self.generador_imagen_ia = GeneradorImagenCloudflare(
                data_dir=self.data_dir,
            )

        return self.generador_imagen_ia

    def _generar_imagen_ia_verificada(
        self,
        clip: dict[str, Any],
        carpeta_segmento: Path,
        posicion_clip: int,
    ) -> tuple[Path, dict[str, Any]] | None:
        """Genera hasta tres candidatas y acepta solo una verificada."""
        generador = self._obtener_generador_imagen_ia()
        requisito = self._requisito_visual(clip)

        for variante in range(1, 4):
            destino = (
                carpeta_segmento
                / (
                    f"clip_{posicion_clip:02d}_"
                    f"cloudflare_v{variante}.jpg"
                )
            )

            print(
                "  Generando imagen documental con Workers AI "
                f"({variante}/3)..."
            )

            metadata = generador.generate(
                clip=clip,
                destination=destino,
                variant=variante,
            )

            lamina = (
                carpeta_segmento
                / (
                    f"verificacion_cloudflare_"
                    f"{posicion_clip:02d}_{variante}.jpg"
                )
            )

            try:
                verificacion = self.verificador_visual.seleccionar(
                    imagenes=[destino],
                    requisito_visual=requisito,
                    lamina_temporal=lamina,
                )

            except Exception as error:
                if self._registrar_error_fatal(error):
                    self.detener_recoleccion = False
                    self.motivo_detencion = ""

                print(
                    "  Gemini no pudo verificar la imagen IA; "
                    "se usara CLIP local."
                )

                verificacion = (
                    self.verificador_visual_local.seleccionar(
                        imagenes=[destino],
                        requisito_visual=requisito,
                        lamina_temporal=lamina,
                    )
                )

            if (
                int(verificacion.get("seleccion", 0)) == 0
                and verificacion.get("verificador") != "CLIP local"
            ):
                print(
                    "  Gemini rechazo la imagen IA; "
                    "CLIP local realizara una segunda revision."
                )

                verificacion_local = (
                    self.verificador_visual_local.seleccionar(
                        imagenes=[destino],
                        requisito_visual=requisito,
                        lamina_temporal=lamina,
                    )
                )

                if bool(verificacion_local.get("aprobada", False)):
                    verificacion = verificacion_local

            aprobada = (
                int(verificacion.get("seleccion", 0)) == 1
                and bool(verificacion.get("aprobada", False))
            )

            if aprobada:
                metadata["verificacion_visual"] = verificacion
                metadata["requisito_visual"] = requisito
                generador.confirm_cache(
                    source=destino,
                    fingerprint=str(metadata["prompt_sha256"]),
                )
                print(
                    "  IMAGEN IA APROBADA: "
                    f"{verificacion.get('puntaje', 0)}/100"
                )
                return destino, metadata

            print(
                "  IMAGEN IA RECHAZADA: no coincide "
                "estrictamente con la narracion."
            )
            destino.unlink(missing_ok=True)

        return None

    def _consultas_clip(
        self,
        clip: dict[str, Any],
    ) -> list[str]:
        alternativas_raw = clip.get(
            "consultas_alternativas",
            [],
        )

        alternativas = (
            [
                str(consulta)
                for consulta in alternativas_raw
                if str(consulta).strip()
            ]
            if isinstance(
                alternativas_raw,
                list,
            )
            else []
        )

        valores = [
            str(
                clip.get(
                    "busqueda_en",
                    "",
                )
            ),
            *alternativas,
            str(
                clip.get(
                    "busqueda_es",
                    "",
                )
            ),
            str(
                clip.get(
                    "concepto_central",
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

    def _evaluar_metadata_video(
        self,
        resultado: dict[str, Any],
        consulta: str,
    ) -> dict[str, Any]:
        """Valida el titulo autentico antes de descargar un video."""
        fuente = str(
            resultado.get(
                "_fuente",
                "pixabay",
            )
        ).lower()

        pagina = str(
            resultado.get(
                "pageURL",
                "",
            )
        )

        ruta_pagina = urllib.parse.unquote(
            urllib.parse.urlparse(
                pagina
            ).path
        ).replace(
            "-",
            " ",
        ).replace(
            "_",
            " ",
        )

        descripcion = str(
            resultado.get(
                "descripcion_original",
                "",
            )
        )

        etiquetas = str(
            resultado.get(
                "tags",
                "",
            )
        )

        partes_metadata = [
            ruta_pagina,
            descripcion,
        ]

        if (
            fuente != "pexels"
            and etiquetas.strip().lower()
            != consulta.strip().lower()
        ):
            partes_metadata.append(
                etiquetas
            )

        familias = {
            "research": {
                "research",
                "researcher",
                "researchers",
                "scientist",
                "scientists",
                "scientific",
            },
            "laboratory": {
                "lab",
                "labs",
                "laboratory",
                "laboratories",
            },
            "network": {
                "network",
                "networks",
            },
            "server": {
                "server",
                "servers",
            },
            "robot": {
                "robot",
                "robots",
                "robotic",
                "robotics",
            },
            "graph": {
                "graph",
                "graphs",
            },
            "processor": {
                "processor",
                "processors",
                "processing",
            },
        }

        equivalencias = {
            variante: familia
            for familia, variantes in familias.items()
            for variante in variantes
        }

        genericas = {
            "adult",
            "ai",
            "analyzing",
            "animation",
            "behavior",
            "business",
            "close",
            "closeup",
            "computer",
            "computers",
            "digital",
            "documentary",
            "footage",
            "future",
            "high",
            "intelligence",
            "image",
            "man",
            "modern",
            "monitor",
            "monitoring",
            "monitors",
            "people",
            "person",
            "photo",
            "professional",
            "screen",
            "screens",
            "stock",
            "technology",
            "video",
            "woman",
            "work",
            "working",
        }

        def claves(
            contenido: str,
        ) -> set[str]:
            return {
                equivalencias.get(
                    palabra,
                    palabra,
                )
                for palabra in self._palabras_tematicas(
                    contenido
                )
                if palabra not in genericas
                and not palabra.isdigit()
            }

        claves_consulta = claves(
            consulta
        )

        claves_metadata = claves(
            " ".join(
                partes_metadata
            )
        )

        coincidencias = sorted(
            claves_consulta
            & claves_metadata
        )

        minimo = (
            1
            if len(claves_consulta) <= 4
            else 2
        )

        aprobada = bool(
            claves_consulta
            and claves_metadata
            and len(coincidencias) >= minimo
        )

        puntaje = round(
            100
            * len(coincidencias)
            / max(
                1,
                len(claves_consulta),
            )
        )

        return {
            "aprobada": aprobada,
            "puntaje": min(
                100,
                puntaje,
            ),
            "coincidencias": coincidencias,
            "consulta": consulta,
            "pagina": pagina,
            "fuente": fuente,
            "motivo": (
                "La metadata autentica coincide."
                if aprobada
                else (
                    "El titulo autentico del video "
                    "no coincide suficientemente "
                    "con la consulta."
                )
            ),
        }

    def _seleccionar_video(
        self,
        resultados: list[dict[str, Any]],
        consulta: str = "",
    ) -> dict[str, Any] | None:
        for resultado in resultados:
            verificacion_metadata = (
                self._evaluar_metadata_video(
                    resultado=resultado,
                    consulta=consulta,
                )
            )

            if not verificacion_metadata[
                "aprobada"
            ]:
                print(
                    "  VIDEO RECHAZADO POR METADATA: "
                    f"{resultado.get('pageURL', '')}"
                )
                continue

            try:
                identificador = int(
                    resultado.get("id")
                )
            except (TypeError, ValueError):
                continue

            fuente_resultado = str(
                resultado.get(
                    "_fuente",
                    "pixabay",
                )
            )

            clave = (
                f"video_{fuente_resultado}",
                identificador,
            )

            if clave in self.recursos_usados:
                continue

            videos = resultado.get(
                "videos",
                {},
            )

            if (
                not videos
                and resultado.get("url")
            ):
                videos = {
                    "medium": {
                        "url": resultado.get("url"),
                        "width": resultado.get(
                            "width",
                            0,
                        ),
                        "height": resultado.get(
                            "height",
                            0,
                        ),
                        "size": resultado.get(
                            "size",
                            0,
                        ),
                    }
                }

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
                "extension": resultado.get(
                    "extension",
                    "",
                ),
                "licencia": resultado.get(
                    "licencia",
                    "",
                ),
                "licencia_url": resultado.get(
                    "licencia_url",
                    "",
                ),
                "credito": resultado.get(
                    "credito",
                    "",
                ),
                "descripcion_original": resultado.get(
                    "descripcion_original",
                    "",
                ),
                "verificacion_metadata": (
                    verificacion_metadata
                ),
            }

        return None

    def _palabras_tematicas(
        self,
        texto: str,
    ) -> list[str]:
        """Extrae palabras ?tiles para b?squedas y filtros."""
        normalizado = unicodedata.normalize(
            "NFKD",
            texto.lower(),
        )

        normalizado = "".join(
            caracter
            for caracter in normalizado
            if not unicodedata.combining(caracter)
        )

        palabras = re.findall(
            r"[a-z0-9]+",
            normalizado,
        )

        omitidas = {
            "a", "an", "and", "as", "at", "by",
            "close", "for", "from", "in", "into",
            "of", "on", "or", "the", "to", "up",
            "versus", "with",
            "analizando", "con", "de", "del",
            "en", "la", "las", "los", "para",
            "por", "una", "uno", "y",
            "adult", "behavior", "documentary", "footage",
            "image", "man", "people", "person", "photo",
            "real", "stock", "video", "woman",
        }

        resultado: list[str] = []

        for palabra in palabras:
            if (
                len(palabra) >= 3
                and palabra not in omitidas
                and palabra not in resultado
            ):
                resultado.append(palabra)

        return resultado

    def _consultas_stock_precisas(
        self,
        consultas_originales: list[str],
    ) -> list[str]:
        """Genera consultas breves para bancos visuales."""
        consultas: list[str] = []

        def agregar(consulta: str) -> None:
            consulta = limpiar_consulta(
                consulta
            )

            if (
                consulta
                and consulta.lower()
                not in {
                    existente.lower()
                    for existente in consultas
                }
            ):
                consultas.append(consulta)

        for original in consultas_originales:
            palabras = self._palabras_tematicas(
                original
            )

            conjunto = set(palabras)

            if (
                "deepfake" in conjunto
                or "deepfakes" in conjunto
            ):
                agregar("deepfake face comparison forensics")
                agregar("video manipulation forensic analysis")

            if (
                "authenticity" in conjunto
                or "autenticidad" in conjunto
                or "forensics" in conjunto
                or "forense" in conjunto
            ):
                agregar("digital forensics video authentication")
                agregar("media authenticity forensic analyst")

            if (
                "political" in conjunto
                or "politico" in conjunto
                or "election" in conjunto
                or "elecciones" in conjunto
            ):
                agregar("political press conference cameras")
                agregar("election speech news media")

            if (
                "fraud" in conjunto
                or "fraude" in conjunto
                or "scam" in conjunto
                or "estafa" in conjunto
            ):
                agregar("digital fraud investigation")
                agregar("phone banking scam investigation")

            if (
                "parliament" in conjunto
                or "parlamento" in conjunto
                or "lawmakers" in conjunto
                or "legisladores" in conjunto
            ):
                agregar("lawmakers technology regulation parliament")
                agregar("parliament debate press cameras")

            if (
                "videoconference" in conjunto
                or "videoconferencia" in conjunto
                or (
                    "video" in conjunto
                    and "conference" in conjunto
                )
            ):
                agregar("video conference face camera")
                agregar("webcam face tracking meeting")

            if "tensores" in conjunto or "matriz" in conjunto:
                agregar("tensor matrix visualization")
                agregar("numerical matrix heatmap")

            if "cartesiano" in conjunto and "multidimensional" in conjunto:
                agregar("vector space dimensions diagram")
                agregar("multidimensional coordinate system")

            if "watermark" in conjunto or "radiografia" in conjunto:
                agregar("chest x ray watermark")
                agregar("medical imaging shortcut learning")

            if "transformer" in conjunto and (
                "attention" in conjunto or "atencion" in conjunto
            ):
                agregar("multi head attention diagram")
                agregar("transformer attention mechanism diagram")

            if "gradcam" in conjunto or (
                "mapa" in conjunto and "calor" in conjunto
            ):
                agregar("Grad CAM heatmap")
                agregar("class activation map diagram")

            if "supervision" in conjunto and "humana" in conjunto:
                agregar("human in the loop diagram")
                agregar("human AI decision workflow")

            if "explicabilidad" in conjunto and "capacidad" in conjunto:
                agregar("explainability accuracy tradeoff")
                agregar("interpretable machine learning tradeoff")

            if "lineal" in conjunto and "complejos" in conjunto:
                agregar("linear regression nonlinear data")
                agregar("underfitting regression diagram")

            if "superordenador" in conjunto:
                agregar("supercomputer data center research")
                agregar("high performance computing laboratory")


            if (
                "submarine" in conjunto
                and "cable" in conjunto
            ):
                agregar("submarine cable landing station")
                agregar("fiber optic cable station coast")

            if (
                "thermal" in conjunto
                and (
                    "processor" in conjunto
                    or "cpu" in conjunto
                    or "chip" in conjunto
                )
            ):
                agregar("thermal camera computer processor")
                agregar("infrared electronics heat")

            if (
                "data" in conjunto
                and "center" in conjunto
                and (
                    "server" in conjunto
                    or "racks" in conjunto
                    or "aisle" in conjunto
                )
            ):
                agregar("data center server racks aisle")
                agregar("server room corridor")

            if (
                "immersion" in conjunto
                and "cooling" in conjunto
            ):
                agregar("immersion cooling servers")
                agregar("liquid cooled data center")

            if (
                "tokamak" in conjunto
                or (
                    "fusion" in conjunto
                    and "reactor" in conjunto
                )
            ):
                agregar("tokamak fusion reactor interior")
                agregar("nuclear fusion research facility")

            if (
                "photonic" in conjunto
                or "photonics" in conjunto
                or "fotonico" in conjunto
            ):
                agregar("photonic integrated circuit")
                agregar("silicon photonics chip")

            if (
                "hypercube" in conjunto
                or "tesseract" in conjunto
                or "hipercubo" in conjunto
            ):
                agregar(
                    "hypercube tesseract projection diagram"
                )
                agregar(
                    "four dimensional cube diagram"
                )

            if (
                "perceptron" in conjunto
                or "multilayer" in conjunto
                or (
                    "ocultas" in conjunto
                    and (
                        "neural" in conjunto
                        or "neuronal" in conjunto
                        or "network" in conjunto
                    )
                )
            ):
                agregar(
                    "multilayer perceptron neural network diagram"
                )
                agregar(
                    "input hidden output layers diagram"
                )

            if (
                "synaptic" in conjunto
                or "synapse" in conjunto
                or "sinapsis" in conjunto
                or "sinaptico" in conjunto
                or (
                    "weight" in conjunto
                    and "neuron" in conjunto
                )
                or (
                    "peso" in conjunto
                    and "neurona" in conjunto
                )
            ):
                agregar(
                    "artificial neuron model"
                )
                agregar(
                    "artificial neural network weights"
                )
                agregar(
                    "artificial neuron synaptic weights diagram"
                )
                agregar(
                    "neural connection weight arrow diagram"
                )

            if {"neural", "network"}.issubset(conjunto):
                agregar("neural network diagram")

            if {"machine", "learning"}.issubset(conjunto):
                agregar("machine learning diagram")

            if {"source", "code"}.issubset(conjunto):
                if "debugging" in conjunto:
                    agregar("source code debugging")

                agregar("source code programming")

            if {"vintage", "computer"}.issubset(conjunto):
                agregar("vintage computer")

            if (
                "researchers" in conjunto
                and "computer" in conjunto
            ):
                agregar("computer programmers office")
                agregar("software developers monitors")

            agregar(" ".join(palabras[:4]))
            agregar(" ".join(palabras[:3]))

            if len(palabras) >= 2:
                agregar(" ".join(palabras[-2:]))

        return consultas[:12]

    def _puntaje_textual_candidato(
        self,
        resultado: dict[str, Any],
        consulta: str,
    ) -> int:
        """Punt?a coincidencias entre candidato y consulta."""
        palabras_consulta = set(
            self._palabras_tematicas(
                consulta
            )
        )

        contenido = " ".join(
            [
                str(resultado.get("tags", "")),
                str(
                    resultado.get(
                        "descripcion_original",
                        "",
                    )
                ),
            ]
        )

        palabras_resultado = set(
            self._palabras_tematicas(
                contenido
            )
        )

        return len(
            palabras_consulta
            & palabras_resultado
        )

    def _convertir_candidato_imagen(
        self,
        resultado: dict[str, Any],
        fuente: str,
    ) -> dict[str, Any] | None:
        """Convierte un resultado sin marcarlo como utilizado."""
        try:
            identificador = int(
                resultado.get("id")
            )
        except (TypeError, ValueError):
            return None

        url = (
            resultado.get("largeImageURL")
            or resultado.get("webformatURL")
        )

        if not url:
            return None

        return {
            "id": identificador,
            "url": url,
            "_fuente": fuente,
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
            "extension": resultado.get(
                "extension",
                "",
            ),
            "licencia": resultado.get(
                "licencia",
                "",
            ),
            "licencia_url": resultado.get(
                "licencia_url",
                "",
            ),
            "credito": resultado.get(
                "credito",
                "",
            ),
            "descripcion_original": resultado.get(
                "descripcion_original",
                "",
            ),
        }

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
                "extension": resultado.get(
                    "extension",
                    "",
                ),
                "licencia": resultado.get(
                    "licencia",
                    "",
                ),
                "licencia_url": resultado.get(
                    "licencia_url",
                    "",
                ),
                "credito": resultado.get(
                    "credito",
                    "",
                ),
                "descripcion_original": resultado.get(
                    "descripcion_original",
                    "",
                ),
            }

        return None

    def _requisito_visual(
        self,
        clip: dict[str, Any],
    ) -> str:
        """Construye un contrato visual verificable para el clip."""
        concepto = str(
            clip.get(
                "concepto_central",
                "",
            )
            or clip.get(
                "descripcion",
                "",
            )
        ).strip()

        descripcion = str(
            clip.get(
                "descripcion",
                "",
            )
        ).strip()

        narracion = str(
            clip.get(
                "texto_narrado",
                "",
            )
        ).strip()

        criterios_raw = clip.get(
            "criterios_obligatorios",
            [],
        )

        prohibidos_raw = clip.get(
            "elementos_prohibidos",
            [],
        )

        alternativas_raw = clip.get(
            "consultas_alternativas",
            [],
        )

        criterios = (
            [
                str(valor).strip()
                for valor in criterios_raw
                if str(valor).strip()
            ]
            if isinstance(
                criterios_raw,
                list,
            )
            else []
        )

        prohibidos = (
            [
                str(valor).strip()
                for valor in prohibidos_raw
                if str(valor).strip()
            ]
            if isinstance(
                prohibidos_raw,
                list,
            )
            else []
        )

        alternativas = (
            [
                str(valor).strip()
                for valor in alternativas_raw
                if str(valor).strip()
            ]
            if isinstance(
                alternativas_raw,
                list,
            )
            else []
        )

        if not criterios and descripcion:
            criterios = [
                descripcion,
            ]

        secciones = [
            (
                "CONCEPTO CENTRAL: "
                + concepto
            ),
            (
                "DESCRIPCION OBJETIVO: "
                + descripcion
            ),
            "CRITERIOS OBLIGATORIOS:",
            *[
                "- " + criterio
                for criterio in criterios
            ],
            "ELEMENTOS PROHIBIDOS:",
            *[
                "- " + prohibido
                for prohibido in prohibidos
            ],
            (
                "CONTEXTO NARRADO: "
                + narracion[:600]
            ),
            "BUSQUEDAS ALTERNATIVAS:",
            *[
                "- " + alternativa
                for alternativa in alternativas
            ],
        ]

        return "\n".join(
            seccion
            for seccion in secciones
            if seccion.strip()
        )

    def _ruta_cache_selecciones(
        self,
        ruta_plan: Path,
    ) -> Path:
        """Obtiene una cach? vinculada al contenido del plan."""
        huella = hashlib.sha256(
            ruta_plan.read_bytes()
        ).hexdigest()[:16]

        carpeta = (
            self.data_dir
            / "cache"
            / "verificacion_visual"
        )

        carpeta.mkdir(
            parents=True,
            exist_ok=True,
        )

        return carpeta / f"selecciones_lote_{huella}.json"

    def _verificacion_cache_estricta(
        self,
        guardado: dict[str, Any],
    ) -> bool:
        """Impide reutilizar decisiones degradadas de versiones anteriores."""
        recurso = guardado.get("recurso")
        verificacion = guardado.get("verificacion")

        if not isinstance(recurso, dict):
            return False

        if not isinstance(verificacion, dict):
            return False

        return (
            int(verificacion.get("seleccion", 0)) > 0
            and int(verificacion.get("puntaje", 0))
            >= self.verificador_visual.umbral
            and bool(verificacion.get("aprobada", False))
            and bool(verificacion.get("cumple_concepto", False))
            and bool(verificacion.get("cumple_obligatorios", False))
            and not bool(verificacion.get("viola_prohibidos", True))
            and not bool(
                verificacion.get("verificacion_degradada", False)
            )
        )

    def _guardar_cache_selecciones(
        self,
        ruta_cache: Path,
        datos: dict[str, Any],
    ) -> None:
        """Guarda las decisiones de forma recuperable."""
        temporal = ruta_cache.with_suffix(".tmp")

        temporal.write_text(
            json.dumps(
                datos,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporal.replace(ruta_cache)

    def _obtener_candidatos_lote(
        self,
        clip: dict[str, Any],
        identificador: str,
    ) -> tuple[
        list[dict[str, Any]],
        list[Path],
        str,
    ]:
        """Re?ne cuatro candidatos usando consultas alternativas."""
        consultas_originales = self._consultas_clip(
            clip
        )

        if not consultas_originales:
            return [], [], ""

        consultas = self._consultas_stock_precisas(
            consultas_originales[:3]
        )

        carpeta = (
            self.data_dir
            / "cache"
            / "verificacion_visual"
            / "candidatos_lote"
            / identificador
        )

        carpeta.mkdir(
            parents=True,
            exist_ok=True,
        )

        recursos: list[dict[str, Any]] = []
        imagenes: list[Path] = []
        claves_vistas: set[tuple[str, int]] = set()
        conteo_fuente = {
            "pexels": 0,
            "wikimedia": 0,
            "pixabay": 0,
            "openverse": 0,
        }
        fuentes_bloqueadas: set[str] = set()
        consulta_principal = consultas[0]

        concepto_tecnico = any(
            termino in consulta_principal.lower()
            for termino in (
                "diagram",
                "architecture",
                "neural network",
                "machine learning",
                "deep learning",
                "flowchart",
                "model layers",
                "perceptron",
                "hypercube",
                "tesseract",
                "synaptic",
                "synapse",
                "artificial neuron",
                "neuron model",
                "neural network weights",
                "tensor matrix",
                "vector space",
                "chest x ray",
                "multi head attention",
                "transformer attention",
                "grad cam",
                "class activation",
                "human in the loop",
                "explainability accuracy",
                "linear regression",
            )
        )

        limites_fuente = (
            {
                "pexels": 1,
                "wikimedia": 1,
                "pixabay": 1,
                "openverse": 1,
            }
            if concepto_tecnico
            else {
                "pexels": 1,
                "wikimedia": 1,
                "pixabay": 1,
                "openverse": 1,
            }
        )

        for consulta in consultas:
            resultados_por_fuente: list[
                tuple[
                    str,
                    list[dict[str, Any]],
                    Any,
                ]
            ] = []

            try:
                resultados_pexels = (
                    self.cliente_pexels.buscar_imagenes(
                        consulta=consulta,
                    )
                )

                resultados_por_fuente.append(
                    (
                        "pexels",
                        resultados_pexels,
                        self.cliente_pexels,
                    )
                )

            except Exception as error:
                if self._registrar_error_fatal(error):
                    raise RuntimeError(
                        "DETENER_RECOLECCION: "
                        f"{error}"
                    ) from error

                print(
                    f"  AVISO Pexels: {error}"
                )

            try:
                resultados_wikimedia = (
                    self.cliente_wikimedia.buscar_imagenes(
                        consulta=consulta,
                    )
                )

                resultados_por_fuente.append(
                    (
                        "wikimedia",
                        resultados_wikimedia,
                        self.cliente_wikimedia,
                    )
                )

            except Exception as error:
                if self._registrar_error_fatal(error):
                    raise RuntimeError(
                        "DETENER_RECOLECCION: "
                        f"{error}"
                    ) from error

                print(
                    f"  AVISO Wikimedia: {error}"
                )

            try:
                resultados_pixabay = (
                    self.cliente.buscar_imagenes(
                        consulta=consulta,
                    )
                )

                resultados_por_fuente.append(
                    (
                        "pixabay",
                        resultados_pixabay,
                        self.cliente,
                    )
                )

            except Exception as error:
                if self._registrar_error_fatal(error):
                    raise RuntimeError(
                        "DETENER_RECOLECCION: "
                        f"{error}"
                    ) from error

                print(
                    f"  AVISO Pixabay: {error}"
                )

            try:
                resultados_openverse = (
                    self.cliente_openverse.buscar_imagenes(
                        consulta=consulta,
                    )
                )

                resultados_por_fuente.append(
                    (
                        "openverse",
                        resultados_openverse,
                        self.cliente_openverse,
                    )
                )

            except Exception as error:
                if self._registrar_error_fatal(error):
                    raise RuntimeError(
                        "DETENER_RECOLECCION: "
                        f"{error}"
                    ) from error

                print(
                    f"  AVISO Openverse: {error}"
                )

            for fuente, resultados, cliente in resultados_por_fuente:
                if fuente in fuentes_bloqueadas:
                    continue

                if conteo_fuente.get(fuente, 0) >= limites_fuente.get(fuente, 1):
                    continue

                resultados_ordenados = sorted(
                    resultados,
                    key=lambda resultado: (
                        self._puntaje_textual_candidato(
                            resultado,
                            consulta,
                        )
                    ),
                    reverse=True,
                )

                for resultado in resultados_ordenados[:10]:
                    if conteo_fuente.get(fuente, 0) >= limites_fuente.get(fuente, 1):
                        break

                    puntaje_textual = (
                        self._puntaje_textual_candidato(
                            resultado,
                            consulta,
                        )
                    )

                    minimo = (
                        2
                        if fuente in {"wikimedia", "openverse"}
                        else 1
                    )

                    if puntaje_textual < minimo:
                        continue

                    recurso = self._convertir_candidato_imagen(
                        resultado=resultado,
                        fuente=fuente,
                    )

                    if recurso is None:
                        continue

                    recurso["_puntaje_textual_local"] = (
                        puntaje_textual
                    )
                    recurso["_consulta_local"] = consulta

                    clave = (
                        fuente,
                        int(recurso["id"]),
                    )

                    if clave in claves_vistas:
                        continue

                    extension = str(
                        recurso.get("extension")
                        or ".jpg"
                    )

                    if not extension.startswith("."):
                        extension = f".{extension}"

                    destino = (
                        carpeta
                        / (
                            f"{fuente}_"
                            f"{recurso['id']}"
                            f"{extension}"
                        )
                    )

                    try:
                        if not destino.is_file():
                            cliente.descargar(
                                url=str(recurso["url"]),
                                destino=destino,
                            )

                    except Exception as error:
                        if self._registrar_error_fatal(error):
                            raise RuntimeError(
                                "DETENER_RECOLECCION: "
                                f"{error}"
                            ) from error

                        mensaje_error = str(error)

                        if "HTTP Error 429" in mensaje_error:
                            fuentes_bloqueadas.add(
                                fuente
                            )

                            print(
                                "  AVISO: "
                                f"{fuente} limit? temporalmente "
                                "las descargas. Se usar? la "
                                "otra fuente para este clip."
                            )
                            break

                        print(
                            "  AVISO candidato visual: "
                            f"{error}"
                        )
                        continue

                    claves_vistas.add(clave)
                    recursos.append(recurso)
                    imagenes.append(destino)

                    if fuente in {"wikimedia", "openverse"}:
                        time.sleep(0.5)

                    conteo_fuente[fuente] = (
                        conteo_fuente.get(fuente, 0)
                        + 1
                    )

                    if len(imagenes) >= 4:
                        break

                if len(imagenes) >= 4:
                    break

            if len(imagenes) >= 4:
                break

        return (
            recursos[:4],
            imagenes[:4],
            consulta_principal,
        )

    def _preparar_selecciones_lote(
        self,
        contenido_plan: dict[str, Any],
        ruta_plan: Path,
        limite: int,
    ) -> None:
        """Verifica hasta cinco clips por solicitud y conserva cach?."""
        self.modo_lote_activo = True

        ruta_cache = self._ruta_cache_selecciones(
            ruta_plan
        )

        cache: dict[str, Any] = {
            "plan": str(ruta_plan.resolve()),
            "selecciones": {},
        }

        if ruta_cache.is_file():
            try:
                cargado = json.loads(
                    ruta_cache.read_text(
                        encoding="utf-8"
                    )
                )

                if isinstance(cargado, dict):
                    cache = cargado

            except Exception:
                pass

        selecciones_cache = cache.setdefault(
            "selecciones",
            {},
        )

        objetivos: list[
            tuple[str, dict[str, Any]]
        ] = []

        cantidad_imagenes = 0
        segmentos = contenido_plan[
            "plan_visual"
        ]["segmentos"]

        for indice_segmento, segmento in enumerate(
            segmentos,
            start=1,
        ):
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

                if (
                    str(clip.get("tipo_recurso", ""))
                    != "imagen_stock"
                ):
                    continue

                identificador = (
                    f"s{indice_segmento:02d}_"
                    f"c{posicion_clip:02d}"
                )

                clip[
                    "_id_verificacion_lote"
                ] = identificador

                cantidad_imagenes += 1

                guardado = selecciones_cache.get(
                    identificador
                )

                if (
                    isinstance(guardado, dict)
                    and self._verificacion_cache_estricta(guardado)
                ):
                    recurso = guardado.get(
                        "recurso"
                    )

                    self.selecciones_lote[
                        identificador
                    ] = (
                        recurso
                        if isinstance(recurso, dict)
                        else None
                    )

                    self.consultas_lote[
                        identificador
                    ] = str(
                        guardado.get(
                            "consulta",
                            "",
                        )
                    )

                else:
                    if isinstance(guardado, dict):
                        selecciones_cache.pop(
                            identificador,
                            None,
                        )

                    objetivos.append(
                        (
                            identificador,
                            clip,
                        )
                    )

                if (
                    limite > 0
                    and cantidad_imagenes >= limite
                ):
                    break

            if (
                limite > 0
                and cantidad_imagenes >= limite
            ):
                break

        if not objetivos:
            print(
                "Verificaci?n visual: "
                "selecciones recuperadas de la cach?."
            )
            return

        grupos_pendientes: list[
            dict[str, Any]
        ] = []

        metadatos_grupo: dict[
            str,
            dict[str, Any]
        ] = {}

        def procesar_grupos() -> None:
            if not grupos_pendientes:
                return

            numero_lote = (
                len(selecciones_cache) // 5
            ) + 1

            lamina = (
                ruta_cache.parent
                / f"lamina_lote_{ruta_cache.stem}_{numero_lote}.jpg"
            )

            print(
                "Verificando lote visual: "
                f"{len(grupos_pendientes)} clips "
                "en una solicitud de Gemini."
            )

            if getattr(
                self,
                "_verificacion_visual_remota_desactivada",
                False,
            ):
                resultados = {}
            else:
                try:
                    resultados = (
                        self.verificador_visual.seleccionar_lote(
                            grupos=grupos_pendientes,
                            lamina_temporal=lamina,
                        )
                    )
                except (RuntimeError, httpx.TransportError) as error:
                    self._verificacion_visual_remota_desactivada = True
                    resultados = {}

                    print(
                        "  AVISO: Gemini no esta disponible. "
                        "Se activara la seleccion visual local "
                        f"durante esta ejecucion: {error}"
                    )

            if resultados:
                grupos_rechazados = [
                    grupo
                    for grupo in grupos_pendientes
                    if int(
                        resultados.get(
                            str(grupo["id"]),
                            {},
                        ).get("seleccion", 0)
                    )
                    == 0
                ]

                if grupos_rechazados:
                    print(
                        "  CLIP local revisara los rechazos de Gemini: "
                        f"{len(grupos_rechazados)} clips."
                    )

                    try:
                        resultados_locales = (
                            self.verificador_visual_local.seleccionar_lote(
                                grupos=grupos_rechazados,
                                lamina_temporal=lamina,
                            )
                        )

                        for identificador_local, resultado_local in (
                            resultados_locales.items()
                        ):
                            if (
                                int(resultado_local.get("seleccion", 0)) > 0
                                and bool(
                                    resultado_local.get("aprobada", False)
                                )
                            ):
                                resultados[identificador_local] = resultado_local

                    except Exception as error:
                        print(
                            "  AVISO: CLIP local no pudo revisar "
                            f"los rechazos: {error}"
                        )

            if not resultados:
                print(
                    "  Gemini no esta disponible; "
                    "verificando las imagenes con CLIP local."
                )

                try:
                    resultados = (
                        self.verificador_visual_local.seleccionar_lote(
                            grupos=grupos_pendientes,
                            lamina_temporal=lamina,
                        )
                    )
                except Exception as error:
                    resultados = {}
                    print(
                        "  BLOQUEO ESTRICTO: CLIP local tampoco "
                        f"esta disponible: {error}"
                    )

                for grupo_respaldo in grupos_pendientes:
                    identificador_respaldo = str(
                        grupo_respaldo["id"]
                    )

                    if identificador_respaldo in resultados:
                        continue

                    resultados[identificador_respaldo] = {
                        "seleccion": 0,
                        "aprobada": False,
                        "puntaje": 0,
                        "cumple_concepto": False,
                        "cumple_obligatorios": False,
                        "viola_prohibidos": True,
                        "motivo": (
                            "No se aprobo sin una verificacion visual."
                        ),
                        "verificacion_degradada": False,
                        "verificador": "ninguno",
                    }

            for grupo in grupos_pendientes:
                identificador = str(
                    grupo["id"]
                )

                resultado = resultados.get(
                    identificador,
                    {},
                )

                seleccion = int(
                    resultado.get(
                        "seleccion",
                        0,
                    )
                )

                metadata = metadatos_grupo[
                    identificador
                ]

                recursos = metadata[
                    "recursos"
                ]

                recurso_elegido = None

                if (
                    1 <= seleccion <= len(recursos)
                ):
                    recurso_elegido = dict(
                        recursos[seleccion - 1]
                    )

                    recurso_elegido[
                        "verificacion_visual"
                    ] = resultado

                    clave_usada = (
                        "imagen",
                        int(recurso_elegido["id"]),
                    )

                    self.recursos_usados.add(
                        clave_usada
                    )

                    print(
                        "  APROBADA "
                        f"{identificador}: "
                        f"{resultado.get('puntaje', 0)}/100"
                    )

                else:
                    print(
                        "  RECHAZADA "
                        f"{identificador}: "
                        "ning?n candidato adecuado."
                    )

                consulta = str(
                    metadata["consulta"]
                )

                self.selecciones_lote[
                    identificador
                ] = recurso_elegido

                self.consultas_lote[
                    identificador
                ] = consulta

                selecciones_cache[
                    identificador
                ] = {
                    "consulta": consulta,
                    "recurso": recurso_elegido,
                    "verificacion": resultado,
                }

            self._guardar_cache_selecciones(
                ruta_cache=ruta_cache,
                datos=cache,
            )

            grupos_pendientes.clear()
            metadatos_grupo.clear()

        for identificador, clip in objetivos:
            print(
                "Preparando candidatos: "
                f"{identificador}"
            )

            recursos, imagenes, consulta = (
                self._obtener_candidatos_lote(
                    clip=clip,
                    identificador=identificador,
                )
            )

            if not imagenes:
                self.selecciones_lote[
                    identificador
                ] = None

                self.consultas_lote[
                    identificador
                ] = consulta

                selecciones_cache[
                    identificador
                ] = {
                    "consulta": consulta,
                    "recurso": None,
                    "verificacion": {
                        "seleccion": 0,
                        "aprobada": False,
                        "motivo": (
                            "No se encontraron candidatos."
                        ),
                    },
                }

                self._guardar_cache_selecciones(
                    ruta_cache=ruta_cache,
                    datos=cache,
                )
                continue

            grupos_pendientes.append(
                {
                    "id": identificador,
                    "imagenes": imagenes,
                    "requisito_visual": (
                        self._requisito_visual(
                            clip
                        )
                    ),
                }
            )

            metadatos_grupo[
                identificador
            ] = {
                "recursos": recursos,
                "consulta": consulta,
            }

            if len(grupos_pendientes) >= 5:
                procesar_grupos()

        procesar_grupos()

    def _registrar_error_fatal(
        self,
        error: Exception,
    ) -> bool:
        """Activa el cortacircuitos ante cuota o red ca?da."""
        mensaje = str(error)
        mensaje_mayusculas = mensaje.upper()

        indicadores = (
            "RESOURCE_EXHAUSTED",
            "QUOTA EXCEEDED",
            "GENERATE_CONTENT_FREE_TIER_REQUESTS",
        )

        if not any(
            indicador in mensaje_mayusculas
            for indicador in indicadores
        ):
            return False

        self.detener_recoleccion = True
        self.motivo_detencion = mensaje

        return True

    def _seleccionar_imagen_verificada(
        self,
        resultados_pexels: list[dict[str, Any]],
        resultados_wikimedia: list[dict[str, Any]],
        resultados_pixabay: list[dict[str, Any]],
        resultados_openverse: list[dict[str, Any]],
        clip: dict[str, Any],
    ) -> dict[str, Any] | None:
        candidatos: list[
            tuple[
                dict[str, Any],
                Path,
                str,
            ]
        ] = []

        carpeta_revision = (
            self.data_dir
            / "cache"
            / "verificacion_visual"
        )

        carpeta_revision.mkdir(
            parents=True,
            exist_ok=True,
        )

        fuentes = [
            (
                "pexels",
                resultados_pexels[:3],
                self.cliente_pexels,
            ),
            (
                "wikimedia",
                resultados_wikimedia[:3],
                self.cliente_wikimedia,
            ),
            (
                "pixabay",
                resultados_pixabay[:3],
                self.cliente,
            ),
            (
                "openverse",
                resultados_openverse[:3],
                self.cliente_openverse,
            ),
        ]

        for fuente, resultados, cliente in fuentes:
            for resultado in resultados:
                recurso = self._seleccionar_imagen(
                    [resultado]
                )

                if recurso is None:
                    continue

                extension = str(
                    recurso.get("extension")
                    or ".jpg"
                )

                destino_revision = (
                    carpeta_revision
                    / (
                        f"{fuente}_"
                        f"{recurso['id']}"
                        f"{extension}"
                    )
                )

                try:
                    if not destino_revision.is_file():
                        cliente.descargar(
                            url=str(recurso["url"]),
                            destino=destino_revision,
                        )

                except Exception as error:
                    print(
                        "  AVISO candidato visual: "
                        f"{error}"
                    )
                    continue

                recurso["_fuente"] = fuente

                candidatos.append(
                    (
                        recurso,
                        destino_revision,
                        fuente,
                    )
                )

        if not candidatos:
            return None

        requisito = self._requisito_visual(
            clip
        )

        lamina = (
            carpeta_revision
            / (
                "lamina_"
                f"{abs(hash(requisito))}"
                ".jpg"
            )
        )

        try:
            verificacion = (
                self.verificador_visual.seleccionar(
                    imagenes=[
                        candidato[1]
                        for candidato in candidatos
                    ],
                    requisito_visual=requisito,
                    lamina_temporal=lamina,
                )
            )

        except Exception as error:
            if self._registrar_error_fatal(error):
                self.detener_recoleccion = False
                self.motivo_detencion = ""

            print(
                "  AVISO verificacion Gemini: "
                f"{error}. Se usara CLIP local."
            )

            try:
                verificacion = (
                    self.verificador_visual_local.seleccionar(
                        imagenes=[
                            candidato[1]
                            for candidato in candidatos
                        ],
                        requisito_visual=requisito,
                        lamina_temporal=lamina,
                    )
                )
            except Exception as error_local:
                print(
                    "  BLOQUEO ESTRICTO: CLIP local no pudo "
                    f"verificar las imagenes: {error_local}"
                )
                return None

        if (
            int(verificacion.get("seleccion", 0)) == 0
            and verificacion.get("verificador") != "CLIP local"
        ):
            print(
                "  Gemini rechazo todas las candidatas; "
                "CLIP local realizara una segunda revision."
            )

            try:
                verificacion_local = (
                    self.verificador_visual_local.seleccionar(
                        imagenes=[
                            candidato[1]
                            for candidato in candidatos
                        ],
                        requisito_visual=requisito,
                        lamina_temporal=lamina,
                    )
                )

                if bool(verificacion_local.get("aprobada", False)):
                    verificacion = verificacion_local
            except Exception as error_local:
                print(
                    "  AVISO: CLIP local no pudo realizar "
                    f"la segunda revision: {error_local}"
                )

        seleccion = int(
            verificacion.get(
                "seleccion",
                0,
            )
        )

        if seleccion < 1 or seleccion > len(candidatos):
            print(
                "  RECHAZADO: ninguna imagen "
                "alcanz? 75/100."
            )
            return None

        recurso_elegido = candidatos[
            seleccion - 1
        ][0]

        recurso_elegido[
            "verificacion_visual"
        ] = verificacion

        print(
            "  Imagen aprobada por "
            f"{verificacion.get('verificador', 'Gemini')}: "
            f"{verificacion.get('puntaje', 0)}/100"
        )

        return recurso_elegido

    def buscar_recurso(
        self,
        tipo: str,
        clip: dict[str, Any],
    ) -> tuple[
        dict[str, Any] | None,
        str,
    ]:
        """Busca y verifica un recurso usando varias consultas."""
        if (
            tipo == "imagen_stock"
            and self.modo_lote_activo
        ):
            identificador = str(
                clip.get(
                    "_id_verificacion_lote",
                    "",
                )
            )

            if identificador:
                return (
                    self.selecciones_lote.get(
                        identificador
                    ),
                    self.consultas_lote.get(
                        identificador,
                        "",
                    ),
                )

            return None, ""

        consultas = self._consultas_clip(
            clip
        )

        for consulta in consultas:
            if tipo == "video_stock":
                fuentes_video = [
                    (
                        "pexels",
                        self.cliente_pexels,
                    ),
                    (
                        "pixabay",
                        self.cliente,
                    ),
                ]

                for fuente, cliente in fuentes_video:
                    try:
                        resultados = (
                            cliente.buscar_videos(
                                consulta=consulta,
                            )
                        )

                    except Exception as error:
                        if self._registrar_error_fatal(error):
                            raise RuntimeError(
                                "DETENER_RECOLECCION: "
                                f"{error}"
                            ) from error

                        print(
                            f"  AVISO {fuente.title()}: "
                            f"{error}"
                        )
                        continue

                    for resultado in resultados:
                        if isinstance(resultado, dict):
                            resultado["_fuente"] = fuente

                    recurso = self._seleccionar_video(
                        resultados,
                        consulta=consulta,
                    )

                    if recurso is not None:
                        recurso["_fuente"] = fuente
                        return recurso, consulta

                continue

            try:
                resultados_pexels = (
                    self.cliente_pexels.buscar_imagenes(
                        consulta=consulta,
                    )
                )

            except Exception as error:
                if self._registrar_error_fatal(error):
                    raise RuntimeError(
                        "DETENER_RECOLECCION: "
                        f"{error}"
                    ) from error

                print("  AVISO Pexels: " f"{error}")
                resultados_pexels = []

            try:
                resultados_wikimedia = (
                    self.cliente_wikimedia.buscar_imagenes(
                        consulta=consulta,
                    )
                )

            except Exception as error:
                if self._registrar_error_fatal(error):
                    raise RuntimeError(
                        "DETENER_RECOLECCION: "
                        f"{error}"
                    ) from error

                print(
                    "  AVISO Wikimedia: "
                    f"{error}"
                )
                resultados_wikimedia = []

            try:
                resultados_pixabay = (
                    self.cliente.buscar_imagenes(
                        consulta=consulta,
                    )
                )

            except Exception as error:
                if self._registrar_error_fatal(error):
                    raise RuntimeError(
                        "DETENER_RECOLECCION: "
                        f"{error}"
                    ) from error

                print(
                    "  AVISO Pixabay: "
                    f"{error}"
                )
                resultados_pixabay = []

            try:
                resultados_openverse = (
                    self.cliente_openverse.buscar_imagenes(
                        consulta=consulta,
                    )
                )

            except Exception as error:
                if self._registrar_error_fatal(error):
                    raise RuntimeError(
                        "DETENER_RECOLECCION: "
                        f"{error}"
                    ) from error

                print(
                    "  AVISO Openverse: "
                    f"{error}"
                )
                resultados_openverse = []

            recurso = (
                self._seleccionar_imagen_verificada(
                    resultados_pexels=(
                        resultados_pexels
                    ),
                    resultados_wikimedia=(
                        resultados_wikimedia
                    ),
                    resultados_pixabay=(
                        resultados_pixabay
                    ),
                    resultados_openverse=(
                        resultados_openverse
                    ),
                    clip=clip,
                )
            )

            if recurso is not None:
                return recurso, consulta

        return None, ""

    def recolectar(
        self,
        contenido_plan: dict[str, Any],
        ruta_plan: Path,
        limite: int = 6,
        channel_slug: str = "nexon_ia",
    ) -> dict[str, Any]:
        """Descarga recursos del plan visual."""
        plan = contenido_plan["plan_visual"]
        segmentos = plan["segmentos"]

        self._cargar_recursos_historicos(
            channel_slug=channel_slug,
            titulo_video=str(plan.get("titulo", "")),
        )

        self._preparar_selecciones_lote(
            contenido_plan=contenido_plan,
            ruta_plan=ruta_plan,
            limite=limite,
        )

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
        descargados_stock = 0
        generados_ia = 0
        reutilizados_clip = 0
        reutilizados_historicos = 0
        pendientes = 0
        sin_recurso = 0
        pendientes_cuota_ia = 0
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
                    "concepto_central": clip.get(
                        "concepto_central",
                        "",
                    ),
                    "criterios_obligatorios": clip.get(
                        "criterios_obligatorios",
                        [],
                    ),
                    "elementos_prohibidos": clip.get(
                        "elementos_prohibidos",
                        [],
                    ),
                    "continuidad_id": clip.get(
                        "continuidad_id",
                        "",
                    ),
                    "consultas_alternativas": clip.get(
                        "consultas_alternativas",
                        [],
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
                        reutilizado = self._reutilizar_recurso_aprobado(
                            clip=clip,
                            segmento_indice=indice_segmento,
                            titulo_segmento=titulo_segmento,
                            carpeta_segmento=carpeta_segmento,
                            posicion_clip=posicion_clip,
                        )

                        if reutilizado is not None:
                            destino_reutilizado, metadata_reutilizacion = (
                                reutilizado
                            )
                            descargados += 1
                            reutilizados_clip += 1
                            if bool(
                                metadata_reutilizacion.get(
                                    "coleccion_historica",
                                    False,
                                )
                            ):
                                reutilizados_historicos += 1
                            elementos.append(
                                {
                                    **base,
                                    "estado": "descargado",
                                    "fuente": "reutilizacion_clip_local",
                                    "consulta": "narracion_directa",
                                    "archivo": str(
                                        destino_reutilizado.resolve()
                                    ),
                                    "reutilizacion": metadata_reutilizacion,
                                }
                            )
                            print(
                                "  OK REUTILIZADO: "
                                f"{destino_reutilizado.name}"
                            )
                            continue

                        if generados_ia >= self.maximo_imagenes_ia:
                            raise RuntimeError(
                                "Se alcanzo el limite editorial de "
                                f"{self.maximo_imagenes_ia} imagenes IA "
                                "para este documental."
                            )

                        if self.cuota_imagen_ia_agotada:
                            raise CuotaImagenIAAgotada(
                                "Workers AI sigue sin cuota disponible; "
                                "se continuara revisando el resto del plan."
                            )

                        resultado_ia = (
                            self._generar_imagen_ia_verificada(
                                clip=clip,
                                carpeta_segmento=carpeta_segmento,
                                posicion_clip=posicion_clip,
                            )
                        )

                        if resultado_ia is None:
                            raise RuntimeError(
                                "Workers AI no genero una candidata "
                                "que superara la verificacion visual."
                            )

                        destino_ia, metadata_ia = resultado_ia
                        descargados += 1
                        generados_ia += 1

                        elementos.append(
                            {
                                **base,
                                "estado": "descargado",
                                "fuente": "cloudflare_workers_ai",
                                "consulta": "narracion_directa",
                                "archivo": str(destino_ia.resolve()),
                                "licencia": (
                                    "Imagen ilustrativa generada por IA"
                                ),
                                "generacion_ia": metadata_ia,
                            }
                        )

                        self._registrar_recurso_reutilizable(
                            segmento_indice=indice_segmento,
                            archivo=destino_ia,
                            fuente="cloudflare_workers_ai",
                        )

                        print(f"  OK IA: {destino_ia.name}")
                        continue

                    fuente = str(
                        recurso.get(
                            "_fuente",
                            "pixabay",
                        )
                    )

                    extension = (
                        ".mp4"
                        if tipo == "video_stock"
                        else str(
                            recurso.get("extension")
                            or ".jpg"
                        )
                    )

                    nombre_archivo = (
                        f"clip_{posicion_clip:02d}_"
                        f"{fuente}_{recurso['id']}"
                        f"{extension}"
                    )

                    destino = (
                        carpeta_segmento
                        / nombre_archivo
                    )

                    clientes_descarga = {
                        "wikimedia": self.cliente_wikimedia,
                        "pexels": self.cliente_pexels,
                        "pixabay": self.cliente,
                        "openverse": self.cliente_openverse,
                    }

                    cliente_descarga = (
                        clientes_descarga.get(
                            fuente,
                            self.cliente,
                        )
                    )

                    ultimo_error_descarga: Exception | None = None

                    for intento_descarga in range(1, 4):
                        try:
                            cliente_descarga.descargar(
                                url=str(recurso["url"]),
                                destino=destino,
                            )

                            ultimo_error_descarga = None
                            break

                        except Exception as error_descarga:
                            ultimo_error_descarga = error_descarga

                            if self._registrar_error_fatal(
                                error_descarga
                            ):
                                raise

                            if intento_descarga >= 3:
                                break

                            mensaje_descarga = str(
                                error_descarga
                            )

                            espera_descarga = (
                                10 * intento_descarga
                                if "429" in mensaje_descarga
                                else 3 * intento_descarga
                            )

                            print(
                                "  AVISO descarga "
                                f"{fuente}: "
                                f"{error_descarga}. "
                                "Reintento "
                                f"{intento_descarga}/2 "
                                "en "
                                f"{espera_descarga} segundos..."
                            )

                            time.sleep(
                                espera_descarga
                            )

                    if ultimo_error_descarga is not None:
                        raise ultimo_error_descarga

                    descargados += 1
                    descargados_stock += 1

                    elementos.append(
                        {
                            **base,
                            "estado": "descargado",
                            "fuente": fuente,
                            "consulta": consulta,
                            "archivo": str(
                                destino.resolve()
                            ),
                            fuente: {
                                clave: valor
                                for clave, valor
                                in recurso.items()
                                if clave not in {
                                    "url",
                                    "_fuente",
                                }
                            },
                        }
                    )

                    self._registrar_recurso_reutilizable(
                        segmento_indice=indice_segmento,
                        archivo=destino,
                        fuente=fuente,
                    )

                    print(
                        f"  OK: {nombre_archivo}"
                    )

                    time.sleep(0.25)

                except CuotaImagenIAAgotada as error:
                    pendientes_cuota_ia += 1
                    self.cuota_imagen_ia_agotada = True
                    self.detener_recoleccion = False
                    self.motivo_detencion = str(error)

                    elementos.append(
                        {
                            **base,
                            "estado": "pendiente_cuota_imagen_ia",
                            "motivo": str(error),
                        }
                    )

                    print(f"  PAUSA SEGURA: {error}")
                    print(
                        "  CONTINUANDO: se buscaran recursos de stock "
                        "y reutilizaciones CLIP para los clips restantes."
                    )

                except Exception as error:
                    error_fatal = (
                        self._registrar_error_fatal(
                            error
                        )
                    )

                    if error_fatal:
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

                    else:
                        sin_recurso += 1

                        elementos.append(
                            {
                                **base,
                                "estado": "pendiente_sin_recurso",
                                "motivo": (
                                    "Recurso de stock no disponible. "
                                    "El control editorial prohibe "
                                    "sustituirlo por un grafico."
                                ),
                                "error_original": str(error),
                            }
                        )

                        print(
                            "  PENDIENTE: no se encontro una imagen "
                            "o video que coincida con la narracion."
                        )

                    if self.detener_recoleccion:
                        print(
                            "\nRECOLECCI?N DETENIDA PARA "
                            "PROTEGER LA CUOTA Y EVITAR "
                            "M?S INTENTOS."
                        )
                        print(
                            "Motivo: "
                            f"{self.motivo_detencion}"
                        )
                        break

            if self.detener_recoleccion:
                break

        cobertura_contextual = self._completar_cobertura_segmentos(
            elementos
        )
        descargados = sum(
            1
            for elemento in elementos
            if str(elemento.get("estado", "")) == "descargado"
        )
        pendientes_cuota_ia = sum(
            1
            for elemento in elementos
            if str(elemento.get("estado", ""))
            == "pendiente_cuota_imagen_ia"
        )
        sin_recurso = sum(
            1
            for elemento in elementos
            if str(elemento.get("estado", ""))
            == "pendiente_sin_recurso"
        )

        manifiesto = {
            "generado_en": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "channel_slug": channel_slug,
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
                "descargados_stock": descargados_stock,
                "generados_ia": generados_ia,
                "reutilizados_clip_local": reutilizados_clip,
                "reutilizados_colecciones_anteriores": (
                    reutilizados_historicos
                ),
                "coberturas_contextuales": cobertura_contextual,
                "maximo_imagenes_ia": self.maximo_imagenes_ia,
                "pendientes_generacion": pendientes,
                "pendientes_sin_recurso": sin_recurso,
                "pendientes_cuota_imagen_ia": pendientes_cuota_ia,
                "omitidos_por_limite": omitidos,
                "errores": errores,
                "recoleccion_detenida": self.detener_recoleccion,
                "motivo_detencion": self.motivo_detencion,
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
