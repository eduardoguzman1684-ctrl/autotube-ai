from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.ai.gemini_client import GeminiClient
from autotube.content.script_validator import localizar_guion


PLAN_VISUAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "titulo": {
            "type": "string",
        },
        "estilo_visual_general": {
            "type": "string",
        },
        "resolucion": {
            "type": "string",
        },
        "segmentos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                    },
                    "numero": {
                        "type": "integer",
                    },
                    "titulo": {
                        "type": "string",
                    },
                    "duracion_audio_segundos": {
                        "type": "number",
                    },
                    "clips": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "orden": {
                                    "type": "integer",
                                },
                                "duracion_segundos": {
                                    "type": "number",
                                },
                                "tipo_recurso": {
                                    "type": "string",
                                    "enum": [
                                        "video_stock",
                                        "imagen_stock",
                                        "captura_interfaz",
                                        "grafico",
                                        "texto_animado",
                                    ],
                                },
                                "descripcion": {
                                    "type": "string",
                                },
                                "busqueda_es": {
                                    "type": "string",
                                },
                                "busqueda_en": {
                                    "type": "string",
                                },
                                "movimiento": {
                                    "type": "string",
                                },
                                "texto_pantalla": {
                                    "type": "string",
                                },
                            },
                            "required": [
                                "orden",
                                "duracion_segundos",
                                "tipo_recurso",
                                "descripcion",
                                "busqueda_es",
                                "busqueda_en",
                                "movimiento",
                                "texto_pantalla",
                            ],
                        },
                    },
                },
                "required": [
                    "tipo",
                    "numero",
                    "titulo",
                    "duracion_audio_segundos",
                    "clips",
                ],
            },
        },
        "notas_edicion": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
    },
    "required": [
        "titulo",
        "estilo_visual_general",
        "resolucion",
        "segmentos",
        "notas_edicion",
    ],
}


def localizar_manifiesto(
    output_dir: Path,
    archivo: Path | None = None,
) -> Path:
    """Localiza el manifiesto de audio más reciente."""
    if archivo is not None:
        ruta = archivo.expanduser().resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe el manifiesto indicado: {ruta}"
            )

        return ruta

    archivos = sorted(
        (output_dir / "audio").glob(
            "narracion_*/manifest.json"
        ),
        key=lambda elemento: elemento.stat().st_mtime,
        reverse=True,
    )

    if not archivos:
        raise FileNotFoundError(
            "No se encontró ningún manifiesto de audio."
        )

    return archivos[0]


