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
                                "texto_narrado": {
                                    "type": "string",
                                },
                                "inicio_segundos": {
                                    "type": "number",
                                },
                                "final_segundos": {
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
                                "texto_narrado",
                                "inicio_segundos",
                                "final_segundos",
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


def crear_bloques_narracion(
    segmento: dict[str, Any],
    inicio_global: float,
    objetivo_segundos: float = 9.5,
) -> list[dict[str, Any]]:
    """
    Divide un segmento de voz en bloques temporales reales.

    Cada bloque representa exactamente la parte de la narraci?n
    que debe ilustrarse durante ese intervalo.
    """
    try:
        duracion = float(
            segmento.get(
                "duracion_real_segundos",
                0,
            )
        )
    except (TypeError, ValueError):
        duracion = 0.0

    if duracion <= 0:
        return []

    marcas_raw = segmento.get(
        "marcas_palabras",
        [],
    )

    marcas: list[dict[str, Any]] = []

    if isinstance(marcas_raw, list):
        for marca in marcas_raw:
            if not isinstance(marca, dict):
                continue

            palabra = str(
                marca.get("texto", "")
            ).strip()

            if not palabra:
                continue

            try:
                inicio = float(
                    marca.get(
                        "inicio_segundos",
                        0,
                    )
                )

                final = float(
                    marca.get(
                        "final_segundos",
                        inicio,
                    )
                )
            except (TypeError, ValueError):
                continue

            marcas.append(
                {
                    "texto": palabra,
                    "inicio": inicio,
                    "final": final,
                }
            )

    bloques: list[dict[str, Any]] = []

    if marcas:
        palabras_actuales: list[str] = []
        inicio_bloque = 0.0
        ultimo_final = 0.0

        for marca in marcas:
            palabras_actuales.append(
                marca["texto"]
            )

            ultimo_final = min(
                duracion,
                max(
                    ultimo_final,
                    float(marca["final"]),
                ),
            )

            duracion_actual = (
                ultimo_final
                - inicio_bloque
            )

            if duracion_actual >= objetivo_segundos:
                bloques.append(
                    {
                        "orden": len(bloques) + 1,
                        "inicio_relativo": round(
                            inicio_bloque,
                            3,
                        ),
                        "final_relativo": round(
                            ultimo_final,
                            3,
                        ),
                        "inicio_segundos": round(
                            inicio_global
                            + inicio_bloque,
                            3,
                        ),
                        "final_segundos": round(
                            inicio_global
                            + ultimo_final,
                            3,
                        ),
                        "duracion_segundos": round(
                            ultimo_final
                            - inicio_bloque,
                            3,
                        ),
                        "texto_narrado": " ".join(
                            palabras_actuales
                        ).strip(),
                    }
                )

                palabras_actuales = []
                inicio_bloque = ultimo_final

        if palabras_actuales:
            final_bloque = duracion

            bloques.append(
                {
                    "orden": len(bloques) + 1,
                    "inicio_relativo": round(
                        inicio_bloque,
                        3,
                    ),
                    "final_relativo": round(
                        final_bloque,
                        3,
                    ),
                    "inicio_segundos": round(
                        inicio_global
                        + inicio_bloque,
                        3,
                    ),
                    "final_segundos": round(
                        inicio_global
                        + final_bloque,
                        3,
                    ),
                    "duracion_segundos": round(
                        final_bloque
                        - inicio_bloque,
                        3,
                    ),
                    "texto_narrado": " ".join(
                        palabras_actuales
                    ).strip(),
                }
            )

        if bloques:
            # Garantiza cobertura exacta del segmento.
            bloques[0]["inicio_relativo"] = 0.0
            bloques[0]["inicio_segundos"] = round(
                inicio_global,
                3,
            )

            bloques[-1]["final_relativo"] = round(
                duracion,
                3,
            )

            bloques[-1]["final_segundos"] = round(
                inicio_global + duracion,
                3,
            )

            for bloque in bloques:
                bloque["duracion_segundos"] = round(
                    bloque["final_segundos"]
                    - bloque["inicio_segundos"],
                    3,
                )

            return bloques

    # --------------------------------------------------------
    # Respaldo para manifiestos antiguos
    # --------------------------------------------------------
    texto = str(
        segmento.get("texto_voz")
        or segmento.get("texto")
        or ""
    ).strip()

    palabras = texto.split()

    cantidad = max(
        1,
        round(
            duracion / objetivo_segundos
        ),
    )

    if not palabras:
        palabras = [""]

    for indice in range(cantidad):
        inicio_palabra = round(
            len(palabras)
            * indice
            / cantidad
        )

        final_palabra = round(
            len(palabras)
            * (indice + 1)
            / cantidad
        )

        inicio_relativo = (
            duracion
            * indice
            / cantidad
        )

        final_relativo = (
            duracion
            * (indice + 1)
            / cantidad
        )

        bloques.append(
            {
                "orden": indice + 1,
                "inicio_relativo": round(
                    inicio_relativo,
                    3,
                ),
                "final_relativo": round(
                    final_relativo,
                    3,
                ),
                "inicio_segundos": round(
                    inicio_global
                    + inicio_relativo,
                    3,
                ),
                "final_segundos": round(
                    inicio_global
                    + final_relativo,
                    3,
                ),
                "duracion_segundos": round(
                    final_relativo
                    - inicio_relativo,
                    3,
                ),
                "texto_narrado": " ".join(
                    palabras[
                        inicio_palabra:
                        final_palabra
                    ]
                ),
            }
        )

    return bloques



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
        """
        Construye segmentos visuales a partir del audio real.

        Cada segmento contiene bloques de aproximadamente
        8-12 segundos asociados a texto narrado concreto.
        """
        contexto: list[dict[str, Any]] = []
        inicio_global = 0.0

        for segmento in manifiesto.get(
            "segmentos",
            [],
        ):
            if not isinstance(segmento, dict):
                continue

            tipo = str(
                segmento.get(
                    "tipo",
                    "escena",
                )
            )

            try:
                numero = int(
                    segmento.get(
                        "numero",
                        0,
                    )
                )
            except (TypeError, ValueError):
                numero = 0

            try:
                duracion = float(
                    segmento.get(
                        "duracion_real_segundos",
                        0,
                    )
                )
            except (TypeError, ValueError):
                duracion = 0.0

            texto = str(
                segmento.get("texto_voz")
                or segmento.get("texto")
                or ""
            ).strip()

            bloques = crear_bloques_narracion(
                segmento=segmento,
                inicio_global=inicio_global,
            )

            contexto.append(
                {
                    "tipo": tipo,
                    "numero": numero,
                    "titulo": segmento.get(
                        "titulo",
                        "Sin t?tulo",
                    ),
                    "inicio_segmento_segundos": round(
                        inicio_global,
                        3,
                    ),
                    "duracion_audio_segundos": duracion,
                    "cantidad_clips_recomendada": len(
                        bloques
                    ),
                    "narracion": texto,
                    "bloques_narracion": bloques,
                }
            )

            inicio_global += duracion

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
Act?a como director audiovisual y editor profesional de videos
educativos para YouTube del canal NEXON IA.

T?TULO:
{guion.get("titulo", "Sin t?tulo")}

SEGMENTOS Y BLOQUES TEMPORIZADOS CON EL AUDIO REAL:
{contexto_json}

INSTRUCCIONES OBLIGATORIAS:

1. Conserva exactamente el mismo n?mero y orden de segmentos.
2. Cada segmento contiene "bloques_narracion" ya sincronizados.
3. Debes devolver EXACTAMENTE UN clip por cada bloque_narracion.
4. El clip debe ilustrar ?nicamente el texto_narrado de ese bloque.
5. Copia exactamente en cada clip:
   - texto_narrado
   - inicio_segundos
   - final_segundos
   - duracion_segundos
6. No combines frases pertenecientes a bloques diferentes.
7. Si el texto habla de Make, ChatGPT, OpenAI, Gmail, una API,
   m?dulos, escenarios, prompts, botones, formularios o paneles,
   prioriza "captura_interfaz" o "grafico".
8. Usa "video_stock" e "imagen_stock" principalmente para conceptos
   f?sicos, personas, oficinas, productividad, tiempo, negocios,
   servidores u otras escenas que realmente existan como B-roll.
9. No uses una persona mirando una computadora como sustituto
   gen?rico cuando la narraci?n describe una acci?n espec?fica
   dentro de un software.
10. Las b?squedas de stock deben describir exactamente el concepto
    visual del bloque. Usa entre 3 y 7 palabras clave concretas.
11. Evita b?squedas gen?ricas como:
    technology, artificial intelligence, computer, business.
12. Para busqueda_en usa t?rminos naturales en ingl?s adecuados
    para bancos de im?genes o videos.
13. Para busqueda_es usa t?rminos concretos equivalentes en espa?ol.
14. No repitas la misma descripci?n o b?squeda en clips consecutivos.
15. Alterna recursos solo cuando tenga sentido para la narraci?n.
16. Para herramientas digitales no inventes caracter?sticas o
    botones inexistentes; las capturas locales son ilustrativas.
17. movimiento puede ser:
    zoom lento, paneo horizontal, acercamiento,
    desplazamiento vertical, corte directo o sin movimiento.
18. texto_pantalla debe ser breve y solo cuando a?ada valor.
19. El resultado es horizontal 1920x1080.
20. Devuelve exclusivamente el JSON solicitado.
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
            bloques = original.get(
                "bloques_narracion",
                [],
            )

            clips_alineados: list[
                dict[str, Any]
            ] = []

            claves_interfaz = (
                "make",
                "chatgpt",
                "openai",
                "gmail",
                "google sheets",
                "notion",
                "panel",
                "bot?n",
                "boton",
                "escenario",
                "m?dulo",
                "modulo",
                "trigger",
                "disparador",
                "formulario",
                "interfaz",
                "cuenta",
                "prompt",
            )

            for indice, bloque in enumerate(
                bloques,
            ):
                if indice < len(clips):
                    clip = dict(
                        clips[indice]
                    )
                else:
                    clip = {}

                texto_narrado = str(
                    bloque.get(
                        "texto_narrado",
                        "",
                    )
                )

                texto_minusculas = (
                    texto_narrado.lower()
                )

                tipo_recurso = str(
                    clip.get(
                        "tipo_recurso",
                        "grafico",
                    )
                )

                if any(
                    clave in texto_minusculas
                    for clave in claves_interfaz
                ):
                    tipo_recurso = (
                        "captura_interfaz"
                    )

                clip["orden"] = indice + 1

                clip["duracion_segundos"] = round(
                    float(
                        bloque.get(
                            "duracion_segundos",
                            1,
                        )
                    ),
                    3,
                )

                clip["texto_narrado"] = (
                    texto_narrado
                )

                clip["inicio_segundos"] = float(
                    bloque.get(
                        "inicio_segundos",
                        0,
                    )
                )

                clip["final_segundos"] = float(
                    bloque.get(
                        "final_segundos",
                        0,
                    )
                )

                clip["tipo_recurso"] = (
                    tipo_recurso
                )

                if not str(
                    clip.get(
                        "descripcion",
                        "",
                    )
                ).strip():
                    clip["descripcion"] = (
                        "Representaci?n visual "
                        "espec?fica de: "
                        + texto_narrado
                    )

                clip.setdefault(
                    "busqueda_es",
                    "",
                )

                clip.setdefault(
                    "busqueda_en",
                    "",
                )

                clip.setdefault(
                    "movimiento",
                    "zoom lento",
                )

                clip.setdefault(
                    "texto_pantalla",
                    "",
                )

                clips_alineados.append(
                    clip
                )

            generado["clips"] = (
                clips_alineados
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