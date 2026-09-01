from __future__ import annotations

import copy
import json
import math
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


AMPLIACIONES_COGNIVIVA = (
    (
        "Al observar {tema} con calma, conviene distinguir entre lo que "
        "pensamos, lo que sentimos y la respuesta que finalmente elegimos."
    ),
    (
        "Esa diferencia importa porque una reacción automática puede parecer "
        "inevitable, aunque en realidad forme parte de un patrón aprendido."
    ),
    (
        "En la vida cotidiana, reconocer ese patrón permite comprender el "
        "proceso sin convertirlo en una etiqueta ni en un juicio personal."
    ),
    (
        "También ayuda considerar el contexto: la misma conducta puede cumplir "
        "funciones distintas según la situación, la presión y las expectativas."
    ),
    (
        "Por eso, el tema de {tema} no se explica mediante una sola causa, sino "
        "por la interacción entre hábitos, emociones y decisiones."
    ),
    (
        "Un cambio de perspectiva comienza al detectar el instante que precede "
        "a la acción y preguntarnos qué necesidad intenta resolver."
    ),
    (
        "Esta mirada evita simplificaciones y permite analizar tanto el alivio "
        "inmediato como las consecuencias que aparecen con el paso del tiempo."
    ),
    (
        "Lo relevante no es buscar una reacción perfecta, sino entender qué "
        "elementos mantienen la respuesta y cuáles pueden modificarse gradualmente."
    ),
    (
        "Cuando conectamos pensamiento, emoción y conducta, la explicación de "
        "{tema} adquiere una dimensión más práctica y cercana."
    ),
    (
        "Ese análisis también permite diferenciar una dificultad ocasional de "
        "un patrón repetido que termina afectando decisiones importantes."
    ),
    (
        "A veces el conflicto no está en desconocer lo que conviene hacer, sino "
        "en tolerar la incomodidad que acompaña al primer paso."
    ),
    (
        "Comprender esa tensión ayuda a explicar por qué la intención y la acción "
        "no siempre avanzan al mismo ritmo."
    ),
    (
        "Desde esta perspectiva, pequeños detalles del entorno pueden facilitar "
        "una respuesta o reforzar, casi sin notarlo, la conducta anterior."
    ),
    (
        "La experiencia se vuelve más clara cuando observamos la secuencia "
        "completa: desencadenante, interpretación, emoción, decisión y consecuencia."
    ),
    (
        "Esa secuencia ofrece un mapa útil para comprender {tema} sin reducir la "
        "complejidad de cada persona y de cada circunstancia."
    ),
    (
        "Otro aspecto importante es el diálogo interno, porque puede aumentar la "
        "presión o abrir espacio para una evaluación más equilibrada."
    ),
    (
        "La culpa y la exigencia suelen estrechar la atención, mientras que una "
        "mirada curiosa permite identificar opciones que antes pasaban inadvertidas."
    ),
    (
        "Esto no significa ignorar la responsabilidad, sino comprender mejor las "
        "condiciones necesarias para actuar de manera más consciente."
    ),
    (
        "En {tema}, la repetición puede convertir una respuesta puntual en una "
        "rutina que el cerebro ejecuta con cada vez menos deliberación."
    ),
    (
        "Interrumpir esa rutina empieza por hacer visible lo automático y observar "
        "qué ocurre cuando aparece una alternativa pequeña y concreta."
    ),
    (
        "Las relaciones también influyen, porque las expectativas ajenas pueden "
        "modificar la forma en que interpretamos riesgos, límites y prioridades."
    ),
    (
        "Por esa razón, entender el comportamiento requiere mirar tanto la "
        "experiencia individual como el ambiente social que la rodea."
    ),
    (
        "A largo plazo, la suma de decisiones pequeñas puede pesar más que una "
        "resolución intensa que resulta imposible mantener."
    ),
    (
        "Esta idea conecta {tema} con una pregunta esencial: qué condiciones hacen "
        "más probable la conducta que realmente queremos sostener."
    ),
)


