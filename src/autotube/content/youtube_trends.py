from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://www.googleapis.com/youtube/v3"


def _entero(valor: Any) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _duracion_segundos(valor: str) -> int:
    patron = re.compile(
        r"^P(?:(?P<dias>\d+)D)?T"
        r"(?:(?P<horas>\d+)H)?"
        r"(?:(?P<minutos>\d+)M)?"
        r"(?:(?P<segundos>\d+)S)?$"
    )
    coincidencia = patron.match(valor or "")

    if not coincidencia:
        return 0

    partes = {
        nombre: _entero(numero)
        for nombre, numero in coincidencia.groupdict().items()
    }

    return (
        partes["dias"] * 86400
        + partes["horas"] * 3600
        + partes["minutos"] * 60
        + partes["segundos"]
    )


class InvestigadorTendenciasYouTube:
    """Consulta se?ales p?blicas recientes de YouTube."""

    def __init__(
        self,
        api_key: str | None,
        timeout: int = 25,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.timeout = max(5, min(int(timeout), 60))

    def _solicitar(
        self,
        recurso: str,
        parametros: dict[str, Any],
    ) -> dict[str, Any]:
        url = (
            f"{API_BASE}/{recurso}?"
            f"{urlencode(parametros, doseq=True)}"
        )

        solicitud = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "AutoTube-AI/1.0",
                "X-Goog-Api-Key": self.api_key,
            },
        )

        with urlopen(
            solicitud,
            timeout=self.timeout,
        ) as respuesta:
            datos = json.loads(
                respuesta.read().decode("utf-8")
            )

        if not isinstance(datos, dict):
            raise RuntimeError(
                "YouTube devolvi? una respuesta inv?lida."
            )

        return datos

    @staticmethod
    def _consulta_nicho(nicho: str) -> str:
        limpio = " ".join(nicho.strip().split())
        minusculas = limpio.lower()

        if "inteligencia artificial" in minusculas:
            return (
                "inteligencia artificial tecnologia futuro "
                "-futbol -mundial -xeneize -gameplay"
            )

        palabras = limpio.split()
        return " ".join(palabras[:8])

    @staticmethod
    def _motivo_http(error: HTTPError) -> str:
        try:
            cuerpo = error.read().decode(
                "utf-8",
                errors="replace",
            )
            datos = json.loads(cuerpo)
            mensaje = datos.get("error", {}).get(
                "message",
                "",
            )
            if mensaje:
                return f"HTTP {error.code}: {mensaje}"
        except Exception:
            pass

        return f"HTTP {error.code}: {error.reason}"

    def investigar(
        self,
        nicho: str,
        region: str = "MX",
        idioma: str = "es",
        dias: int = 21,
        max_resultados: int = 25,
    ) -> dict[str, Any]:
        """Obtiene y clasifica videos recientes del nicho."""
        ahora = datetime.now(timezone.utc)
        dias = max(3, min(int(dias), 60))
        max_resultados = max(
            5,
            min(int(max_resultados), 50),
        )

        base: dict[str, Any] = {
            "consultado_en": ahora.isoformat(
                timespec="seconds"
            ),
            "consulta": self._consulta_nicho(nicho),
            "region": region.upper(),
            "idioma": idioma.lower(),
            "ventana_dias": dias,
            "disponible": False,
            "videos_analizados": 0,
            "videos": [],
        }

        if not self.api_key:
            base["motivo"] = (
                "YOUTUBE_API_KEY no est? configurada."
            )
            return base

        publicado_desde = (
            ahora - timedelta(days=dias)
        ).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")

        try:
            busqueda = self._solicitar(
                "search",
                {
                    "part": "snippet",
                    "type": "video",
                    "order": "viewCount",
                    "maxResults": max_resultados,
                    "publishedAfter": publicado_desde,
                    "regionCode": region.upper(),
                    "relevanceLanguage": idioma.lower(),
                    "safeSearch": "moderate",
                    "videoDuration": "medium",
                    "q": base["consulta"],
                },
            )

            identificadores = [
                str(
                    item.get("id", {}).get(
                        "videoId",
                        "",
                    )
                )
                for item in busqueda.get("items", [])
                if isinstance(item, dict)
            ]
            identificadores = [
                item
                for item in identificadores
                if item
            ]

            if not identificadores:
                base["motivo"] = (
                    "YouTube no devolvi? videos recientes."
                )
                return base

            detalles = self._solicitar(
                "videos",
                {
                    "part": (
                        "snippet,statistics,contentDetails"
                    ),
                    "id": ",".join(identificadores),
                    "maxResults": 50,
                },
            )

        except HTTPError as error:
            base["motivo"] = self._motivo_http(error)
            return base
        except URLError as error:
            base["motivo"] = (
                f"No se pudo conectar con YouTube: "
                f"{error.reason}"
            )
            return base
        except Exception as error:
            base["motivo"] = (
                f"Consulta de tendencias fallida: {error}"
            )
            return base

        videos: list[dict[str, Any]] = []

        for item in detalles.get("items", []):
            if not isinstance(item, dict):
                continue

            snippet = item.get("snippet", {})
            estadisticas = item.get("statistics", {})
            contenido = item.get("contentDetails", {})

            publicado_texto = str(
                snippet.get("publishedAt", "")
            )

            try:
                publicado = datetime.fromisoformat(
                    publicado_texto.replace(
                        "Z",
                        "+00:00",
                    )
                )
            except ValueError:
                continue

            duracion = _duracion_segundos(
                str(contenido.get("duration", ""))
            )

            if duracion < 240:
                continue

            vistas = _entero(
                estadisticas.get("viewCount")
            )
            me_gusta = _entero(
                estadisticas.get("likeCount")
            )
            comentarios = _entero(
                estadisticas.get("commentCount")
            )

            edad_dias = max(
                0.25,
                (ahora - publicado).total_seconds()
                / 86400,
            )
            vistas_dia = round(
                vistas / edad_dias,
                1,
            )
            interaccion = (
                (me_gusta + comentarios) / vistas
                if vistas > 0
                else 0.0
            )

            puntuacion = round(
                math.log10(vistas_dia + 1) * 18
                + min(interaccion * 100, 12) * 2
                + max(0.0, 21 - edad_dias),
                2,
            )

            video_id = str(item.get("id", ""))

            videos.append(
                {
                    "video_id": video_id,
                    "titulo": str(
                        snippet.get("title", "")
                    ),
                    "canal": str(
                        snippet.get(
                            "channelTitle",
                            "",
                        )
                    ),
                    "publicado_en": publicado_texto,
                    "edad_dias": round(edad_dias, 2),
                    "duracion_segundos": duracion,
                    "vistas": vistas,
                    "me_gusta": me_gusta,
                    "comentarios": comentarios,
                    "vistas_por_dia": vistas_dia,
                    "interaccion_porcentaje": round(
                        interaccion * 100,
                        3,
                    ),
                    "puntuacion_tendencia": puntuacion,
                    "url": (
                        "https://www.youtube.com/watch?v="
                        f"{video_id}"
                    ),
                }
            )

        videos.sort(
            key=lambda video: (
                video["puntuacion_tendencia"],
                video["vistas_por_dia"],
            ),
            reverse=True,
        )

        terminos_excluidos = {
            "futbol",
            "fifa",
            "fortnite",
            "gameplay",
            "minecraft",
            "mundial",
            "xeneize",
        }

        videos_editoriales = []

        for video in videos:
            titulo_normalizado = unicodedata.normalize(
                "NFKD",
                str(video.get("titulo", "")).lower(),
            )
            titulo_normalizado = "".join(
                caracter
                for caracter in titulo_normalizado
                if not unicodedata.combining(caracter)
            )

            if any(
                termino in titulo_normalizado
                for termino in terminos_excluidos
            ):
                continue

            videos_editoriales.append(video)

        fuertes = [
            video
            for video in videos_editoriales
            if (
                video["vistas_por_dia"] >= 500
                and video["vistas"] >= 5000
            )
        ]

        moderados = [
            video
            for video in videos_editoriales
            if (
                video["vistas_por_dia"] >= 100
                and video["vistas"] >= 1000
            )
        ]

        respaldo = [
            video
            for video in videos_editoriales
            if (
                video["vistas_por_dia"] >= 25
                and video["vistas"] >= 500
            )
        ]

        if len(fuertes) >= 5:
            videos = fuertes
        elif len(moderados) >= 3:
            videos = moderados
        else:
            videos = respaldo

        videos = videos[:20]

        base["disponible"] = bool(videos)
        base["videos_analizados"] = len(videos)
        base["videos"] = videos

        if not videos:
            base["motivo"] = (
                "No se encontraron videos medianos v?lidos."
            )

        return base


