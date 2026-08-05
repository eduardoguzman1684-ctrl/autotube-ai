from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.ai.gemini_client import GeminiClient


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
    ) -> dict[str, Any]:
        """Convierte una idea en un guion estructurado."""
        if not idea:
            raise ValueError("La idea no puede estar vacía.")

        idioma_limpio = idioma.strip()

        if not idioma_limpio:
            raise ValueError("El idioma no puede estar vacío.")

        idea_json = json.dumps(
            idea,
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""
Actúa como guionista profesional de YouTube especializado en
inteligencia artificial, automatización, marketing digital,
productividad y negocios digitales.

Convierte la siguiente idea en un guion original, educativo,
dinámico y preparado para producción automática.

IDEA:
{idea_json}

IDIOMA:
{idioma_limpio}

REQUISITOS:

1. El gancho inicial debe captar atención durante los primeros segundos.
2. La introducción debe explicar claramente lo que aprenderá el espectador.
3. Divide el contenido en escenas ordenadas.
4. Cada escena debe incluir:
   - narración completa;
   - recursos visuales sugeridos;
   - texto breve para mostrar en pantalla;
   - duración aproximada en segundos.
5. Para videos largos, utiliza entre 7 y 12 escenas.
6. Para Shorts, utiliza entre 3 y 5 escenas.
7. No inventes estadísticas, noticias, precios ni funciones actuales.
8. No afirmes haber probado herramientas si no existe evidencia.
9. Evita promesas irreales de ingresos.
10. La narración debe sonar natural y no repetitiva.
11. Incluye una llamada a la acción breve.
12. Genera una descripción optimizada para YouTube.
13. Genera entre 8 y 15 etiquetas relacionadas.
14. Devuelve solamente el JSON solicitado.
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