def cargar_contexto_visual(
    data_dir: Path,
    output_dir: Path,
    archivo_guion: Path | None = None,
    archivo_manifiesto: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    """Carga el guion y su manifiesto de audio."""
    ruta_manifiesto = localizar_manifiesto(
        output_dir=output_dir,
        archivo=archivo_manifiesto,
    )

    manifiesto = json.loads(
        ruta_manifiesto.read_text(encoding="utf-8")
    )

    if archivo_guion is not None:
        ruta_guion = localizar_guion(
            data_dir=data_dir,
            archivo=archivo_guion,
        )
    else:
        origen = manifiesto.get("guion_origen")

        if origen and Path(str(origen)).is_file():
            ruta_guion = Path(str(origen)).resolve()
        else:
            ruta_guion = localizar_guion(
                data_dir=data_dir,
            )

    contenido_guion = json.loads(
        ruta_guion.read_text(encoding="utf-8")
    )

    guion = contenido_guion.get("guion")

    if not isinstance(guion, dict):
        raise RuntimeError(
            "El archivo no contiene un guion válido."
        )

    segmentos = manifiesto.get("segmentos")

    if not isinstance(segmentos, list) or not segmentos:
        raise RuntimeError(
            "El manifiesto no contiene segmentos de audio."
        )

    return (
        contenido_guion,
        manifiesto,
        ruta_guion,
        ruta_manifiesto,
    )


def ajustar_duraciones_clips(
    clips: list[dict[str, Any]],
    duracion_total: float,
) -> list[dict[str, Any]]:
    """Ajusta los clips para coincidir con el audio real."""
    if not clips:
        return []

    pesos: list[float] = []

    for clip in clips:
        try:
            valor = float(
                clip.get("duracion_segundos", 0)
            )
        except (TypeError, ValueError):
            valor = 0

        pesos.append(valor if valor > 0 else 1.0)

    suma_pesos = sum(pesos)

    duraciones = [
        round(
            duracion_total * peso / suma_pesos,
            2,
        )
        for peso in pesos
    ]

    diferencia = round(
        duracion_total - sum(duraciones),
        2,
    )

    duraciones[-1] = round(
        max(0.1, duraciones[-1] + diferencia),
        2,
    )

    resultado: list[dict[str, Any]] = []

    for indice, (clip, duracion) in enumerate(
        zip(clips, duraciones),
        start=1,
    ):
        copia = dict(clip)
        copia["orden"] = indice
        copia["duracion_segundos"] = duracion
        resultado.append(copia)

    return resultado


class PlanificadorVisual:
    """Crea un plan visual sincronizado con la narración."""

    def __init__(
        self,
        cliente: GeminiClient | None = None,
    ) -> None:
        self.cliente = cliente or GeminiClient()

    def construir_contexto_segmentos(
        self,
        guion: dict[str, Any],
        manifiesto: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Relaciona cada audio con su texto y sugerencias visuales."""
        escenas_guion = guion.get("escenas", [])

        mapa_escenas: dict[int, dict[str, Any]] = {}

        if isinstance(escenas_guion, list):
            for posicion, escena in enumerate(
                escenas_guion,
                start=1,
            ):
                if not isinstance(escena, dict):
                    continue

                try:
                    numero = int(
                        escena.get("numero", posicion)
                    )
                except (TypeError, ValueError):
                    numero = posicion

                mapa_escenas[numero] = escena

        contexto: list[dict[str, Any]] = []

        for segmento in manifiesto.get(
            "segmentos",
            [],
        ):
            if not isinstance(segmento, dict):
                continue

            tipo = str(
                segmento.get("tipo", "escena")
            )

            try:
                numero = int(
                    segmento.get("numero", 0)
                )
            except (TypeError, ValueError):
                numero = 0

            duracion = float(
                segmento.get(
                    "duracion_real_segundos",
                    0,
                )
            )

            cantidad_clips = max(
                2,
                min(
                    10,
                    round(duracion / 10),
                ),
            )

            if tipo == "introduccion":
                texto = str(
                    guion.get("introduccion", "")
                )

                sugerencias = []
                texto_pantalla = ""

            elif tipo == "cta":
                texto = str(
                    guion.get("llamada_accion", "")
                )

                sugerencias = [
                    "Animación de suscripción",
                    "Identidad visual del canal Nexo IA",
                ]

                texto_pantalla = "Suscríbete a Nexo IA"

            else:
                escena = mapa_escenas.get(
                    numero,
                    {},
                )

                texto = str(
                    escena.get(
                        "narracion",
                        segmento.get("texto", ""),
                    )
                )

                sugerencias = escena.get(
                    "visuales",
                    [],
                )

                texto_pantalla = str(
                    escena.get(
                        "texto_pantalla",
                        "",
                    )
                )

            contexto.append(
                {
                    "tipo": tipo,
                    "numero": numero,
                    "titulo": segmento.get(
                        "titulo",
                        "Sin título",
                    ),
                    "duracion_audio_segundos": duracion,
                    "cantidad_clips_recomendada": cantidad_clips,
                    "narracion": texto,
                    "visuales_originales": sugerencias,
                    "texto_pantalla_original": texto_pantalla,
                }
            )

        return contexto

    def generar(
        self,
        contenido_guion: dict[str, Any],
        manifiesto: dict[str, Any],
    ) -> dict[str, Any]:
        """Genera el plan mediante Gemini."""
        guion = contenido_guion["guion"]

        contexto = self.construir_contexto_segmentos(
            guion=guion,
            manifiesto=manifiesto,
        )

        contexto_json = json.dumps(
            contexto,
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""
Actúa como director audiovisual y editor profesional de videos
educativos para YouTube.

Debes crear el plan visual completo para el siguiente video del canal
Nexo IA.

TÍTULO:
{guion.get("titulo", "Sin título")}

SEGMENTOS SINCRONIZADOS CON EL AUDIO:
{contexto_json}

INSTRUCCIONES OBLIGATORIAS:

1. Conserva exactamente el mismo número y orden de segmentos.
2. Usa la duración real de audio indicada para cada segmento.
3. Crea aproximadamente la cantidad de clips recomendada.
4. Cada clip debe representar una parte específica de la narración.
5. Alterna videos de archivo, imágenes, gráficos, texto animado y
   capturas de interfaz cuando sea apropiado.
6. Evita mantener una sola imagen demasiado tiempo.
7. Las búsquedas en español e inglés deben ser breves y concretas.
8. Para herramientas digitales, prioriza capturas genéricas de interfaz
   y no inventes botones o funciones.
9. No uses marcas registradas como decoración sin relación con el tema.
10. No propongas descargar contenido protegido de otros canales.
11. En el campo movimiento indica acciones como:
    zoom lento, paneo horizontal, acercamiento, desplazamiento vertical,
    corte directo o sin movimiento.
12. El texto en pantalla debe ser corto. Puede quedar vacío cuando no
    sea necesario.
13. El resultado debe ser apropiado para video horizontal 1920x1080.
14. Devuelve exclusivamente el JSON solicitado.
""".strip()

        resultado = self.cliente.generar_json(
            prompt=prompt,
            schema=PLAN_VISUAL_SCHEMA,
        )

        segmentos_generados = resultado.get(
            "segmentos"
        )

        if not isinstance(
            segmentos_generados,
            list,
        ):
            raise RuntimeError(
                "Gemini no devolvió segmentos visuales válidos."
            )

        if len(segmentos_generados) != len(contexto):
            raise RuntimeError(
                "El número de segmentos visuales no coincide "
                "con el manifiesto de audio."
            )

        segmentos_finales: list[dict[str, Any]] = []

        for original, generado in zip(
            contexto,
            segmentos_generados,
        ):
            if not isinstance(generado, dict):
                raise RuntimeError(
                    "Se recibió un segmento visual inválido."
                )

            clips = generado.get("clips", [])

            if not isinstance(clips, list) or not clips:
                raise RuntimeError(
                    f"El segmento '{original['titulo']}' "
                    "no contiene clips."
                )

            duracion = float(
                original["duracion_audio_segundos"]
            )

            generado["tipo"] = original["tipo"]
            generado["numero"] = original["numero"]
            generado["titulo"] = original["titulo"]
            generado["duracion_audio_segundos"] = duracion
            generado["clips"] = ajustar_duraciones_clips(
                clips=clips,
                duracion_total=duracion,
            )

            segmentos_finales.append(generado)

        resultado["titulo"] = guion.get(
            "titulo",
            resultado.get("titulo", "Sin título"),
        )

        resultado["resolucion"] = "1920x1080"
        resultado["segmentos"] = segmentos_finales

        return {
            "generado_en": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "modelo": self.cliente.last_model_used,
            "voz": manifiesto.get("voz", ""),
            "duracion_total_segundos": manifiesto.get(
                "duracion_total_segundos",
                0,
            ),
            "plan_visual": resultado,
        }

    def guardar(
        self,
        resultado: dict[str, Any],
        data_dir: Path,
    ) -> Path:
        """Guarda el plan visual."""
        carpeta = data_dir / "visual_plans"

        carpeta.mkdir(
            parents=True,
            exist_ok=True,
        )

        marca_tiempo = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        ruta = (
            carpeta
            / f"plan_visual_{marca_tiempo}.json"
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