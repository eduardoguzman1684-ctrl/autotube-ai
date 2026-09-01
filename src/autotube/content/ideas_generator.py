from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from autotube.ai.gemini_client import GeminiClient
from autotube.content.channel_profiles import (
    DEFAULT_CHANNEL,
    channel_profile,
    default_niche,
    editorial_prompt,
    normalize_channel_slug,
    resolve_niche,
    strategy_profile_path,
)
from autotube.content.youtube_trends import (
    InvestigadorTendenciasYouTube,
    ordenar_ideas_por_tendencia,
    tendencias_para_prompt,
)


NICHO_PREDETERMINADO = default_niche(DEFAULT_CHANNEL)


IDEAS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "gancho": {"type": "string"},
                    "formato": {"type": "string"},
                    "duracion_minutos": {"type": "integer"},
                    "palabra_clave": {"type": "string"},
                    "angulo": {"type": "string"},
                    "potencial": {"type": "string"},
                },
                "required": [
                    "titulo",
                    "gancho",
                    "formato",
                    "duracion_minutos",
                    "palabra_clave",
                    "angulo",
                    "potencial",
                ],
            },
        }
    },
    "required": ["ideas"],
}


PALABRAS_VACIAS = {
    "a", "al", "algo", "como", "con", "de", "del", "desde",
    "el", "en", "es", "esta", "este", "esto", "la", "las",
    "lo", "los", "mas", "mejor", "para", "por", "que", "sin",
    "su", "sus", "te", "tu", "tus", "un", "una", "uno", "y",
    "ya", "video", "guia", "tutorial", "paso",
}


HERRAMIENTAS = {
    "make",
    "zapier",
    "n8n",
    "chatgpt",
    "openai",
    "claude",
    "gemini",
    "notion",
    "midjourney",
    "canva",
    "gmail",
    "google sheets",
    "airtable",
    "trello",
    "slack",
    "copilot",
    "perplexity",
    "powerpoint",
    "capcut",
}


PLATAFORMAS_AUTOMATIZACION = {
    "make",
    "zapier",
    "n8n",
}