def tendencias_para_prompt(
    resultado: dict[str, Any],
    limite: int = 15,
) -> str:
    """Convierte la investigaci?n en contexto editorial."""
    if not resultado.get("disponible"):
        return (
            "No hay datos externos de tendencias disponibles. "
            "Usa criterio editorial y evita afirmar que un tema "
            "es tendencia sin evidencia."
        )

    lineas = [
        "SE?ALES REALES Y RECIENTES DE YOUTUBE:",
        (
            f"Consulta: {resultado.get('consulta', '')} | "
            f"Regi?n: {resultado.get('region', '')} | "
            f"Ventana: {resultado.get('ventana_dias', 0)} d?as"
        ),
        (
            "Los t?tulos siguientes son evidencia de inter?s, "
            "no deben copiarse literalmente."
        ),
    ]

    for numero, video in enumerate(
        resultado.get("videos", [])[:limite],
        start=1,
    ):
        lineas.append(
            f"{numero}. {video['titulo']} | "
            f"{video['vistas']} vistas | "
            f"{video['vistas_por_dia']} vistas/d?a | "
            f"{video['edad_dias']} d?as | "
            f"score {video['puntuacion_tendencia']}"
        )

    return "\n".join(lineas)


PALABRAS_GENERICAS_TENDENCIA = {
    "artificial",
    "canal",
    "ciencia",
    "como",
    "con",
    "del",
    "desde",
    "este",
    "esta",
    "futuro",
    "inteligencia",
    "para",
    "por",
    "que",
    "sobre",
    "tecnologia",
    "una",
    "video",
}


