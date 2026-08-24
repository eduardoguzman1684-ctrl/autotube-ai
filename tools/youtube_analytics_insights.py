from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def cargar_json(
    ruta: Path,
) -> dict[str, Any]:
    datos = json.loads(
        ruta.read_text(
            encoding="utf-8-sig"
        )
    )

    if not isinstance(datos, dict):
        raise ValueError(
            f"El archivo no contiene un objeto JSON: {ruta}"
        )

    return datos


def ultimo_informe() -> Path:
    candidatos = sorted(
        (
            ruta
            for ruta in (
                ROOT
                / "data"
                / "analytics"
            ).glob(
                "youtube_analytics_*.json"
            )
            if ruta.is_file()
        ),
        key=lambda ruta: ruta.stat().st_mtime,
        reverse=True,
    )

    for ruta in candidatos:
        try:
            datos = cargar_json(
                ruta
            )
        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue

        if (
            isinstance(
                datos.get("resumen"),
                dict,
            )
            and isinstance(
                datos.get("videos"),
                list,
            )
        ):
            return ruta

    raise FileNotFoundError(
        "No se encontro un informe de YouTube Analytics."
    )


def resolver_informe(
    valor: str | None,
) -> Path:
    if not valor:
        return ultimo_informe()

    ruta = Path(
        valor
    ).expanduser()

    if not ruta.is_absolute():
        ruta = ROOT / ruta

    ruta = ruta.resolve()

    if not ruta.is_file():
        raise FileNotFoundError(
            f"No existe el informe: {ruta}"
        )

    return ruta


def numero(
    valor: Any,
    predeterminado: float = 0.0,
) -> float:
    try:
        return float(valor)
    except (
        TypeError,
        ValueError,
    ):
        return predeterminado


def porcentaje(
    numerador: float,
    denominador: float,
) -> float:
    if denominador <= 0:
        return 0.0

    return (
        numerador
        / denominador
        * 100
    )


def limitar(
    valor: float,
    minimo: float,
    maximo: float,
) -> float:
    return max(
        minimo,
        min(
            maximo,
            valor,
        ),
    )


def nivel_confianza(
    vistas: int,
    videos_con_vistas: int,
) -> dict[str, Any]:
    if (
        vistas < 100
        or videos_con_vistas < 3
    ):
        return {
            "nivel": "exploratoria",
            "puntaje": round(
                limitar(
                    vistas / 100 * 25,
                    1,
                    25,
                ),
                1,
            ),
            "descripcion": (
                "La muestra es insuficiente para elegir "
                "temas ganadores o descartar formatos."
            ),
            "sobreajuste_prohibido": True,
        }

    if (
        vistas < 1000
        or videos_con_vistas < 8
    ):
        return {
            "nivel": "provisional",
            "puntaje": round(
                25
                + limitar(
                    vistas / 1000 * 35,
                    0,
                    35,
                ),
                1,
            ),
            "descripcion": (
                "Hay senales utiles, pero deben confirmarse "
                "con mas videos y visualizaciones."
            ),
            "sobreajuste_prohibido": True,
        }

    return {
        "nivel": "solida",
        "puntaje": round(
            60
            + limitar(
                math.log10(
                    max(
                        vistas,
                        1000,
                    )
                )
                * 10,
                0,
                40,
            ),
            1,
        ),
        "descripcion": (
            "La muestra permite tomar decisiones comparativas "
            "con mayor confianza."
        ),
        "sobreajuste_prohibido": False,
    }


def palabras_titulo(
    titulo: str,
) -> set[str]:
    palabras = re.findall(
        r"[a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ]+",
        titulo.lower(),
    )

    excluidas = {
        "a",
        "al",
        "como",
        "con",
        "cuando",
        "de",
        "del",
        "el",
        "en",
        "es",
        "ia",
        "inteligencia",
        "artificial",
        "la",
        "las",
        "los",
        "para",
        "por",
        "que",
        "se",
        "sin",
        "su",
        "un",
        "una",
        "y",
    }

    return {
        palabra
        for palabra in palabras
        if (
            len(palabra) >= 4
            and palabra not in excluidas
        )
    }