GRUPOS_CONCEPTO = {
    "automatizacion": {
        "automatizar",
        "automatizacion",
        "automatizado",
        "automatizados",
        "flujo",
        "flujos",
        "workflow",
        "workflows",
    },
    "correo": {
        "correo",
        "correos",
        "email",
        "emails",
        "gmail",
        "borrador",
        "borradores",
    },
    "presentaciones": {
        "presentacion",
        "presentaciones",
        "diapositiva",
        "diapositivas",
        "powerpoint",
        "pitch",
    },
    "imagenes": {
        "imagen",
        "imagenes",
        "fotografia",
        "fotografias",
        "midjourney",
        "diseno",
        "marca",
    },
    "productividad": {
        "productividad",
        "tareas",
        "trabajo",
        "tiempo",
        "organizacion",
        "organizar",
    },
    "datos": {
        "datos",
        "extraer",
        "extraccion",
        "hoja",
        "hojas",
        "sheets",
        "tabla",
        "tablas",
    },
    "agentes": {
        "agente",
        "agentes",
        "autonomo",
        "autonomos",
    },
}


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparaci?n."""
    valor = unicodedata.normalize(
        "NFKD",
        str(texto).lower(),
    )

    valor = "".join(
        caracter
        for caracter in valor
        if not unicodedata.combining(caracter)
    )

    valor = re.sub(
        r"[^a-z0-9\s]+",
        " ",
        valor,
    )

    return re.sub(
        r"\s+",
        " ",
        valor,
    ).strip()


def tokens_relevantes(texto: str) -> set[str]:
    """Obtiene palabras relevantes."""
    return {
        token
        for token in normalizar_texto(texto).split()
        if len(token) >= 3
        and token not in PALABRAS_VACIAS
    }


def extraer_herramientas(
    texto: str,
) -> set[str]:
    """Detecta herramientas/plataformas conocidas."""
    normalizado = f" {normalizar_texto(texto)} "

    encontradas: set[str] = set()

    for herramienta in HERRAMIENTAS:
        objetivo = (
            f" {normalizar_texto(herramienta)} "
        )

        if objetivo in normalizado:
            encontradas.add(herramienta)

    return encontradas


def extraer_conceptos(
    texto: str,
) -> set[str]:
    """Detecta los principales casos de uso."""
    tokens = tokens_relevantes(texto)

    conceptos: set[str] = set()

    for concepto, palabras in GRUPOS_CONCEPTO.items():
        if tokens.intersection(
            {
                normalizar_texto(palabra)
                for palabra in palabras
            }
        ):
            conceptos.add(concepto)

    return conceptos


def texto_idea(
    idea: dict[str, Any],
) -> str:
    """Une los campos ?tiles de una idea."""
    return " ".join(
        str(
            idea.get(campo, "")
        )
        for campo in (
            "titulo",
            "gancho",
            "palabra_clave",
            "angulo",
        )
    )


def resumen_guion(
    contenido: dict[str, Any],
) -> tuple[str, str]:
    """Obtiene t?tulo y resumen de un guion producido."""
    guion = contenido.get("guion")

    if not isinstance(guion, dict):
        return "", ""

    titulo = str(
        guion.get("titulo", "")
    ).strip()

    partes = [
        titulo,
        str(
            guion.get(
                "gancho_inicial",
                "",
            )
        ),
        str(
            guion.get(
                "introduccion",
                "",
            )
        ),
    ]

    escenas = guion.get(
        "escenas",
        [],
    )

    if isinstance(escenas, list):
        for escena in escenas:
            if not isinstance(escena, dict):
                continue

            partes.append(
                str(
                    escena.get(
                        "titulo",
                        "",
                    )
                )
            )

            narracion = str(
                escena.get(
                    "narracion",
                    "",
                )
            )

            # Solo un fragmento. Evita enviar guiones
            # completos al detector.
            partes.append(
                narracion[:400]
            )

    return (
        titulo,
        " ".join(partes),
    )


def cargar_historial_guiones(
    data_dir: Path | None,
    limite: int = 20,
    channel_slug: str = DEFAULT_CHANNEL,
) -> list[dict[str, str]]:
    """Carga t?tulos realmente convertidos en guiones."""
    if data_dir is None:
        return []

    carpeta = (
        Path(data_dir)
        / "scripts"
    )

    if not carpeta.is_dir():
        return []

    archivos = sorted(
        carpeta.glob("guion*.json"),
        key=lambda ruta: ruta.stat().st_mtime,
        reverse=True,
    )

    historial: list[dict[str, str]] = []
    titulos_vistos: set[str] = set()
    channel_slug = normalize_channel_slug(channel_slug)

    for ruta in archivos:
        try:
            contenido = json.loads(
                ruta.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        script_channel = normalize_channel_slug(
            str(
                contenido.get(
                    "channel_slug",
                    DEFAULT_CHANNEL,
                )
            )
        )

        if script_channel != channel_slug:
            continue

        titulo, resumen = resumen_guion(
            contenido
        )

        if not titulo:
            continue

        clave = normalizar_texto(
            titulo
        )

        if clave in titulos_vistos:
            continue

        titulos_vistos.add(
            clave
        )

        historial.append(
            {
                "titulo": titulo,
                "resumen": resumen,
            }
        )

        if len(historial) >= limite:
            break

    return historial


def similitud_idea_historial(
    idea: dict[str, Any],
    historial: dict[str, str],
) -> tuple[float, list[str]]:
    """Calcula similitud tem?tica entre idea y video previo."""
    candidato = texto_idea(
        idea
    )

    anterior = str(
        historial.get(
            "resumen",
            "",
        )
    )

    titulo_nuevo = normalizar_texto(
        str(
            idea.get(
                "titulo",
                "",
            )
        )
    )

    titulo_anterior = normalizar_texto(
        historial.get(
            "titulo",
            "",
        )
    )

    ratio_titulo = SequenceMatcher(
        None,
        titulo_nuevo,
        titulo_anterior,
    ).ratio()

    tokens_nuevo = tokens_relevantes(
        candidato
    )

    tokens_anterior = tokens_relevantes(
        anterior
    )

    union = (
        tokens_nuevo
        | tokens_anterior
    )

    if union:
        jaccard = len(
            tokens_nuevo
            & tokens_anterior
        ) / len(union)
    else:
        jaccard = 0.0

    herramientas_nuevas = (
        extraer_herramientas(
            candidato
        )
    )

    herramientas_anteriores = (
        extraer_herramientas(
            anterior
        )
    )

    inter_herramientas = (
        herramientas_nuevas
        & herramientas_anteriores
    )

    if (
        herramientas_nuevas
        and herramientas_anteriores
    ):
        similitud_herramientas = (
            len(inter_herramientas)
            / min(
                len(herramientas_nuevas),
                len(herramientas_anteriores),
            )
        )
    else:
        similitud_herramientas = 0.0

    conceptos_nuevos = (
        extraer_conceptos(
            candidato
        )
    )

    conceptos_anteriores = (
        extraer_conceptos(
            anterior
        )
    )

    inter_conceptos = (
        conceptos_nuevos
        & conceptos_anteriores
    )

    if (
        conceptos_nuevos
        and conceptos_anteriores
    ):
        similitud_conceptos = (
            len(inter_conceptos)
            / min(
                len(conceptos_nuevos),
                len(conceptos_anteriores),
            )
        )
    else:
        similitud_conceptos = 0.0

    puntuacion = (
        ratio_titulo * 0.25
        + jaccard * 0.15
        + similitud_herramientas * 0.30
        + similitud_conceptos * 0.30
    )

    motivos: list[str] = []

    if ratio_titulo >= 0.70:
        motivos.append(
            "titulo muy parecido"
        )

    if inter_herramientas:
        motivos.append(
            "herramientas coincidentes: "
            + ", ".join(
                sorted(
                    inter_herramientas
                )
            )
        )

    if inter_conceptos:
        motivos.append(
            "casos de uso coincidentes: "
            + ", ".join(
                sorted(
                    inter_conceptos
                )
            )
        )

    # --------------------------------------------------------
    # Regla fuerte:
    # la misma plataforma de automatizaci?n no debe dominar
    # varios videos consecutivos de naturaleza similar.
    # --------------------------------------------------------

    plataformas_comunes = (
        inter_herramientas
        & PLATAFORMAS_AUTOMATIZACION
    )

    if (
        plataformas_comunes
        and "automatizacion"
        in conceptos_nuevos
        and "automatizacion"
        in conceptos_anteriores
    ):
        puntuacion = max(
            puntuacion,
            0.82,
        )

        motivos.append(
            "misma plataforma principal de automatizacion"
        )

    # Mismo flujo de correo + automatizaci?n.
    if (
        "correo" in conceptos_nuevos
        and "correo" in conceptos_anteriores
        and "automatizacion" in conceptos_nuevos
        and "automatizacion" in conceptos_anteriores
    ):
        puntuacion = max(
            puntuacion,
            0.92,
        )

        motivos.append(
            "mismo caso practico de automatizacion de correo"
        )

    return (
        round(
            min(
                1.0,
                puntuacion,
            ),
            3,
        ),
        motivos,
    )


def filtrar_ideas_repetidas(
    ideas: list[dict[str, Any]],
    historial: list[dict[str, str]],
    cantidad: int,
    umbral: float = 0.72,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Filtra ideas repetidas contra historial y entre s?."""
    aceptadas: list[dict[str, Any]] = []
    rechazadas: list[dict[str, Any]] = []

    historial_dinamico = list(
        historial
    )

    for idea in ideas:
        if not isinstance(
            idea,
            dict,
        ):
            continue

        peor_score = 0.0
        peor_titulo = ""
        peores_motivos: list[str] = []

        for previo in historial_dinamico:
            score, motivos = (
                similitud_idea_historial(
                    idea,
                    previo,
                )
            )

            if score > peor_score:
                peor_score = score
                peor_titulo = str(
                    previo.get(
                        "titulo",
                        "",
                    )
                )
                peores_motivos = motivos

        if peor_score >= umbral:
            rechazadas.append(
                {
                    "titulo": idea.get(
                        "titulo",
                        "",
                    ),
                    "similitud": round(
                        peor_score * 100,
                        1,
                    ),
                    "comparado_con": (
                        peor_titulo
                    ),
                    "motivos": (
                        peores_motivos
                    ),
                }
            )

            continue

        aceptadas.append(
            idea
        )

        # Evita que Gemini genere dos ideas muy
        # similares dentro del mismo lote.
        historial_dinamico.append(
            {
                "titulo": str(
                    idea.get(
                        "titulo",
                        "",
                    )
                ),
                "resumen": texto_idea(
                    idea
                ),
            }
        )

        if len(aceptadas) >= cantidad:
            break

    return (
        aceptadas,
        rechazadas,
    )