def _tokens_tendencia(texto: str) -> set[str]:
    normalizado = unicodedata.normalize(
        "NFKD",
        texto.lower(),
    )
    normalizado = "".join(
        caracter
        for caracter in normalizado
        if not unicodedata.combining(caracter)
    )

    return {
        palabra
        for palabra in re.findall(
            r"[a-z0-9]+",
            normalizado,
        )
        if (
            len(palabra) >= 3
            and palabra
            not in PALABRAS_GENERICAS_TENDENCIA
        )
    }


PALABRAS_GENERICAS_COPIA = {
    "artificial",
    "de",
    "del",
    "el",
    "en",
    "futuro",
    "ia",
    "inteligencia",
    "la",
    "las",
    "los",
    "para",
    "por",
    "que",
    "tecnologia",
    "un",
    "una",
    "y",
}


def _palabras_titulo(texto: str) -> list[str]:
    normalizado = unicodedata.normalize(
        "NFKD",
        texto.lower(),
    )
    normalizado = "".join(
        caracter
        for caracter in normalizado
        if not unicodedata.combining(caracter)
    )
    return re.findall(
        r"[a-z0-9]+",
        normalizado,
    )


def _frases_compartidas(
    titulo_idea: str,
    titulo_video: str,
    longitud: int = 4,
) -> set[str]:
    idea = _palabras_titulo(titulo_idea)
    video = _palabras_titulo(titulo_video)

    if (
        len(idea) < longitud
        or len(video) < longitud
    ):
        return set()

    frases_idea = {
        tuple(
            idea[indice:indice + longitud]
        )
        for indice in range(
            len(idea) - longitud + 1
        )
    }

    frases_video = {
        tuple(
            video[indice:indice + longitud]
        )
        for indice in range(
            len(video) - longitud + 1
        )
    }

    compartidas = frases_idea & frases_video

    return {
        " ".join(frase)
        for frase in compartidas
        if any(
            palabra not in PALABRAS_GENERICAS_COPIA
            for palabra in frase
        )
    }