def analizar_videos(
    videos: list[Any],
    retencion_canal: float,
) -> list[dict[str, Any]]:
    resultados: list[
        dict[str, Any]
    ] = []

    for elemento in videos:
        if not isinstance(
            elemento,
            dict,
        ):
            continue

        vistas = int(
            numero(
                elemento.get(
                    "views",
                    0,
                )
            )
        )

        likes = numero(
            elemento.get(
                "likes",
                0,
            )
        )

        comentarios = numero(
            elemento.get(
                "comments",
                0,
            )
        )

        compartidos = numero(
            elemento.get(
                "shares",
                0,
            )
        )

        ganados = numero(
            elemento.get(
                "subscribersGained",
                0,
            )
        )

        perdidos = numero(
            elemento.get(
                "subscribersLost",
                0,
            )
        )

        retencion = numero(
            elemento.get(
                "averageViewPercentage",
                0,
            )
        )

        interaccion = porcentaje(
            likes
            + comentarios
            + compartidos,
            vistas,
        )

        conversion = porcentaje(
            ganados
            - perdidos,
            vistas,
        )

        peso = (
            vistas
            / (
                vistas
                + 100
            )
            if vistas > 0
            else 0
        )

        retencion_ajustada = (
            retencion * peso
            + retencion_canal
            * (
                1
                - peso
            )
        )

        puntuacion = (
            limitar(
                retencion_ajustada / 40,
                0,
                1,
            )
            * 65
            + limitar(
                interaccion / 8,
                0,
                1,
            )
            * 20
            + limitar(
                max(
                    conversion,
                    0,
                )
                / 3,
                0,
                1,
            )
            * 15
        )

        resultados.append(
            {
                **elemento,
                "views": vistas,
                "retencion_porcentaje": round(
                    retencion,
                    2,
                ),
                "interaccion_porcentaje": round(
                    interaccion,
                    2,
                ),
                "conversion_suscriptor_porcentaje": round(
                    conversion,
                    2,
                ),
                "peso_estadistico": round(
                    peso,
                    4,
                ),
                "puntuacion_ajustada": round(
                    puntuacion,
                    2,
                ),
                "palabras_titulo": sorted(
                    palabras_titulo(
                        str(
                            elemento.get(
                                "titulo",
                                "",
                            )
                        )
                    )
                ),
                "evidencia_suficiente": (
                    vistas >= 100
                ),
            }
        )

    return sorted(
        resultados,
        key=lambda elemento: (
            elemento["evidencia_suficiente"],
            elemento["puntuacion_ajustada"],
            elemento["views"],
        ),
        reverse=True,
    )


def crear_recomendaciones(
    vistas: int,
    videos_con_vistas: int,
    retencion: float,
    interaccion: float,
    conversion: float,
    confianza: dict[str, Any],
) -> list[dict[str, str]]:
    recomendaciones: list[
        dict[str, str]
    ] = []

    if confianza["nivel"] == "exploratoria":
        recomendaciones.append(
            {
                "prioridad": "alta",
                "area": "muestra",
                "accion": (
                    "Publicar al menos 3 documentales adicionales "
                    "y acumular 100 vistas por video antes de "
                    "declarar un tema ganador."
                ),
                "motivo": (
                    f"Solo hay {vistas} vistas distribuidas en "
                    f"{videos_con_vistas} videos con actividad."
                ),
                "confianza": "alta",
            }
        )

    if retencion < 20:
        recomendaciones.append(
            {
                "prioridad": "alta",
                "area": "retencion",
                "accion": (
                    "Abrir con una pregunta o consecuencia fuerte "
                    "en los primeros 8 segundos, eliminar saludos "
                    "largos y presentar la promesa antes del contexto."
                ),
                "motivo": (
                    f"La retencion media observada es {retencion:.1f}%."
                ),
                "confianza": (
                    "media"
                    if vistas >= 100
                    else "exploratoria"
                ),
            }
        )

        recomendaciones.append(
            {
                "prioridad": "media",
                "area": "duracion",
                "accion": (
                    "Probar una serie de documentales de 8 a 12 "
                    "minutos frente al formato actual de 15 a 16 "
                    "minutos, cambiando solo esa variable."
                ),
                "motivo": (
                    "La duracion media vista es baja respecto "
                    "al largo actual de los documentales."
                ),
                "confianza": "exploratoria",
            }
        )

    elif retencion < 35:
        recomendaciones.append(
            {
                "prioridad": "media",
                "area": "retencion",
                "accion": (
                    "Acelerar los cambios visuales y colocar "
                    "microganchos cada 45 a 60 segundos."
                ),
                "motivo": (
                    f"La retencion media es {retencion:.1f}%."
                ),
                "confianza": "media",
            }
        )

    else:
        recomendaciones.append(
            {
                "prioridad": "media",
                "area": "retencion",
                "accion": (
                    "Mantener la estructura narrativa actual "
                    "y probar mejoras pequenas en el gancho."
                ),
                "motivo": (
                    f"La retencion media es {retencion:.1f}%."
                ),
                "confianza": "media",
            }
        )

    recomendaciones.append(
        {
            "prioridad": "media",
            "area": "titulos",
            "accion": (
                "Usar titulos de 45 a 70 caracteres con un "
                "solo conflicto, consecuencia o pregunta central. "
                "No copiar aun el tema del video con mas vistas."
            ),
            "motivo": (
                "La API disponible no ofrece CTR compatible "
                "en este informe y la muestra es pequena."
            ),
            "confianza": "alta",
        }
    )

    recomendaciones.append(
        {
            "prioridad": "media",
            "area": "experimentos",
            "accion": (
                "Cambiar una sola variable por serie: primero "
                "gancho, luego duracion y despues estilo de titulo."
            ),
            "motivo": (
                "Cambiar varias variables impide saber cual "
                "produjo una mejora."
            ),
            "confianza": "alta",
        }
    )

    if vistas < 100:
        recomendaciones.append(
            {
                "prioridad": "media",
                "area": "interaccion",
                "accion": (
                    "No interpretar todavia la tasa de likes "
                    "ni la conversion de suscriptores."
                ),
                "motivo": (
                    f"Interaccion observada: {interaccion:.1f}%; "
                    f"conversion: {conversion:.1f}%, con muestra baja."
                ),
                "confianza": "alta",
            }
        )

    return recomendaciones


