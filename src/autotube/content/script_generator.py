from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.ai.gemini_client import GeminiClient
from autotube.content.channel_profiles import (
    DEFAULT_CHANNEL,
    channel_profile,
    editorial_prompt,
    normalize_channel_slug,
)


SCRIPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "objetivo": {"type": "string"},
        "publico_objetivo": {"type": "string"},
        "formato": {"type": "string"},
        "duracion_estimada_minutos": {"type": "integer"},
        "palabra_clave": {"type": "string"},
        "gancho_inicial": {"type": "string"},
        "introduccion": {"type": "string"},
        "escenas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "numero": {"type": "integer"},
                    "titulo": {"type": "string"},
                    "narracion": {"type": "string"},
                    "visuales": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "texto_pantalla": {"type": "string"},
                    "duracion_segundos": {"type": "integer"},
                },
                "required": [
                    "numero",
                    "titulo",
                    "narracion",
                    "visuales",
                    "texto_pantalla",
                    "duracion_segundos",
                ],
            },
        },
        "llamada_accion": {"type": "string"},
        "descripcion_youtube": {"type": "string"},
        "etiquetas": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "titulo",
        "objetivo",
        "publico_objetivo",
        "formato",
        "duracion_estimada_minutos",
        "palabra_clave",
        "gancho_inicial",
        "introduccion",
        "escenas",
        "llamada_accion",
        "descripcion_youtube",
        "etiquetas",
    ],
}


def cargar_idea(
    data_dir: Path,
    indice: int = 1,
    archivo: Path | None = None,
    channel_slug: str | None = None,
) -> tuple[dict[str, Any], Path]:
    """Carga una idea desde un archivo específico o desde el más reciente."""
    if indice < 1:
        raise ValueError("El índice de la idea debe ser 1 o mayor.")

    if archivo is None:
        ideas_dir = data_dir / "ideas"
        archivos = sorted(
            ideas_dir.glob("ideas_*.json"),
            key=lambda ruta: ruta.stat().st_mtime,
            reverse=True,
        )

        if not archivos:
            raise FileNotFoundError(
                "No existen archivos de ideas. Ejecuta primero "
                "'autotube ideas'."
            )

        ruta = archivos[0]
    else:
        ruta = archivo.expanduser()

        if not ruta.is_absolute():
            ruta = Path.cwd() / ruta

        ruta = ruta.resolve()

    if not ruta.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo de ideas: {ruta}"
        )

    contenido = json.loads(ruta.read_text(encoding="utf-8"))

    if channel_slug is not None:
        expected_channel = normalize_channel_slug(channel_slug)
        source_channel = normalize_channel_slug(
            str(
                contenido.get(
                    "channel_slug",
                    DEFAULT_CHANNEL,
                )
            )
        )

        if source_channel != expected_channel:
            raise RuntimeError(
                "BLOQUEO EDITORIAL: el archivo de ideas pertenece "
                f"a {source_channel}, no a {expected_channel}."
            )

    ideas = contenido.get("ideas")

    if not isinstance(ideas, list) or not ideas:
        raise RuntimeError(
            "El archivo seleccionado no contiene una lista válida de ideas."
        )

    if indice > len(ideas):
        raise IndexError(
            f"El archivo contiene {len(ideas)} ideas y solicitaste "
            f"la número {indice}."
        )

    idea = ideas[indice - 1]

    if not isinstance(idea, dict):
        raise RuntimeError("La idea seleccionada no tiene un formato válido.")

    return idea, ruta


class GeneradorGuiones:
    """Genera guiones estructurados para videos de YouTube."""

    def __init__(self, cliente: GeminiClient | None = None) -> None:
        self.cliente = cliente or GeminiClient()

    def generar(
        self,
        idea: dict[str, Any],
        idioma: str = "español",
        channel_slug: str = DEFAULT_CHANNEL,
    ) -> dict[str, Any]:
        """Convierte una idea en un guion estructurado."""
        if not idea:
            raise ValueError("La idea no puede estar vacía.")

        idioma_limpio = idioma.strip()
        channel_slug = normalize_channel_slug(channel_slug)
        profile = channel_profile(channel_slug)

        if not idioma_limpio:
            raise ValueError("El idioma no puede estar vacío.")

        idea_json = json.dumps(
            idea,
            ensure_ascii=False,
            indent=2,
        )

        contexto_editorial = editorial_prompt(
            channel_slug
        )

        prompt = f"""
Actua como guionista profesional de videos documentales educativos
para YouTube.

PERFIL DEL CANAL:
{contexto_editorial}

Convierte la siguiente idea en un documental original, educativo,
narrativo, riguroso y visualmente atractivo.

IDEA:
{idea_json}

IDIOMA:
{idioma_limpio}

DURACION OBLIGATORIA:

- duracion objetivo: 15 minutos;
- narracion total: entre 2100 y 2250 palabras;
- velocidad prevista: 145 palabras por minuto;
- suma aproximada de las escenas: 900 segundos.

LLAMADA A LA ACCION DEL CANAL:
{profile['cta']}

REQUISITOS:

1. Escribe un gancho intrigante para los primeros 20 segundos.
2. Presenta una pregunta central que se responda progresivamente.
3. Divide el documental en entre 10 y 12 escenas ordenadas.
4. Desarrolla el tema mediante: {profile['script_development']}.
5. Cada escena debe incluir narracion completa, recursos visuales
   sugeridos, texto breve en pantalla y duracion en segundos.
6. Sugiere recursos que puedan encontrarse como video_stock,
   imagen_stock, grafico o texto_animado.
7. No escribas tutoriales, instalaciones, configuraciones,
   instrucciones paso a paso ni recorridos por interfaces.
8. No ordenes al espectador abrir, instalar, pulsar o configurar nada.
9. Explica los conceptos para publico general con ejemplos claros.
10. Utiliza transiciones naturales y evita repetir informacion.
11. No inventes estadisticas, investigaciones, noticias o citas.
12. Si no existe certeza sobre una cifra, explicala sin dato numerico.
13. Mantiene un tono documental, humano, reflexivo y dinamico.
14. Incluye una conclusion que responda la pregunta central.
15. Incluye una llamada a la accion breve al final.
16. Genera descripcion para YouTube y entre 8 y 15 etiquetas.
17. Devuelve solamente el JSON solicitado.
18. Respeta estrictamente el perfil del canal y no introduzcas la
    identidad, los temas ni la llamada a la accion de otro canal.
19. Para psicologia, ofrece educacion general basada en evidencia:
    no diagnostiques, no prescribas y no sustituyas ayuda profesional.
""".strip()

        guion = self.cliente.generar_json(
            prompt=prompt,
            schema=SCRIPT_SCHEMA,
        )

        escenas = guion.get("escenas")

        if not isinstance(escenas, list) or not escenas:
            raise RuntimeError(
                "Gemini no devolvió una lista válida de escenas."
            )

        return {
            "generado_en": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "modelo": self.cliente.last_model_used,
            "channel_slug": channel_slug,
            "channel_name": profile["display_name"],
            "idioma": idioma_limpio,
            "idea_original": idea,
            "guion": guion,
        }

    def guardar(
        self,
        resultado: dict[str, Any],
        data_dir: Path,
    ) -> Path:
        """Guarda el guion generado como JSON."""
        scripts_dir = data_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta = scripts_dir / f"guion_{marca_tiempo}.json"

        ruta.write_text(
            json.dumps(
                resultado,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return ruta