AMPLIACIONES_GENERALES = (
    (
        "Para comprender mejor {tema}, conviene separar sus causas inmediatas de "
        "los procesos que se desarrollan de forma gradual."
    ),
    (
        "Esta distinción permite observar el fenómeno completo y no solamente el "
        "resultado que aparece al final del proceso."
    ),
    (
        "El contexto también importa, porque una misma decisión puede producir "
        "consecuencias diferentes según las condiciones que la rodean."
    ),
    (
        "Al conectar estos elementos, {tema} deja de ser una idea aislada y se "
        "convierte en una secuencia más fácil de analizar."
    ),
    (
        "Otro punto relevante es la relación entre las decisiones presentes y "
        "los efectos que solo se hacen visibles con el tiempo."
    ),
    (
        "Mirar esa relación ayuda a evitar explicaciones simples y permite valorar "
        "los matices que suelen quedar fuera de la primera impresión."
    ),
    (
        "En este escenario, cada elemento cumple una función específica y modifica "
        "la manera en que interpretamos el conjunto."
    ),
    (
        "Por eso, entender {tema} requiere seguir el proceso paso a paso y comparar "
        "sus implicaciones inmediatas y futuras."
    ),
    (
        "La pregunta central no se limita a qué ocurre, sino también a por qué "
        "ocurre y qué cambia cuando varían las condiciones."
    ),
    (
        "Esta perspectiva ofrece una base más sólida para interpretar el tema sin "
        "depender de afirmaciones exageradas ni conclusiones apresuradas."
    ),
    (
        "Los detalles adquieren mayor sentido cuando se relacionan con el panorama "
        "general y con las consecuencias observables del proceso."
    ),
    (
        "Así, {tema} puede examinarse como parte de una transformación más amplia, "
        "con oportunidades, límites y decisiones todavía abiertas."
    ),
)


def completar_duracion_localmente(
    guion: dict[str, Any],
    palabras_minimas: int,
    palabras_maximas: int,
    channel_slug: str,
) -> tuple[dict[str, Any], int]:
    """Completa una carencia moderada sin depender de otra llamada externa."""
    ampliado = copy.deepcopy(guion)
    escenas = ampliado.get("escenas")

    if not isinstance(escenas, list) or not escenas:
        return ampliado, contar_palabras_guion(ampliado)

    plantillas = (
        AMPLIACIONES_COGNIVIVA
        if channel_slug == "cogniviva"
        else AMPLIACIONES_GENERALES
    )

    indice = 0
    max_aportes = len(plantillas) * 2

    while (
        contar_palabras_guion(ampliado) < palabras_minimas
        and indice < max_aportes
    ):
        escena = escenas[indice % len(escenas)]

        if not isinstance(escena, dict):
            indice += 1
            continue

        titulo = str(
            escena.get("titulo", "este aspecto")
        ).strip() or "este aspecto"
        plantilla = plantillas[indice % len(plantillas)]
        aporte = plantilla.format(tema=titulo)
        palabras_actuales = contar_palabras_guion(ampliado)

        if (
            palabras_actuales + contar_palabras(aporte)
            > palabras_maximas
        ):
            break

        narracion = str(escena.get("narracion", "")).strip()
        escena["narracion"] = f"{narracion} {aporte}".strip()
        indice += 1

    return ampliado, contar_palabras_guion(ampliado)


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
        channel_slug: str | None = None,
    ) -> dict[str, Any]:
        """Corrige la duración real del guion."""
        if palabras_por_minuto < 100 or palabras_por_minuto > 220:
            raise ValueError(
                "Las palabras por minuto deben estar entre 100 y 220."
            )

        channel_slug = normalize_channel_slug(
            channel_slug
            or str(
                contenido.get(
                    "channel_slug",
                    DEFAULT_CHANNEL,
                )
            )
        )
        profile = channel_profile(channel_slug)
        contexto_editorial = editorial_prompt(channel_slug)

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
            minutos_objetivo * palabras_por_minuto
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
Actua como editor profesional de videos documentales educativos.

