from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.ai.gemini_client import GeminiClient
from autotube.content.script_generator import SCRIPT_SCHEMA
from autotube.content.script_validator import (
    contar_palabras,
    localizar_guion,
)


def contar_palabras_guion(guion: dict[str, Any]) -> int:
    """Cuenta las palabras narradas de todo el guion."""
    partes = [
        str(guion.get("introduccion", "")),
    ]

    escenas = guion.get("escenas", [])

    if isinstance(escenas, list):
        for escena in escenas:
            if isinstance(escena, dict):
                partes.append(
                    str(escena.get("narracion", ""))
                )

    partes.append(
        str(guion.get("llamada_accion", ""))
    )

    return contar_palabras(
        "\n".join(
            parte
            for parte in partes
            if parte.strip()
        )
    )


def cargar_guion_para_correccion(
    data_dir: Path,
    archivo: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Carga el guion que debe corregirse."""
    ruta = localizar_guion(
        data_dir=data_dir,
        archivo=archivo,
    )

    contenido = json.loads(
        ruta.read_text(encoding="utf-8")
    )

    guion = contenido.get("guion")

    if not isinstance(guion, dict):
        raise RuntimeError(
            "El archivo no contiene un guion válido."
        )

    return contenido, ruta


class ReparadorGuiones:
    """Expande y corrige guiones cuya narración es demasiado corta."""

    def __init__(
        self,
        cliente: GeminiClient | None = None,
    ) -> None:
        self.cliente = cliente or GeminiClient()

    def corregir(
        self,
        contenido: dict[str, Any],
        palabras_por_minuto: int = 145,
    ) -> dict[str, Any]:
        """Corrige la duración real del guion."""
        if palabras_por_minuto < 100 or palabras_por_minuto > 220:
            raise ValueError(
                "Las palabras por minuto deben estar entre 100 y 220."
            )

        guion_original = contenido.get("guion")

        if not isinstance(guion_original, dict):
            raise RuntimeError(
                "No se encontró un guion válido para corregir."
            )

        escenas_originales = guion_original.get("escenas")

        if not isinstance(escenas_originales, list):
            raise RuntimeError(
                "El guion original no contiene escenas válidas."
            )

        try:
            minutos_objetivo = int(
                guion_original.get(
                    "duracion_estimada_minutos",
                    0,
                )
            )
        except (TypeError, ValueError):
            minutos_objetivo = 0

        if minutos_objetivo <= 0:
            raise ValueError(
                "El guion no contiene una duración objetivo válida."
            )

        palabras_objetivo_total = (
            round(minutos_objetivo * palabras_por_minuto * 1.04)
        )

        plan_escenas: list[dict[str, Any]] = []

        for posicion, escena in enumerate(
            escenas_originales,
            start=1,
        ):
            if not isinstance(escena, dict):
                continue

            try:
                duracion = int(
                    escena.get("duracion_segundos", 0)
                )
            except (TypeError, ValueError):
                duracion = 0

            narracion = str(
                escena.get("narracion", "")
            )

            palabras_objetivo = max(
                25,
                round(
                    duracion
                    / 60
                    * palabras_por_minuto
                    * 1.04
                ),
            )

            plan_escenas.append(
                {
                    "numero": escena.get(
                        "numero",
                        posicion,
                    ),
                    "titulo": escena.get(
                        "titulo",
                        f"Escena {posicion}",
                    ),
                    "duracion_segundos": duracion,
                    "palabras_actuales": contar_palabras(
                        narracion
                    ),
                    "palabras_objetivo": palabras_objetivo,
                }
            )

        guion_json = json.dumps(
            guion_original,
            ensure_ascii=False,
            indent=2,
        )

        plan_json = json.dumps(
            plan_escenas,
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""
Actua como editor profesional de documentales de divulgacion
sobre inteligencia artificial para el canal NEXON IA.

El siguiente documental declara una duracion de
{minutos_objetivo} minutos, pero su narracion es demasiado corta.

GUION ACTUAL:
{guion_json}

PLAN DE PALABRAS POR ESCENA:
{plan_json}

OBJETIVO TOTAL:
Aproximadamente {palabras_objetivo_total} palabras narradas,
calculadas a {palabras_por_minuto} palabras por minuto.

INSTRUCCIONES OBLIGATORIAS:

1. Conserva el tema, titulo y numero de escenas.
2. Conserva exactamente la duracion en segundos de cada escena.
3. Amplia cada escena hasta aproximarse a sus palabras objetivo.
4. Cada escena puede variar como maximo un 10 por ciento.
5. Mantiene un estilo documental, narrativo y divulgativo.
6. Agrega contexto historico, explicaciones, ejemplos,
   consecuencias, contrastes y reflexiones relevantes.
7. Utiliza transiciones naturales entre escenas.
8. No a?adas tutoriales, instalaciones, configuraciones,
   pasos detallados ni instrucciones sobre interfaces.
9. No ordenes abrir, instalar, pulsar o configurar programas.
10. No rellenes el texto con repeticiones.
11. No inventes estadisticas, estudios, noticias, precios o citas.
12. Mantiene los recursos visuales relacionados con la narracion
    y compatibles con videos de stock, imagenes de stock y texto animado.
13. Conserva una conclusion clara y una llamada a la accion breve.
14. Devuelve exclusivamente el JSON solicitado.

El resultado debe contener narracion suficiente para aproximarse
realmente a la duracion declarada.
""".strip()

        guion_corregido = self.cliente.generar_json(
            prompt=prompt,
            schema=SCRIPT_SCHEMA,
        )

        escenas_corregidas = guion_corregido.get(
            "escenas"
        )

        if not isinstance(escenas_corregidas, list):
            raise RuntimeError(
                "Gemini no devolvió escenas válidas."
            )

        if len(escenas_corregidas) != len(
            escenas_originales
        ):
            raise RuntimeError(
                "La corrección cambió el número de escenas."
            )

        for posicion, (
            escena_corregida,
            escena_original,
        ) in enumerate(
            zip(
                escenas_corregidas,
                escenas_originales,
            ),
            start=1,
        ):
            if not isinstance(escena_corregida, dict):
                raise RuntimeError(
                    f"La escena corregida {posicion} no es válida."
                )

            if not isinstance(escena_original, dict):
                continue

            escena_corregida["numero"] = (
                escena_original.get(
                    "numero",
                    posicion,
                )
            )

            escena_corregida["duracion_segundos"] = (
                escena_original.get(
                    "duracion_segundos",
                    0,
                )
            )

        palabras_antes = contar_palabras_guion(
            guion_original
        )

        palabras_despues = contar_palabras_guion(
            guion_corregido
        )

        return {
            "generado_en": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "modelo": self.cliente.last_model_used,
            "idioma": contenido.get(
                "idioma",
                "español",
            ),
            "idea_original": contenido.get(
                "idea_original",
                {},
            ),
            "correccion": {
                "palabras_por_minuto": palabras_por_minuto,
                "palabras_objetivo": palabras_objetivo_total,
                "palabras_antes": palabras_antes,
                "palabras_despues": palabras_despues,
                "archivo_original": contenido.get(
                    "generado_en",
                    "",
                ),
            },
            "guion": guion_corregido,
        }

    def guardar(
        self,
        resultado: dict[str, Any],
        data_dir: Path,
    ) -> Path:
        """Guarda el guion corregido sin reemplazar el original."""
        scripts_dir = data_dir / "scripts"
        scripts_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        marca_tiempo = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        ruta = (
            scripts_dir
            / f"guion_corregido_{marca_tiempo}.json"
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