def ordenar_ideas_por_tendencia(
    ideas: list[dict[str, Any]],
    investigacion: dict[str, Any],
) -> list[dict[str, Any]]:
    """Punt?a y ordena ideas seg?n evidencia reciente."""
    videos = investigacion.get("videos", [])

    if (
        not investigacion.get("disponible")
        or not isinstance(videos, list)
        or not videos
    ):
        return ideas

    puntuacion_maxima = max(
        float(
            video.get(
                "puntuacion_tendencia",
                0,
            )
            or 0
        )
        for video in videos
        if isinstance(video, dict)
    ) or 1.0

    vistas_dia_maximas = max(
        float(
            video.get(
                "vistas_por_dia",
                0,
            )
            or 0
        )
        for video in videos
        if isinstance(video, dict)
    ) or 1.0

    evaluadas: list[
        tuple[float, int, dict[str, Any]]
    ] = []

    for posicion, idea_original in enumerate(ideas):
        idea = dict(idea_original)

        texto_idea = " ".join(
            [
                str(idea.get("titulo", "")),
                str(idea.get("palabra_clave", "")),
                str(idea.get("angulo", "")),
                str(idea.get("gancho", "")),
            ]
        )

        tokens_idea = _tokens_tendencia(
            texto_idea
        )

        coincidencias: list[
            tuple[float, dict[str, Any], set[str]]
        ] = []

        for video in videos:
            if not isinstance(video, dict):
                continue

            tokens_video = _tokens_tendencia(
                str(video.get("titulo", ""))
            )
            comunes = tokens_idea & tokens_video

            if not comunes:
                continue

            cobertura = len(comunes) / max(
                1,
                min(
                    len(tokens_idea),
                    len(tokens_video),
                ),
            )

            fuerza = (
                float(
                    video.get(
                        "puntuacion_tendencia",
                        0,
                    )
                    or 0
                )
                / puntuacion_maxima
            )

            demanda = (
                float(
                    video.get(
                        "vistas_por_dia",
                        0,
                    )
                    or 0
                )
                / vistas_dia_maximas
            )

            relevancia = cobertura * (
                0.35 * fuerza
                + 0.65 * math.sqrt(
                    max(0.0, demanda)
                )
            )

            coincidencias.append(
                (
                    relevancia,
                    video,
                    comunes,
                )
            )

        coincidencias.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        mejores = coincidencias[:3]

        if mejores:
            mejor = mejores[0][0]
            promedio = sum(
                item[0]
                for item in mejores
            ) / len(mejores)

            puntuacion = round(
                min(
                    100.0,
                    (
                        mejor * 0.75
                        + promedio * 0.25
                    )
                    * 100,
                ),
                1,
            )
        else:
            puntuacion = 0.0

        frases_copiadas: set[str] = set()

        for video in videos:
            if not isinstance(video, dict):
                continue

            frases_copiadas.update(
                _frases_compartidas(
                    str(idea.get("titulo", "")),
                    str(video.get("titulo", "")),
                )
            )

        puntuacion_antes_originalidad = puntuacion

        if frases_copiadas:
            penalizacion_originalidad = min(
                90.0,
                60.0
                + max(
                    0,
                    len(frases_copiadas) - 1,
                )
                * 10.0,
            )
            puntuacion = round(
                max(
                    0.0,
                    puntuacion
                    - penalizacion_originalidad,
                ),
                1,
            )
        else:
            penalizacion_originalidad = 0.0

        idea["puntuacion_base_tendencia"] = (
            puntuacion_antes_originalidad
        )
        idea["penalizacion_originalidad"] = (
            penalizacion_originalidad
        )
        idea["frases_coincidentes"] = sorted(
            frases_copiadas
        )
        idea["puntuacion_tendencia"] = puntuacion
        idea["evidencia_tendencia"] = [
            {
                "titulo": video.get(
                    "titulo",
                    "",
                ),
                "url": video.get(
                    "url",
                    "",
                ),
                "vistas_por_dia": video.get(
                    "vistas_por_dia",
                    0,
                ),
                "coincidencias": sorted(
                    comunes
                ),
            }
            for _, video, comunes in mejores
        ]

        evaluadas.append(
            (
                puntuacion,
                -posicion,
                idea,
            )
        )

    evaluadas.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return [
        idea
        for _, _, idea in evaluadas
    ]
