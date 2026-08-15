from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from autotube.ai.gemini_client import GeminiClient


NICHO_PREDETERMINADO = (
    "inteligencia artificial, automatizacion, herramientas digitales, "
    "productividad y negocios digitales"
)


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

    for ruta in archivos:
        try:
            contenido = json.loads(
                ruta.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
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
    ) -> dict[str, Any]:
        """Genera ideas nuevas evitando temas ya producidos."""
        nicho_limpio = nicho.strip()
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

        prompt = f"""
Actua como estratega experto en crecimiento de canales de YouTube.

Canal: NEXON IA.

Genera exactamente {cantidad_candidatos} ideas CANDIDATAS para un canal
internacional del nicho:

{nicho_limpio}

Idioma de salida:
{idioma_limpio}

VIDEOS O GUIONES YA SELECCIONADOS:
{historial_prompt}

OBJETIVO PRINCIPAL:

Las nuevas ideas deben ampliar el catalogo del canal.
NO deben ser variaciones superficiales de videos anteriores.

Por ejemplo, si ya existe un tutorial de Make + inteligencia artificial
+ automatizacion de correos, NO propongas otro tutorial de Make +
ChatGPT/OpenAI + correos o tareas repetitivas como si fuera un tema nuevo.

Busca variedad real en:

- herramienta principal;
- problema que se resuelve;
- caso practico;
- publico;
- resultado final;
- tipo de tutorial;
- comparativa o experimento.

Para cada idea proporciona:

- titulo: titulo atractivo, claro y especifico;
- gancho: frase inicial para captar la atencion;
- formato: "video largo" o "short";
- duracion_minutos: numero entero;
- palabra_clave: termino principal para SEO;
- angulo: enfoque diferenciador;
- potencial: "alto", "medio" o "experimental".

REGLAS:

1. No repitas una herramienta principal recientemente utilizada,
   salvo que el objetivo y el caso practico sean claramente distintos.
2. No cambies solamente ChatGPT por OpenAI, Claude o Gemini para
   presentar el mismo flujo como una idea diferente.
3. No repitas automatizacion de correo si ya existe un tutorial
   reciente sobre ese flujo.
4. Prioriza diversidad real del catalogo.
5. Combina tutoriales, comparativas, experimentos y herramientas.
6. No inventes noticias ni funciones actuales.
7. Evita titulos enga?osos.
8. Devuelve solamente el JSON solicitado.
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

        return {
            "generado_en": datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            ),
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
