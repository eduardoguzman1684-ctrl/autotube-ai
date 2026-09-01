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


class GeneradorMetadataYouTube:
    """Genera automáticamente título, descripción, tags y capítulos."""

    def __init__(
        self,
        project_root: Path,
        cliente: GeminiClient | None = None,
        channel_slug: str = DEFAULT_CHANNEL,
    ) -> None:
        self.project_root = Path(project_root)
        self.cliente = cliente or GeminiClient()
        self.channel_slug = normalize_channel_slug(channel_slug)
        self.profile = channel_profile(self.channel_slug)

    def _latest(self, *patterns: str) -> Path:
        candidatos: list[Path] = []
        for pattern in patterns:
            candidatos.extend(self.project_root.glob(pattern))
        if not candidatos:
            raise FileNotFoundError(
                "No se encontró ningún archivo para: " + ", ".join(patterns)
            )
        return max(candidatos, key=lambda p: p.stat().st_mtime)

    @staticmethod
    def _cargar_json(ruta: Path) -> dict[str, Any]:
        data = json.loads(ruta.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError(f"JSON inválido: {ruta}")
        return data

    @staticmethod
    def _timestamp(segundos: float) -> str:
        total = max(0, int(segundos))
        horas, resto = divmod(total, 3600)
        minutos, segundos = divmod(resto, 60)
        if horas:
            return f"{horas}:{minutos:02d}:{segundos:02d}"
        return f"{minutos:02d}:{segundos:02d}"

    def _capitulos(self, plan: dict[str, Any]) -> list[str]:
        raiz = plan.get("plan_visual", plan)
        segmentos = raiz.get("segmentos", [])
        capitulos: list[str] = []
        for indice, segmento in enumerate(segmentos, start=1):
            if not isinstance(segmento, dict):
                continue
            clips = segmento.get("clips") or []
            if not clips:
                continue
            primer_clip = clips[0]
            inicio = primer_clip.get("inicio_segundos", primer_clip.get("inicio", 0))
            try:
                inicio = float(inicio)
            except (TypeError, ValueError):
                inicio = 0.0
            titulo = (
                segmento.get("titulo")
                or segmento.get("nombre")
                or segmento.get("seccion")
                or f"Sección {indice}"
            )
            capitulos.append(f"{self._timestamp(inicio)} {str(titulo).strip()}")
        if capitulos and not capitulos[0].startswith(("00:00 ", "0:00 ")):
            capitulos.insert(0, "00:00 Introducción")
        return capitulos

    @staticmethod
    def _tags_limpios(tags: list[Any]) -> list[str]:
        salida: list[str] = []
        vistos: set[str] = set()
        caracteres = 0
        for tag in tags:
            texto = str(tag).strip().strip("#")
            if not texto:
                continue
            clave = texto.casefold()
            if clave in vistos:
                continue
            if caracteres + len(texto) > 430:
                break
            vistos.add(clave)
            salida.append(texto)
            caracteres += len(texto) + 1
            if len(salida) >= 18:
                break
        return salida

    def generar(self) -> tuple[dict[str, Any], Path]:
        guion_path = self._latest(
            "data/scripts/guion_corregido_*.json",
            "data/scripts/guion_*.json",
        )
        plan_path = self._latest(
            "data/visual_plans/plan_visual_*.json",
            "data/visual_plans/plan_visual*.json",
        )
        guion = self._cargar_json(guion_path)
        plan = self._cargar_json(plan_path)

        script_channel = normalize_channel_slug(
            str(
                guion.get(
                    "channel_slug",
                    DEFAULT_CHANNEL,
                )
            )
        )

        if script_channel != self.channel_slug:
            raise RuntimeError(
                "BLOQUEO EDITORIAL: el guion mas reciente pertenece "
                f"a {script_channel}, no a {self.channel_slug}."
            )

        capitulos = self._capitulos(plan)

        contexto = json.dumps(guion, ensure_ascii=False)[:24000]
        contexto_editorial = editorial_prompt(self.channel_slug)

        prompt = f"""
Eres especialista en packaging y SEO de YouTube para un canal en español.

PERFIL DEL CANAL:
{contexto_editorial}

Crea los metadatos del video usando SOLO el contenido real del guion.

GUION:
{contexto}

REGLAS:
- Título en español, máximo 95 caracteres.
- Atractivo, claro y sin clickbait engañoso.
- Descripción útil y orientada a lo que el espectador aprenderá.
- Incluye esta llamada a la accion o una version breve equivalente:
  {self.profile['cta']}
- No inventes funciones, precios, resultados ni cifras.
- No escribas capítulos: el sistema los añadirá con tiempos reales.
- Genera entre 10 y 18 etiquetas relevantes.
"""

        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "description", "tags"],
        }

        resultado = self.cliente.generar_json(prompt=prompt, schema=schema)
        titulo = str(resultado.get("title", "")).strip()[:100]
        descripcion_base = str(resultado.get("description", "")).strip()
        tags = self._tags_limpios(resultado.get("tags", []))

        if not titulo:
            raise RuntimeError("Gemini no generó un título válido.")
        if not descripcion_base:
            raise RuntimeError("Gemini no generó una descripción válida.")

        descripcion = descripcion_base
        if capitulos:
            descripcion += "\n\nCAPÍTULOS\n\n" + "\n".join(capitulos)

        metadata = {
            "channel_slug": self.channel_slug,
            "channel_name": self.profile["display_name"],
            "title": titulo,
            "description": descripcion[:5000],
            "tags": tags,
            "category_id": self.profile["category_id"],
            "language": "es",
            "privacy": "private",
            "chapters": capitulos,
            "source_script": str(guion_path),
            "source_visual_plan": str(plan_path),
        }

        output_dir = self.project_root / "data" / "publish"
        output_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = output_dir / "metadata.json"
        texto = json.dumps(metadata, ensure_ascii=False, indent=2)
        metadata_path.write_text(texto, encoding="utf-8")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        historial = output_dir / f"metadata_{timestamp}.json"
        historial.write_text(texto, encoding="utf-8")

        return metadata, metadata_path