def crear_contexto_prompt(
    confianza: dict[str, Any],
    metricas: dict[str, Any],
    recomendaciones: list[dict[str, str]],
) -> str:
    lineas = [
        "APRENDIZAJE REAL DEL CANAL:",
        (
            f"- Nivel de evidencia: "
            f"{confianza['nivel'].upper()}."
        ),
        (
            f"- Vistas analizadas: "
            f"{metricas['views']}."
        ),
        (
            f"- Videos con actividad: "
            f"{metricas['videos_con_vistas']}."
        ),
        (
            f"- Retencion media: "
            f"{metricas['retencion_porcentaje']:.1f}%."
        ),
        (
            "- No declares temas ganadores ni descartes "
            "categorias mientras la evidencia sea exploratoria."
        ),
        "- Prioriza diversidad controlada y pruebas de una variable.",
        "",
        "DIRECTRICES EDITORIALES:",
    ]

    for recomendacion in recomendaciones[:5]:
        lineas.append(
            "- "
            + recomendacion[
                "accion"
            ]
        )

    return "\n".join(
        lineas
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convierte YouTube Analytics en recomendaciones "
            "editoriales prudentes."
        )
    )

    parser.add_argument(
        "--reporte",
        default=None,
        help="Informe de Analytics; usa el mas reciente por defecto.",
    )

    args = parser.parse_args()

    ruta_reporte = resolver_informe(
        args.reporte
    )

    reporte = cargar_json(
        ruta_reporte
    )

    resumen = reporte.get(
        "resumen",
        {},
    )

    videos_raw = reporte.get(
        "videos",
        [],
    )

    if not isinstance(
        resumen,
        dict,
    ):
        resumen = {}

    if not isinstance(
        videos_raw,
        list,
    ):
        videos_raw = []

    vistas = int(
        numero(
            resumen.get(
                "views",
                0,
            )
        )
    )

    minutos = numero(
        resumen.get(
            "estimatedMinutesWatched",
            0,
        )
    )

    retencion = numero(
        resumen.get(
            "averageViewPercentage",
            0,
        )
    )

    likes = numero(
        resumen.get(
            "likes",
            0,
        )
    )

    comentarios = numero(
        resumen.get(
            "comments",
            0,
        )
    )

    compartidos = numero(
        resumen.get(
            "shares",
            0,
        )
    )

    ganados = numero(
        resumen.get(
            "subscribersGained",
            0,
        )
    )

    perdidos = numero(
        resumen.get(
            "subscribersLost",
            0,
        )
    )

    videos_con_vistas = sum(
        1
        for video in videos_raw
        if (
            isinstance(
                video,
                dict,
            )
            and numero(
                video.get(
                    "views",
                    0,
                )
            )
            > 0
        )
    )

    interaccion = porcentaje(
        likes
        + comentarios
        + compartidos,
        vistas,
    )

    conversion = porcentaje(
        ganados
        - perdidos,
        vistas,
    )

    confianza = nivel_confianza(
        vistas,
        videos_con_vistas,
    )

    videos = analizar_videos(
        videos_raw,
        retencion,
    )

    metricas = {
        "views": vistas,
        "estimatedMinutesWatched": minutos,
        "averageViewDuration": numero(
            resumen.get(
                "averageViewDuration",
                0,
            )
        ),
        "retencion_porcentaje": round(
            retencion,
            2,
        ),
        "interaccion_porcentaje": round(
            interaccion,
            2,
        ),
        "conversion_suscriptor_porcentaje": round(
            conversion,
            2,
        ),
        "videos_con_vistas": videos_con_vistas,
    }

    recomendaciones = crear_recomendaciones(
        vistas=vistas,
        videos_con_vistas=videos_con_vistas,
        retencion=retencion,
        interaccion=interaccion,
        conversion=conversion,
        confianza=confianza,
    )

    experimentos = [
        {
            "nombre": "Gancho inicial",
            "variable": "primeros_8_segundos",
            "control": (
                "Introduccion narrativa tradicional."
            ),
            "variante": (
                "Pregunta fuerte y consecuencia inmediata."
            ),
            "muestra_minima": (
                "3 videos por formato y 100 vistas por video."
            ),
        },
        {
            "nombre": "Duracion documental",
            "variable": "duracion",
            "control": "14 a 16 minutos.",
            "variante": "8 a 12 minutos.",
            "muestra_minima": (
                "3 videos por duracion y 100 vistas por video."
            ),
        },
        {
            "nombre": "Arquitectura del titulo",
            "variable": "titulo",
            "control": (
                "Titulo descriptivo largo."
            ),
            "variante": (
                "Conflicto unico en 45 a 70 caracteres."
            ),
            "muestra_minima": (
                "3 videos por estilo y 100 vistas por video."
            ),
        },
    ]

    perfil = {
        "version": 1,
        "generado_en": (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        ),
        "reporte_origen": str(
            ruta_reporte.resolve()
        ),
        "periodo": reporte.get(
            "periodo",
            {},
        ),
        "canal": reporte.get(
            "canal",
            {},
        ),
        "confianza": confianza,
        "metricas": metricas,
        "videos_analizados": videos,
        "recomendaciones": recomendaciones,
        "experimentos": experimentos,
        "reglas": {
            "minimo_vistas_por_video": 100,
            "minimo_videos_comparables": 3,
            "cambiar_una_variable": True,
            "usar_tema_ganador_automatico": (
                not confianza[
                    "sobreajuste_prohibido"
                ]
            ),
        },
    }

    perfil["contexto_prompt"] = (
        crear_contexto_prompt(
            confianza,
            metricas,
            recomendaciones,
        )
    )

    carpeta = (
        ROOT
        / "data"
        / "analytics"
    )

    carpeta.mkdir(
        parents=True,
        exist_ok=True,
    )

    marca = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    salida = (
        carpeta
        / f"analytics_insights_{marca}.json"
    )

    contenido = json.dumps(
        perfil,
        ensure_ascii=False,
        indent=2,
    )

    salida.write_text(
        contenido,
        encoding="utf-8",
    )

    perfil_actual = (
        carpeta
        / "strategy_profile.json"
    )

    perfil_actual.write_text(
        contenido,
        encoding="utf-8",
    )

    print()
    print("APRENDIZAJE ESTRATEGICO DE YOUTUBE")
    print("=" * 72)
    print("Informe:", ruta_reporte)
    print("Vistas analizadas:", vistas)
    print("Videos con actividad:", videos_con_vistas)
    print(
        "Retencion media:",
        f"{retencion:.1f}%",
    )
    print(
        "Interaccion:",
        f"{interaccion:.1f}%",
    )
    print(
        "Confianza:",
        confianza["nivel"].upper(),
        f"({confianza['puntaje']}/100)",
    )
    print("-" * 72)

    for posicion, recomendacion in enumerate(
        recomendaciones,
        start=1,
    ):
        print(
            f"{posicion}. "
            f"[{recomendacion['prioridad'].upper()}] "
            f"{recomendacion['accion']}"
        )

    print("=" * 72)
    print("Perfil estrategico:", perfil_actual)
    print("Informe detallado:", salida)
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
