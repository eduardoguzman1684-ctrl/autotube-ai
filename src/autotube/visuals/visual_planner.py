from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.ai.gemini_client import GeminiClient
from autotube.content.script_validator import localizar_guion
from autotube.timeline.speech_alignment import (
    SpeechAlignmentError,
    build_speech_alignment,
)


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
                                        "texto_animado",
                                        "grafico",
                                    ],
                                },
                                "descripcion": {
                                    "type": "string",
                                },
                                "concepto_central": {
                                    "type": "string",
                                },
                                "criterios_obligatorios": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                    },
                                },
                                "elementos_prohibidos": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                    },
                                },
                                "continuidad_id": {
                                    "type": "string",
                                },
                                "consultas_alternativas": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                    },
                                },
                                "busqueda_es": {
                                    "type": "string",
                                },
                                "busqueda_en": {
                                    "type": "string",
                                },
                                "plataforma": {
                                    "type": "string",
                                },
                                "url_oficial": {
                                    "type": "string",
                                },
                                "pantalla_objetivo": {
                                    "type": "string",
                                },
                                "accion_visual": {
                                    "type": "string",
                                },
                                "requiere_login": {
                                    "type": "boolean",
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
                                "concepto_central",
                                "criterios_obligatorios",
                                "elementos_prohibidos",
                                "continuidad_id",
                                "consultas_alternativas",
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
    objetivo_segundos: float = 6.5,
    minimo_segundos: float = 3.0,
    maximo_segundos: float = 10.0,
) -> list[dict[str, Any]]:
    """
    Divide la narracion usando limites semanticos y tiempos reales.

    Prioriza finales de oracion, preguntas, pausas fuertes y comas.
    La ventana audiovisual favorece cambios cada 3-10 segundos para
    mantener el ritmo y conservar la relacion directa con cada frase.
    Solo fuerza un corte interno cuando no existe un limite semantico
    util dentro del intervalo permitido.
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

    texto = str(
        segmento.get("texto_voz")
        or segmento.get("texto")
        or ""
    ).strip()

    try:
        alignment = build_speech_alignment(
            {
                "duracion_total_segundos": duracion,
                "segmentos": [segmento],
            },
            target_seconds=objetivo_segundos,
            minimum_seconds=minimo_segundos,
            maximum_seconds=maximo_segundos,
        )
        global_offset_ms = round(
            inicio_global * 1000
        )
        return [
            {
                "orden": index,
                "inicio_relativo": round(
                    int(phrase["start_ms"]) / 1000,
                    3,
                ),
                "final_relativo": round(
                    int(phrase["end_ms"]) / 1000,
                    3,
                ),
                "inicio_segundos": round(
                    (
                        global_offset_ms
                        + int(phrase["start_ms"])
                    )
                    / 1000,
                    3,
                ),
                "final_segundos": round(
                    (
                        global_offset_ms
                        + int(phrase["end_ms"])
                    )
                    / 1000,
                    3,
                ),
                "duracion_segundos": round(
                    int(phrase["duration_ms"])
                    / 1000,
                    3,
                ),
                "texto_narrado": str(
                    phrase["text"]
                ),
                "sincronizacion": str(
                    phrase["timing_source"]
                ),
                "palabra_inicial": int(
                    phrase["global_word_start"]
                ),
                "palabra_final": int(
                    phrase["global_word_end"]
                ),
            }
            for index, phrase in enumerate(
                alignment["phrases"],
                start=1,
            )
        ]
    except SpeechAlignmentError:
        # Compatibilidad con manifiestos antiguos o incompletos.
        pass

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
                final_marca = float(
                    marca.get(
                        "final_segundos",
                        inicio,
                    )
                )
            except (TypeError, ValueError):
                continue

            inicio = max(
                0.0,
                min(duracion, inicio),
            )
            final_marca = max(
                inicio,
                min(duracion, final_marca),
            )

            marcas.append(
                {
                    "texto": palabra,
                    "inicio": inicio,
                    "final": final_marca,
                }
            )

    marcas.sort(
        key=lambda marca: (
            marca["inicio"],
            marca["final"],
        )
    )

    tokens_puntuados = re.findall(
        r"\S+",
        texto,
    )

    if not marcas:
        if not tokens_puntuados:
            tokens_puntuados = [""]

        paso = duracion / len(
            tokens_puntuados
        )

        for indice, token in enumerate(
            tokens_puntuados
        ):
            marcas.append(
                {
                    "texto": token,
                    "inicio": paso * indice,
                    "final": paso * (indice + 1),
                }
            )

    cierres: dict[int, tuple[int, str]] = {}

    if tokens_puntuados:
        cantidad_tokens = len(
            tokens_puntuados
        )
        cantidad_marcas = len(
            marcas
        )

        for indice in range(
            cantidad_marcas
        ):
            posicion = min(
                cantidad_tokens - 1,
                max(
                    0,
                    int(
                        (indice + 1)
                        * cantidad_tokens
                        / cantidad_marcas
                    )
                    - 1,
                ),
            )

            token = tokens_puntuados[
                posicion
            ].rstrip(
                "\"'???)]}"
            )

            ultimo = token[-1:] if token else ""

            if ultimo in ".!?":
                cierres[indice] = (
                    3,
                    ultimo,
                )
            elif ultimo in ";:":
                cierres[indice] = (
                    2,
                    ultimo,
                )
            elif ultimo == ",":
                cierres[indice] = (
                    1,
                    ultimo,
                )

    bloques: list[dict[str, Any]] = []
    indice_inicial = 0
    inicio_bloque = 0.0
    ultimo_indice = len(marcas) - 1

    while indice_inicial <= ultimo_indice:
        restante = (
            duracion
            - inicio_bloque
        )

        if restante <= maximo_segundos:
            indice_corte = ultimo_indice
        else:
            candidatos = [
                indice
                for indice in range(
                    indice_inicial,
                    ultimo_indice + 1,
                )
                if (
                    minimo_segundos
                    <= (
                        marcas[indice]["final"]
                        - inicio_bloque
                    )
                    <= maximo_segundos
                )
            ]

            semanticos = [
                indice
                for indice in candidatos
                if indice in cierres
            ]

            if semanticos:
                indice_corte = max(
                    semanticos,
                    key=lambda indice: (
                        cierres[indice][0],
                        -abs(
                            (
                                marcas[indice]["final"]
                                - inicio_bloque
                            )
                            - objetivo_segundos
                        ),
                    ),
                )
            elif candidatos:
                indice_corte = min(
                    candidatos,
                    key=lambda indice: abs(
                        (
                            marcas[indice]["final"]
                            - inicio_bloque
                        )
                        - objetivo_segundos
                    ),
                )
            else:
                disponibles = [
                    indice
                    for indice in range(
                        indice_inicial,
                        ultimo_indice + 1,
                    )
                    if (
                        marcas[indice]["final"]
                        > inicio_bloque
                    )
                ]

                if not disponibles:
                    break

                indice_corte = min(
                    disponibles,
                    key=lambda indice: abs(
                        (
                            marcas[indice]["final"]
                            - inicio_bloque
                        )
                        - objetivo_segundos
                    ),
                )

        final_bloque = (
            duracion
            if indice_corte == ultimo_indice
            else marcas[indice_corte]["final"]
        )

        final_bloque = max(
            inicio_bloque + 0.001,
            min(duracion, final_bloque),
        )

        texto_bloque = " ".join(
            str(marca["texto"])
            for marca in marcas[
                indice_inicial:
                indice_corte + 1
            ]
        ).strip()

        cierre = cierres.get(
            indice_corte
        )

        if (
            cierre
            and texto_bloque
            and texto_bloque[-1] not in ".!?,;:"
        ):
            texto_bloque += cierre[1]

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
                "texto_narrado": texto_bloque,
            }
        )

        indice_inicial = indice_corte + 1
        inicio_bloque = final_bloque

    if (
        len(bloques) > 1
        and bloques[-1][
            "duracion_segundos"
        ] < minimo_segundos
    ):
        anterior = bloques[-2]
        ultimo = bloques[-1]

        duracion_combinada = (
            anterior["duracion_segundos"]
            + ultimo["duracion_segundos"]
        )

        if (
            duracion_combinada
            <= maximo_segundos + 1.5
        ):
            anterior["final_relativo"] = (
                ultimo["final_relativo"]
            )
            anterior["final_segundos"] = (
                ultimo["final_segundos"]
            )
            anterior["duracion_segundos"] = round(
                anterior["final_segundos"]
                - anterior["inicio_segundos"],
                3,
            )
            anterior["texto_narrado"] = (
                (
                    anterior["texto_narrado"]
                    + " "
                    + ultimo["texto_narrado"]
                ).strip()
            )
            bloques.pop()

    if bloques:
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

        for indice, bloque in enumerate(
            bloques,
            start=1,
        ):
            bloque["orden"] = indice
            bloque["duracion_segundos"] = round(
                bloque["final_segundos"]
                - bloque["inicio_segundos"],
                3,
            )

    return bloques


def normalizar_texto_busqueda(texto: str) -> str:
    """Normaliza texto para reglas locales de selección visual."""
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto.lower())
        if not unicodedata.combining(caracter)
    )


def resumir_concepto(texto: str, limite: int = 14) -> str:
    """Obtiene una frase breve sin inventar información."""
    palabras = re.findall(r"\b[\wÁÉÍÓÚÜÑáéíóúüñ'-]+\b", texto)
    resumen = " ".join(palabras[:limite]).strip()
    return resumen or "concepto principal de la narración"


def narracion_autoriza_grafico(texto: str) -> bool:
    """Permite gráficos solo cuando el propio texto los necesita."""
    contenido = normalizar_texto_busqueda(texto)
    indicadores = (
        "grafico",
        "diagrama",
        "infografia",
        "tabla de datos",
        "estadistica",
        "porcentaje",
        "mapa de calor",
        "curva comparativa",
        "linea de tiempo",
        "flujo de datos",
    )
    return any(indicador in contenido for indicador in indicadores)


def es_llamada_accion(texto: str, tipo_segmento: str = "") -> bool:
    """Detecta una llamada a la acción real, no una introducción."""
    contenido = normalizar_texto_busqueda(
        f"{tipo_segmento} {texto}"
    )
    indicadores = (
        "llamada a la accion",
        "suscrib",
        "comparte este video",
        "deja tu comentario",
        "activa la campana",
        "dale me gusta",
    )
    return any(indicador in contenido for indicador in indicadores)


def consulta_invalida_para_canal(
    consulta: str,
    nombre_canal: str,
) -> bool:
    """Bloquea consultas editoriales pertenecientes a otro canal."""
    contenido = normalizar_texto_busqueda(consulta)
    if not contenido:
        return True

    if normalizar_texto_busqueda(nombre_canal) != "cogniviva":
        prohibidas = (
            "psychology",
            "therapy",
            "therapist",
            "counseling",
            "mental health",
            "procrastination",
            "burnout",
            "self compassion",
            "psicologia",
            "terapia",
            "procrastinacion",
        )
        return any(valor in contenido for valor in prohibidas)

    return False


def escenario_visual_nexon(
    texto: str,
    titulo: str,
) -> dict[str, Any]:
    """Crea búsquedas documentales concretas para Nexon IA."""
    contexto = normalizar_texto_busqueda(f"{titulo} {texto}")
    escenarios: tuple[
        tuple[tuple[str, ...], str, str, str, str],
        ...,
    ] = (
        (
            ("deepfake", "medio sintetico", "rostro sintetico", "intercambio de rostro"),
            "imagen_stock",
            "análisis forense de rostro deepfake comparación",
            "deepfake face comparison digital forensics analyst",
            "Fotografía documental de un analista examinando señales visibles de manipulación facial en dos fotogramas.",
        ),
        (
            ("evidencia audiovisual", "camara", "grabacion", "testigo imparcial"),
            "video_stock",
            "cámara de noticias grabando evidencia en la calle",
            "news camera recording street evidence journalist",
            "Video documental de una cámara profesional registrando un acontecimiento real con periodistas presentes.",
        ),
        (
            ("manipulacion historica", "propaganda", "fotografia retocada", "raices historicas"),
            "imagen_stock",
            "archivo histórico manipulación fotográfica propaganda",
            "historical photo manipulation propaganda archive",
            "Fotografía de archivo relacionada con técnicas históricas de retoque y propaganda visual.",
        ),
        (
            ("gan", "red generativa", "generador", "discriminador"),
            "imagen_stock",
            "investigadores inteligencia artificial redes GAN laboratorio",
            "GAN artificial intelligence researchers computer laboratory",
            "Fotografía real de investigadores trabajando con modelos generativos en un laboratorio informático.",
        ),
        (
            ("clonacion de voz", "voz sintetica", "audio falso", "onda de audio"),
            "video_stock",
            "grabación de voz micrófono análisis de audio",
            "voice recording microphone audio analysis studio",
            "Video real de una grabación de voz y su análisis técnico en un estudio de audio.",
        ),
        (
            ("tiempo real", "videoconferencia", "mascara digital", "movimiento de labios"),
            "video_stock",
            "videoconferencia cámara seguimiento facial tiempo real",
            "video conference camera real time face tracking",
            "Video de una videoconferencia con una persona frente a cámara y seguimiento facial en tiempo real.",
        ),
        (
            ("politic", "eleccion", "lider mundial", "campana electoral"),
            "video_stock",
            "líder político discurso conferencia de prensa elecciones",
            "political leader press conference election speech",
            "Video documental de un líder político ofreciendo un discurso ante cámaras y periodistas.",
        ),
        (
            ("fraude", "estafa", "delincuencia", "suplantacion", "transferencia bancaria"),
            "video_stock",
            "investigación fraude digital llamada bancaria falsa",
            "digital fraud investigation phone banking scam",
            "Video realista de una investigación de fraude digital relacionado con llamadas o transacciones bancarias.",
        ),
        (
            ("erosion social", "confianza social", "dudar", "desinformacion"),
            "video_stock",
            "personas verificando noticias falsas en teléfonos",
            "people checking fake news smartphones media literacy",
            "Video documental de personas comparando noticias y verificando información recibida en sus teléfonos.",
        ),
        (
            ("forense", "deteccion", "autenticidad", "analisis de pixeles"),
            "video_stock",
            "analista forense verificando autenticidad de video",
            "digital forensics analyst authenticating video footage",
            "Video real de un especialista forense examinando la autenticidad de una grabación audiovisual.",
        ),
        (
            ("legislacion", "ley", "regulacion", "marco etico", "tribunal"),
            "video_stock",
            "legisladores debate regulación tecnología parlamento",
            "lawmakers debating technology regulation parliament",
            "Video documental de legisladores debatiendo regulación tecnológica en una cámara parlamentaria.",
        ),
        (
            ("marca de agua", "procedencia", "firma digital", "c2pa", "infraestructura de la verdad"),
            "imagen_stock",
            "cámara profesional autenticidad contenido firma digital",
            "professional camera content authenticity digital signature",
            "Fotografía real de una cámara profesional y un proceso de verificación de procedencia del contenido.",
        ),
    )

    for palabras_clave, tipo, busqueda_es, busqueda_en, descripcion in escenarios:
        if any(clave in contexto for clave in palabras_clave):
            return {
                "tipo_recurso": tipo,
                "busqueda_es": busqueda_es,
                "busqueda_en": busqueda_en,
                "descripcion": descripcion,
            }

    concepto = resumir_concepto(texto, 10)
    palabras = [
        palabra
        for palabra in re.findall(r"\b[a-zA-Z0-9'-]+\b", contexto)
        if len(palabra) >= 4
        and palabra not in {
            "para", "como", "este", "esta", "desde", "entre",
            "sobre", "tambien", "puede", "pueden", "cuando",
            "donde", "nuestra", "nuestro", "estos", "estas",
        }
    ]
    busqueda_es = " ".join(palabras[:7]) or resumir_concepto(titulo, 6)
    return {
        "tipo_recurso": "imagen_stock",
        "busqueda_es": busqueda_es,
        "busqueda_en": f"{busqueda_es} documentary evidence",
        "descripcion": (
            "Fotografía documental que muestre de forma directa y "
            f"comprobable este concepto narrado: {concepto}."
        ),
    }


def escenario_visual_local(
    texto: str,
    titulo: str,
    nombre_canal: str,
) -> dict[str, Any]:
    """Selecciona un escenario concreto mediante reglas editoriales."""
    if normalizar_texto_busqueda(nombre_canal) != "cogniviva":
        return escenario_visual_nexon(
            texto=texto,
            titulo=titulo,
        )

    contexto = normalizar_texto_busqueda(
        f"{titulo} {texto}"
    )

    escenarios: tuple[
        tuple[tuple[str, ...], str, str, str, str],
        ...,
    ] = (
        (
            ("amigdala", "corteza prefrontal", "sistema limbico"),
            "grafico",
            "diagrama cerebro humano amígdala corteza prefrontal",
            "human brain amygdala prefrontal cortex medical illustration",
            "Diagrama educativo del cerebro humano que identifica la amígdala, la corteza prefrontal y su relación funcional.",
        ),
        (
            ("cerebro", "neuronal", "neurociencia"),
            "grafico",
            "diagrama cerebro humano proceso neuronal educativo",
            "human brain neural process educational medical illustration",
            "Diagrama educativo del cerebro humano con conexiones neuronales claras y sin cifras inventadas.",
        ),
        (
            ("sesgo del presente", "yo futuro", "futuro"),
            "grafico",
            "línea temporal decisiones presente consecuencias futuras",
            "decision timeline present choices future consequences illustration",
            "Línea temporal educativa que conecta una decisión presente con sus posibles consecuencias futuras.",
        ),
        (
            ("bucle", "refuerzo", "alivio inmediato", "recompensa"),
            "grafico",
            "ciclo alivio inmediato evitación hábito conducta",
            "avoidance habit immediate relief behavior cycle diagram",
            "Diagrama circular del ciclo entre incomodidad, evitación, alivio inmediato y repetición de la conducta.",
        ),
        (
            ("procrast", "posponer", "aplazar"),
            "video_stock",
            "persona posponiendo tarea importante escritorio calendario",
            "adult postponing important task desk calendar documentary",
            "Video documental de una persona ante una tarea importante, con calendario visible y señales realistas de postergación.",
        ),
        (
            ("pereza", "autocritica", "culpa", "fracaso"),
            "imagen_stock",
            "persona reflexiva escritorio autocrítica presión emocional",
            "reflective adult desk self criticism emotional pressure",
            "Fotografía real de una persona reflexiva frente a su trabajo, mostrando presión emocional sin dramatización clínica.",
        ),
        (
            ("autocompasion", "compasion", "dialogo interno"),
            "imagen_stock",
            "persona tranquila escribiendo diario reflexión personal",
            "calm adult journaling personal reflection self compassion",
            "Fotografía real de una persona escribiendo en un diario durante un momento tranquilo de reflexión personal.",
        ),
        (
            ("friccion", "primer paso", "comenzar", "iniciar"),
            "video_stock",
            "persona comenzando tarea pequeño primer paso escritorio",
            "adult starting difficult task small first step desk",
            "Video documental de una persona organizando lo necesario y comenzando una tarea con un primer paso concreto.",
        ),
        (
            ("consecuencia", "largo plazo", "fecha limite"),
            "imagen_stock",
            "calendario tareas pendientes consecuencias largo plazo",
            "calendar overdue tasks long term consequences planning",
            "Fotografía real de un calendario con tareas pendientes y una persona revisando prioridades a largo plazo.",
        ),
        (
            ("trabajo", "tarea", "productividad", "proyecto"),
            "video_stock",
            "persona trabajando tarea concreta escritorio oficina",
            "adult completing focused task office desk documentary",
            "Video documental de una persona realizando una tarea concreta en un espacio de trabajo realista y ordenado.",
        ),
        (
            ("decision", "eleccion", "alternativa"),
            "grafico",
            "diagrama opciones decisión conducta consecuencias",
            "decision options behavior consequences educational diagram",
            "Diagrama educativo que conecta opciones, decisión, conducta y consecuencias sin utilizar estadísticas inventadas.",
        ),
        (
            ("emocion", "ansiedad", "estres", "incomodidad"),
            "imagen_stock",
            "persona manejando incomodidad emocional situación cotidiana",
            "adult managing emotional discomfort everyday situation documentary",
            "Fotografía real de una persona atravesando una situación cotidiana de incomodidad emocional con expresión natural.",
        ),
        (
            ("habito", "rutina", "patron", "automatico"),
            "grafico",
            "diagrama hábito señal rutina consecuencia conducta",
            "habit cue routine consequence behavior cycle diagram",
            "Diagrama educativo del ciclo entre señal, rutina y consecuencia aplicado a una conducta cotidiana.",
        ),
    )

    for palabras_clave, tipo, busqueda_es, busqueda_en, descripcion in escenarios:
        if any(clave in contexto for clave in palabras_clave):
            return {
                "tipo_recurso": tipo,
                "busqueda_es": busqueda_es,
                "busqueda_en": busqueda_en,
                "descripcion": descripcion,
            }

    concepto = resumir_concepto(texto)
    return {
        "tipo_recurso": "imagen_stock",
        "busqueda_es": f"psicología cotidiana {resumir_concepto(titulo, 5)}",
        "busqueda_en": "adult everyday behavior psychology documentary photo",
        "descripcion": (
            "Fotografía real de una situación cotidiana que represente "
            f"directamente este concepto: {concepto}."
        ),
    }


def crear_plan_visual_local(
    contexto: list[dict[str, Any]],
    guion: dict[str, Any],
    nombre_canal: str,
) -> dict[str, Any]:
    """Construye un plan completo cuando Gemini no está disponible."""
    segmentos: list[dict[str, Any]] = []
    movimientos = (
        "zoom lento",
        "paneo horizontal",
        "acercamiento",
        "corte directo",
    )
    indice_global = 0
    for original in contexto:
        bloques = original.get("bloques_narracion", [])
        clips: list[dict[str, Any]] = []
        titulo_segmento = str(
            original.get("titulo", "Sin título")
        )
        tipo_segmento = normalizar_texto_busqueda(
            str(original.get("tipo", "escena"))
        )

        for indice, bloque in enumerate(bloques, start=1):
            texto_narrado = str(
                bloque.get("texto_narrado", "")
            ).strip()
            escenario = escenario_visual_local(
                texto=texto_narrado,
                titulo=titulo_segmento,
                nombre_canal=nombre_canal,
            )
            tipo_recurso = str(escenario["tipo_recurso"])

            es_llamada = es_llamada_accion(
                texto=texto_narrado,
                tipo_segmento=tipo_segmento,
            ) and indice == 1

            if es_llamada:
                tipo_recurso = "texto_animado"

            if (
                tipo_recurso == "grafico"
                and not narracion_autoriza_grafico(texto_narrado)
            ):
                tipo_recurso = "imagen_stock"

            concepto = resumir_concepto(
                texto_narrado or titulo_segmento
            )
            consulta_en = str(escenario["busqueda_en"])
            consulta_es = str(escenario["busqueda_es"])
            texto_pantalla = ""
            descripcion = str(escenario["descripcion"])

            if tipo_recurso != escenario["tipo_recurso"]:
                if tipo_recurso == "grafico":
                    descripcion = (
                        "Diagrama educativo horizontal que representa "
                        f"claramente este concepto: {concepto}."
                    )
                elif tipo_recurso == "video_stock":
                    descripcion = (
                        "Video documental de una acción cotidiana "
                        f"relacionada directamente con: {concepto}."
                    )
                else:
                    descripcion = (
                        "Fotografía real de una situación cotidiana "
                        f"relacionada directamente con: {concepto}."
                    )

            if tipo_recurso == "texto_animado":
                texto_pantalla = resumir_concepto(
                    titulo_segmento,
                    7,
                )

            clips.append(
                {
                    "orden": indice,
                    "duracion_segundos": round(
                        float(bloque.get("duracion_segundos", 1)),
                        3,
                    ),
                    "texto_narrado": texto_narrado,
                    "inicio_segundos": float(
                        bloque.get("inicio_segundos", 0)
                    ),
                    "final_segundos": float(
                        bloque.get("final_segundos", 0)
                    ),
                    "tipo_recurso": tipo_recurso,
                    "descripcion": descripcion,
                    "concepto_central": concepto,
                    "criterios_obligatorios": [
                        concepto,
                        "relación directa con el texto narrado",
                    ],
                    "elementos_prohibidos": [
                        "robots humanoides genéricos",
                        "interfaces o estadísticas inventadas",
                        "escenas sin relación con la narración",
                    ],
                    "continuidad_id": (
                        f"segmento_{original.get('numero', 0)}"
                    ),
                    "consultas_alternativas": [
                        consulta_en,
                        consulta_es,
                        f"{consulta_en} close up",
                    ],
                    "busqueda_es": consulta_es,
                    "busqueda_en": consulta_en,
                    "plataforma": "",
                    "url_oficial": "",
                    "pantalla_objetivo": "",
                    "accion_visual": "",
                    "requiere_login": False,
                    "movimiento": movimientos[
                        indice_global % len(movimientos)
                    ],
                    "texto_pantalla": texto_pantalla,
                }
            )
            indice_global += 1

        segmentos.append(
            {
                "tipo": original.get("tipo", "escena"),
                "numero": original.get("numero", 0),
                "titulo": titulo_segmento,
                "duracion_audio_segundos": float(
                    original.get("duracion_audio_segundos", 0)
                ),
                "clips": clips,
            }
        )

    estilo = (
        "Documental horizontal de psicología práctica con fotografías "
        "reales, acciones cotidianas y diagramas educativos claros."
        if normalizar_texto_busqueda(nombre_canal) == "cogniviva"
        else (
            "Documental horizontal educativo con videos y fotografias "
            "reales que coinciden con cada frase narrada. Los graficos "
            "solo se permiten cuando la narracion los necesita de forma "
            "explicita."
        )
    )

    return {
        "titulo": guion.get("titulo", "Sin título"),
        "estilo_visual_general": estilo,
        "resolucion": "1920x1080",
        "segmentos": segmentos,
        "notas_edicion": [
            "Plan de recuperación local sincronizado con el audio real.",
            "Cada clip conserva exactamente su bloque narrado y sus tiempos.",
            "Validar la relación visual antes del render final.",
            "No generar gráficos como respaldo de stock ausente.",
        ],
    }

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

        Cada segmento contiene bloques semanticos de aproximadamente
        3-10 segundos asociados a texto narrado concreto.
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
        nombre_canal = str(
            contenido_guion.get(
                "channel_name",
                "NEXON IA",
            )
        ).strip() or "NEXON IA"

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
educativos para YouTube del canal {nombre_canal}.

T?TULO:
{guion.get("titulo", "Sin t?tulo")}

SEGMENTOS Y BLOQUES TEMPORIZADOS CON EL AUDIO REAL:
{contexto_json}

INSTRUCCIONES OBLIGATORIAS:

1. Conserva exactamente el mismo n?mero y orden de segmentos.
2. Cada segmento contiene "bloques_narracion" ya sincronizados.
3. Debes devolver EXACTAMENTE UN clip por cada bloque_narracion.
4. El clip debe ilustrar ?nicamente el texto_narrado de ese bloque.
   No fragmentes nuevamente el bloque ni pidas varias tomas para cubrirlo.
5. Copia exactamente en cada clip:
   - texto_narrado
   - inicio_segundos
   - final_segundos
   - duracion_segundos
6. No combines frases pertenecientes a bloques diferentes.
7. Nunca uses "captura_web_real" ni "captura_interfaz".
   No abras navegadores, p?ginas web ni pantallas que requieran inicio de sesi?n.
   Si la narraci?n menciona ChatGPT, OpenAI, inteligencia artificial,
   aplicaciones o plataformas digitales, representa el concepto mediante:
   - "video_stock" para escenas reales relacionadas;
   - "imagen_stock" para fotograf?as o ilustraciones relacionadas;
   - "texto_animado" para conceptos y mensajes breves.
   Las im?genes deben coincidir directamente con el texto narrado.
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
    botones inexistentes; usa representaciones visuales conceptuales sin inventar interfaces.
17. movimiento puede ser:
    zoom lento, paneo horizontal, acercamiento,
    desplazamiento vertical, corte directo o sin movimiento.
18. texto_pantalla debe ser breve y solo cuando a?ada valor.
19. El resultado es horizontal 1920x1080.
20. Prioriza imagen_stock y video_stock reales. Cada recurso debe
    mostrar el sujeto, la accion, el lugar o el proceso mencionado
    en el bloque narrado.
21. Usa video_stock solamente cuando exista una acci?n f?sica real
    que pueda encontrarse como video: personas trabajando,
    servidores funcionando, laboratorios, hospitales, tribunales,
    f?bricas, ciudades o equipos en movimiento.
22. No uses videos abstractos de luces, part?culas, rostros rob?ticos
    gen?ricos o c?digos aleatorios.
23. Usa grafico solamente cuando el texto_narrado mencione de forma
    explicita un grafico, diagrama, tabla, estadistica, porcentaje,
    mapa de calor, curva o flujo de datos. Si no lo menciona, el tipo
    debe ser video_stock o imagen_stock. No existe una cuota minima
    de graficos y es correcto devolver cero graficos.
25. Usa texto_animado en un maximo de 5 clips en todo el documental,
    nunca m?s de uno por segmento y ?nicamente para el t?tulo,
    una pregunta central, transiciones importantes o la llamada
    a la acci?n.
24. Cada b?squeda debe derivarse directamente del texto_narrado.
26. Para una fotograf?a real, incluye en descripcion la frase
    "fotograf?a real" y describe sujeto, acci?n, lugar y contexto.
27. Para explicar arquitectura, capas, flujo de datos o procesos
    matem?ticos, usa imagen_stock y especifica "diagrama t?cnico".
28. busqueda_en debe contener entre 5 y 10 t?rminos concretos en
    ingl?s apropiados para Wikimedia Commons y Pixabay.
29. Cuando exista una entidad concreta, incluye su nombre:
    NVIDIA H100, GPU data center, hospital MRI, courtroom,
    bank credit evaluation, transformer neural network u otra
    entidad mencionada por la narraci?n.
30. Proh?be b?squedas gen?ricas aisladas como artificial intelligence,
    technology, computer, future, data, digital o business.
31. No uses una computadora dom?stica para representar un centro
    de datos, una GPU especializada o infraestructura de IA.
32. No uses gr?ficos de barras, porcentajes, estad?sticas inventadas,
    plantillas repetitivas ni infograf?as sin datos verificables.
33. No repitas la misma b?squeda ni el mismo sujeto visual en clips
    consecutivos.
34. Para conceptos abstractos utiliza un diagrama t?cnico real,
    una fotograf?a cient?fica o una aplicaci?n concreta relacionada.
35. Si no existe una representaci?n visual precisa, describe el
    recurso como pendiente; no sustituyas el concepto por una
    imagen atractiva pero incorrecta.
36. Antes de aceptar cada clip, comprueba que una persona pueda
    relacionar directamente el recurso con la frase narrada.
37. No utilices el avatar NEX como sustituto de im?genes documentales.
38. concepto_central debe expresar en una frase corta el
    unico significado visual que debe comunicar el clip.
39. criterios_obligatorios debe contener entre uno y tres elementos
    visibles y comprobables: sujeto, accion, objeto, lugar o proceso.
40. elementos_prohibidos debe enumerar sustitutos genericos que
    volverian incorrecta la escena. Ejemplo: no usar una reunion
    empresarial para representar un comite cientifico.
41. consultas_alternativas debe contener entre dos y cuatro busquedas
    concretas, principalmente en ingles, que mantengan el mismo
    concepto central mediante palabras diferentes.
42. continuidad_id debe repetirse solo cuando varios clips consecutivos
    pertenezcan a la misma secuencia visual, entidad o proceso.
43. Para ideas abstractas busca una aplicacion, objeto, lugar, archivo
    documental o persona real relacionada. No uses un grafico solo
    porque la idea sea abstracta.
44. La descripcion debe poder evaluarse sin leer el resto del guion:
    identifica claramente sujeto, accion, entorno y relacion narrativa.
45. No apruebes como video_stock una accion cuyo resultado probable
    solo coincida por palabras generales. La accion fisica debe ser
    exactamente compatible con la narracion.
46. Antes de devolver cada clip comprueba concepto_central,
    criterios_obligatorios y elementos_prohibidos. Si no existe stock
    preciso, conserva el tipo de stock y marca la descripcion como
    pendiente. Nunca lo cambies a grafico para completar el plan.
47. Devuelve exclusivamente el JSON solicitado.
""".strip()

        modelo_usado = "planificador_local_v1"

        try:
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

            if any(
                not isinstance(segmento, dict)
                or not isinstance(segmento.get("clips"), list)
                or not segmento.get("clips")
                for segmento in segmentos_generados
            ):
                raise RuntimeError(
                    "Gemini devolvió uno o más segmentos sin clips."
                )

            modelo_usado = str(
                getattr(
                    self.cliente,
                    "last_model_used",
                    "gemini",
                )
                or "gemini"
            )

        except Exception as error:
            print()
            print(
                "AVISO: Gemini no pudo crear el plan visual "
                f"({type(error).__name__})."
            )
            print(
                "Aplicando plan visual local sincronizado "
                "con la narración..."
            )
            resultado = crear_plan_visual_local(
                contexto=contexto,
                guion=guion,
                nombre_canal=nombre_canal,
            )
            segmentos_generados = resultado["segmentos"]

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

            tipos_permitidos = {
                "video_stock",
                "imagen_stock",
                "texto_animado",
                "grafico",
            }

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
                            )
                )

                if tipo_recurso not in tipos_permitidos:
                    tipo_recurso = "imagen_stock"

                escenario_seguro = escenario_visual_local(
                    texto=texto_narrado,
                    titulo=str(original.get("titulo", "")),
                    nombre_canal=nombre_canal,
                )

                if (
                    tipo_recurso == "grafico"
                    and not narracion_autoriza_grafico(texto_narrado)
                ):
                    tipo_recurso = str(
                        escenario_seguro["tipo_recurso"]
                    )

                if (
                    tipo_recurso == "texto_animado"
                    and not es_llamada_accion(
                        texto=texto_narrado,
                        tipo_segmento=str(original.get("tipo", "")),
                    )
                ):
                    tipo_recurso = str(
                        escenario_seguro["tipo_recurso"]
                    )

                consulta_generada = " ".join(
                    (
                        str(clip.get("busqueda_en", "")),
                        str(clip.get("busqueda_es", "")),
                    )
                )

                if consulta_invalida_para_canal(
                    consulta=consulta_generada,
                    nombre_canal=nombre_canal,
                ):
                    clip["busqueda_en"] = str(
                        escenario_seguro["busqueda_en"]
                    )
                    clip["busqueda_es"] = str(
                        escenario_seguro["busqueda_es"]
                    )
                    clip["descripcion"] = str(
                        escenario_seguro["descripcion"]
                    )
                    clip["consultas_alternativas"] = [
                        str(escenario_seguro["busqueda_en"]),
                        str(escenario_seguro["busqueda_es"]),
                    ]

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

                clip.setdefault(
                    "plataforma",
                    "",
                )

                clip.setdefault(
                    "url_oficial",
                    "",
                )

                clip.setdefault(
                    "pantalla_objetivo",
                    "",
                )

                clip.setdefault(
                    "accion_visual",
                    "",
                )

                clip.setdefault(
                    "requiere_login",
                    False,
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
                    "concepto_central",
                    texto_narrado,
                )

                clip.setdefault(
                    "continuidad_id",
                    (
                        f"segmento_{original['numero']}_"
                        f"clip_{indice + 1}"
                    ),
                )

                for campo_lista in (
                    "criterios_obligatorios",
                    "elementos_prohibidos",
                    "consultas_alternativas",
                ):
                    if not isinstance(
                        clip.get(campo_lista),
                        list,
                    ):
                        clip[campo_lista] = []

                if not clip[
                    "criterios_obligatorios"
                ]:
                    clip[
                        "criterios_obligatorios"
                    ] = [
                        str(
                            clip.get(
                                "descripcion",
                                texto_narrado,
                            )
                        )
                    ]

                if not clip[
                    "consultas_alternativas"
                ]:
                    clip[
                        "consultas_alternativas"
                    ] = [
                        consulta
                        for consulta in (
                            str(
                                clip.get(
                                    "busqueda_en",
                                    "",
                                )
                            ).strip(),
                            str(
                                clip.get(
                                    "busqueda_es",
                                    "",
                                )
                            ).strip(),
                        )
                        if consulta
                    ]

                clip.setdefault(
                    "movimiento",
                    "zoom lento",
                )

                clip.setdefault(
                    "texto_pantalla",
                    "",
                )

                descripcion_minusculas = str(
                    clip.get(
                        "descripcion",
                        "",
                    )
                ).lower()

                indicadores_grafico = (
                    "diagrama t?cnico",
                    "diagrama tecnico",
                    "gr?fico t?cnico",
                    "grafico tecnico",
                    "mapa de calor",
                    "matriz num?rica",
                    "matriz numerica",
                    "cuadrante comparativo",
                    "curva comparativa",
                    "flujo de decisi?n",
                    "flujo de decision",
                    "arquitectura de red",
                    "sistema de coordenadas",
                    "espacio vectorial",
                )

                if (
                    narracion_autoriza_grafico(texto_narrado)
                    and any(
                        indicador in descripcion_minusculas
                        for indicador in indicadores_grafico
                    )
                ):
                    clip["tipo_recurso"] = "grafico"
                elif clip["tipo_recurso"] == "grafico":
                    clip["tipo_recurso"] = str(
                        escenario_seguro["tipo_recurso"]
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
            "modelo": modelo_usado,
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
