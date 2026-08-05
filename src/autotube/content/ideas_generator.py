from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.ai.gemini_client import GeminiClient


NICHO_PREDETERMINADO = (
    "inteligencia artificial, automatización, herramientas digitales, "
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


class GeneradorIdeas:
    """Genera ideas estructuradas para videos de YouTube."""

    def __init__(self, cliente: GeminiClient | None = None) -> None:
        self.cliente = cliente or GeminiClient()

    def generar(
        self,
        nicho: str = NICHO_PREDETERMINADO,
        cantidad: int = 5,
        idioma: str = "español",
    ) -> dict[str, Any]:
        """Genera una colección de ideas utilizando Gemini."""
        nicho_limpio = nicho.strip()
        idioma_limpio = idioma.strip()

        if not nicho_limpio:
            raise ValueError("El nicho no puede estar vacío.")

        if cantidad < 1 or cantidad > 20:
            raise ValueError("La cantidad debe estar entre 1 y 20.")

        prompt = f"""
Actúa como estratega experto en crecimiento de canales de YouTube.

Genera exactamente {cantidad} ideas originales para un canal internacional
del nicho: {nicho_limpio}.

Idioma de salida: {idioma_limpio}.

El público está formado por emprendedores, creadores, estudiantes,
freelancers y personas interesadas en inteligencia artificial.

Para cada idea proporciona:

- titulo: título atractivo, claro y específico;
- gancho: frase inicial para captar la atención;
- formato: "video largo" o "short";
- duracion_minutos: duración recomendada como número entero;
- palabra_clave: término principal para SEO;
- angulo: enfoque diferenciador del contenido;
- potencial: "alto", "medio" o "experimental".

Reglas:

- No inventes noticias ni afirmes que algo está ocurriendo actualmente.
- Prioriza temas útiles, educativos, comerciales y con potencial evergreen.
- Evita títulos engañosos.
- No repitas ideas.
- Combina tutoriales, comparativas, experimentos y herramientas.
- Devuelve solamente la estructura JSON solicitada.
""".strip()

        respuesta = self.cliente.generar_json(
            prompt=prompt,
            schema=IDEAS_SCHEMA,
        )

        ideas = respuesta.get("ideas")

        if not isinstance(ideas, list) or not ideas:
            raise RuntimeError(
                "Gemini no devolvió una lista válida de ideas."
            )

        return {
            "generado_en": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "nicho": nicho_limpio,
            "idioma": idioma_limpio,
            "modelo": self.cliente.last_model_used,
            "cantidad": len(ideas[:cantidad]),
            "ideas": ideas[:cantidad],
        }

    def guardar(
        self,
        resultado: dict[str, Any],
        data_dir: Path,
    ) -> Path:
        """Guarda las ideas como un archivo JSON."""
        ideas_dir = data_dir / "ideas"
        ideas_dir.mkdir(parents=True, exist_ok=True)

        marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta = ideas_dir / f"ideas_{marca_tiempo}.json"

        ruta.write_text(
            json.dumps(
                resultado,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return ruta