PERFIL DEL CANAL:
{contexto_editorial}

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
15. Mantiene el enfoque editorial del canal y no introduzcas temas,
    marca ni llamadas a la accion de otro canal.
16. La llamada a la accion debe corresponder a esta marca:
    {profile['cta']}
17. En psicologia, informa sin diagnosticar, prescribir ni prometer
    resultados clinicos.

El resultado debe contener narracion suficiente para aproximarse
realmente a la duracion declarada.
""".strip()

        palabras_antes = contar_palabras_guion(
            guion_original
        )

        palabras_minimas = math.ceil(
            minutos_objetivo
            * palabras_por_minuto
            * 0.94
        )

        palabras_maximas = math.floor(
            minutos_objetivo
            * palabras_por_minuto
            * 1.05
        )

        mejor_guion = guion_original
        mejor_palabras = palabras_antes
        ajuste_local_aplicado = False
        palabras_antes_ajuste_local = palabras_antes

        for intento in range(1, 4):
            prompt_intento = (
                prompt
                + "\n\nCONTROL AUTOMATICO DE LONGITUD:\n"
                + f"Este es el intento {intento} de 3.\n"
                + "No resumas ni reduzcas ninguna escena.\n"
                + f"El resultado debe tener entre "
                + f"{palabras_minimas} y "
                + f"{palabras_maximas} palabras narradas.\n"
                + f"El objetivo ideal es exactamente "
                + f"{palabras_objetivo_total} palabras."
            )

            try:
                candidato = self.cliente.generar_json(
                    prompt=prompt_intento,
                    schema=SCRIPT_SCHEMA,
                )
            except Exception as error:
                print(
                    f"Intento {intento}/3 no disponible: "
                    f"{type(error).__name__}."
                )
                continue

            escenas_candidatas = candidato.get(
                "escenas"
            )

            if (
                not isinstance(escenas_candidatas, list)
                or len(escenas_candidatas)
                != len(escenas_originales)
            ):
                print(
                    f"Intento {intento}/3 descartado: "
                    "estructura invalida."
                )
                continue

            palabras_candidato = contar_palabras_guion(
                candidato
            )

            print(
                f"Intento {intento}/3: "
                f"{palabras_candidato} palabras"
            )

            if (
                palabras_minimas
                <= palabras_candidato
                <= palabras_maximas
            ):
                mejor_guion = candidato
                mejor_palabras = palabras_candidato
                break

            distancia_actual = abs(
                mejor_palabras
                - palabras_objetivo_total
            )

            distancia_candidato = abs(
                palabras_candidato
                - palabras_objetivo_total
            )

            if distancia_candidato < distancia_actual:
                mejor_guion = candidato
                mejor_palabras = palabras_candidato

        if mejor_palabras < palabras_minimas:
            palabras_antes_ajuste_local = mejor_palabras
            mejor_guion, mejor_palabras = (
                completar_duracion_localmente(
                    guion=mejor_guion,
                    palabras_minimas=palabras_minimas,
                    palabras_maximas=palabras_maximas,
                    channel_slug=channel_slug,
                )
            )
            ajuste_local_aplicado = (
                mejor_palabras > palabras_antes_ajuste_local
            )

            if ajuste_local_aplicado:
                print(
                    "Ajuste editorial local aplicado: "
                    f"{palabras_antes_ajuste_local} -> "
                    f"{mejor_palabras} palabras."
                )

        if not (
            palabras_minimas <= mejor_palabras <= palabras_maximas
        ):
            raise RuntimeError(
                "Gemini no alcanzo el rango valido despues "
                "de 3 intentos y el ajuste local no pudo completar "
                "la duracion. No se guardara un guion invalido."
            )

        guion_corregido = mejor_guion

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
            "channel_slug": channel_slug,
            "channel_name": profile["display_name"],
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
                "ajuste_local_aplicado": ajuste_local_aplicado,
                "palabras_antes_ajuste_local": (
                    palabras_antes_ajuste_local
                ),
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