def cargar_contexto_estrategico(
    data_dir: Path | None,
    channel_slug: str = DEFAULT_CHANNEL,
) -> str:
    """Carga aprendizaje del canal sin impedir generar ideas."""
    predeterminado = (
        "APRENDIZAJE REAL DEL CANAL:\n"
        "- No existe todavia un perfil estrategico confiable.\n"
        "- Mantener diversidad editorial y no asumir temas ganadores."
    )

    if data_dir is None:
        return predeterminado

    ruta_perfil = strategy_profile_path(
        Path(data_dir),
        channel_slug,
    )

    if not ruta_perfil.is_file():
        return predeterminado

    try:
        perfil = json.loads(
            ruta_perfil.read_text(
                encoding="utf-8-sig"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return predeterminado

    if not isinstance(
        perfil,
        dict,
    ):
        return predeterminado

    contexto = str(
        perfil.get(
            "contexto_prompt",
            "",
        )
    ).strip()

    if not contexto:
        return predeterminado

    return contexto


class GeneradorIdeas:
    """Genera ideas estructuradas para videos de YouTube."""

    def __init__(
        self,
        cliente: GeminiClient | None = None,
    ) -> None:
        self.cliente = (
            cliente
            or GeminiClient()
        )

    def generar(
        self,
        nicho: str = NICHO_PREDETERMINADO,
        cantidad: int = 5,
        idioma: str = "espanol",
        data_dir: Path | None = None,
        youtube_api_key: str | None = None,
        region_tendencias: str = "MX",
        channel_slug: str = DEFAULT_CHANNEL,
    ) -> dict[str, Any]:
        """Genera ideas nuevas evitando temas ya producidos."""
        channel_slug = normalize_channel_slug(channel_slug)
        profile = channel_profile(channel_slug)
        nicho_limpio = resolve_niche(channel_slug, nicho)
        idioma_limpio = idioma.strip()

        if not nicho_limpio:
            raise ValueError(
                "El nicho no puede estar vacio."
            )

        if cantidad < 1 or cantidad > 20:
            raise ValueError(
                "La cantidad debe estar entre 1 y 20."
            )

        historial = cargar_historial_guiones(
            data_dir=data_dir,
            channel_slug=channel_slug,
        )

        historial_prompt = "\n".join(
            f"- {item['titulo']}"
            for item in historial
        )

        if not historial_prompt:
            historial_prompt = (
                "- No hay videos previos registrados."
            )

        # Pedimos candidatos adicionales porque varios
        # pueden ser descartados por similitud.
        cantidad_candidatos = min(
            20,
            max(
                cantidad,
                cantidad * 3,
            ),
        )

        investigador_tendencias = (
            InvestigadorTendenciasYouTube(
                youtube_api_key
            )
        )

        investigacion_tendencias = (
            investigador_tendencias.investigar(
                nicho=nicho_limpio,
                region=region_tendencias,
                idioma="es",
                dias=21,
                max_resultados=25,
            )
        )

        contexto_tendencias = tendencias_para_prompt(
            investigacion_tendencias
        )

        contexto_estrategico = (
            cargar_contexto_estrategico(
                data_dir,
                channel_slug,
            )
        )

        contexto_editorial = editorial_prompt(
            channel_slug
        )

        prompt = f"""
Actua como director editorial y estratega de documentales para YouTube.

PERFIL DEL CANAL:
{contexto_editorial}

NICHO:
{nicho_limpio}

IDIOMA:
{idioma_limpio}

Genera exactamente {cantidad_candidatos} ideas candidatas para
videos documentales originales que pertenezcan estrictamente al nicho.

VIDEOS O GUIONES YA SELECCIONADOS:
{historial_prompt}

INVESTIGACION DE DEMANDA RECIENTE:
{contexto_tendencias}

APRENDIZAJE DEL RENDIMIENTO REAL:
{contexto_estrategico}

OBJETIVO EDITORIAL:

Respeta el perfil del canal y el nicho recibido. No traslades temas,
marcas, vocabulario ni tendencias de otro canal. El contenido debe ser
educativo, riguroso, humano y visualmente atractivo.

Para cada idea proporciona:

- titulo: atractivo, documental, claro y honesto;
- gancho: apertura intrigante sin sensacionalismo falso;
- formato: siempre "video largo";
- duracion_minutos: siempre 15;
- palabra_clave: termino principal para SEO;
- angulo: enfoque documental diferenciador;
- potencial: "alto", "medio" o "experimental".

REGLAS:

1. Cada idea debe poder ilustrarse con videos de stock, imagenes,
   personas, situaciones cotidianas, lugares, archivos, graficos
   y texto animado relacionados realmente con el tema.
2. No propongas temas que requieran mostrar una instalacion o interfaz.
3. No repitas temas incluidos en el historial.
4. Prioriza relevancia, curiosidad, utilidad publica y retencion.
5. No inventes noticias, estudios, estadisticas ni avances.
6. Ordena las ideas desde la de mayor potencial hasta la de menor.
7. Usa las se?ales recientes de YouTube como evidencia de demanda,
   pero no copies t?tulos ni conviertas rumores en hechos.
   No reutilices secuencias de tres o m?s palabras de esos t?tulos.
8. Prefiere temas documentales duraderos que adem?s muestren inter?s
   reciente y puedan explicarse con fuentes verificables.
9. La primera idea debe ser la mejor candidata para producirse
   automaticamente.
10. Devuelve solamente el JSON solicitado.
11. Para CogniViva, evita que inteligencia artificial, tecnologia,
    robots o automatizacion sean el tema central, salvo que aparezcan
    expresamente en el NICHO solicitado.
12. En psicologia, informa y educa sin diagnosticar, prescribir,
    prometer curas ni sustituir ayuda profesional.
""".strip()

        respuesta = (
            self.cliente.generar_json(
                prompt=prompt,
                schema=IDEAS_SCHEMA,
            )
        )

        ideas_raw = respuesta.get(
            "ideas"
        )

        if (
            not isinstance(
                ideas_raw,
                list,
            )
            or not ideas_raw
        ):
            raise RuntimeError(
                "Gemini no devolvio una lista valida de ideas."
            )

        ideas, rechazadas = (
            filtrar_ideas_repetidas(
                ideas=[
                    idea
                    for idea in ideas_raw
                    if isinstance(
                        idea,
                        dict,
                    )
                ],
                historial=historial,
                cantidad=cantidad,
            )
        )

        if not ideas:
            raise RuntimeError(
                "Todas las ideas candidatas fueron rechazadas "
                "por similitud con el historial. "
                "Ejecuta nuevamente 'autotube ideas' para obtener "
                "un lote diferente."
            )

        ideas = ordenar_ideas_por_tendencia(
            ideas=ideas,
            investigacion=investigacion_tendencias,
        )

        seleccion_automatica = {
            "titulo": ideas[0].get("titulo", ""),
            "puntuacion_tendencia": ideas[0].get(
                "puntuacion_tendencia",
                0,
            ),
            "criterio": (
                "demanda reciente, afinidad tem?tica, "
                "originalidad y viabilidad documental"
            ),
        }

        return {
            "generado_en": datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            ),
            "channel_slug": channel_slug,
            "channel_name": profile["display_name"],
            "nicho": nicho_limpio,
            "idioma": idioma_limpio,
            "modelo": (
                self.cliente.last_model_used
            ),
            "cantidad": len(
                ideas
            ),
            "historial_comparado": [
                item["titulo"]
                for item in historial
            ],
            "ideas_rechazadas": rechazadas,
            "investigacion_tendencias": (
                investigacion_tendencias
            ),
            "seleccion_automatica": (
                seleccion_automatica
            ),
            "ideas": ideas,
        }

    def guardar(
        self,
        resultado: dict[str, Any],
        data_dir: Path,
    ) -> Path:
        """Guarda las ideas como JSON."""
        ideas_dir = (
            data_dir
            / "ideas"
        )

        ideas_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        marca_tiempo = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        ruta = (
            ideas_dir
            / f"ideas_{marca_tiempo}.json"
        )

        ruta.write_text(
            json.dumps(
                resultado,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return ruta
