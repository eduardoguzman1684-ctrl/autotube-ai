from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import edge_tts

from autotube.content.script_validator import localizar_guion


VOZ_PREDETERMINADA = "es-MX-JorgeNeural"
VELOCIDAD_PREDETERMINADA = "-4%"
TONO_PREDETERMINADO = "-2Hz"
VOLUMEN_PREDETERMINADO = "+0%"
TIEMPO_MAXIMO_SEGMENTO = 120
PAUSA_ENTRE_SEGMENTOS = 1.0

logger = logging.getLogger("autotube.voice")


NUMEROS_0_29 = {
    0: "cero",
    1: "uno",
    2: "dos",
    3: "tres",
    4: "cuatro",
    5: "cinco",
    6: "seis",
    7: "siete",
    8: "ocho",
    9: "nueve",
    10: "diez",
    11: "once",
    12: "doce",
    13: "trece",
    14: "catorce",
    15: "quince",
    16: "dieciséis",
    17: "diecisiete",
    18: "dieciocho",
    19: "diecinueve",
    20: "veinte",
    21: "veintiuno",
    22: "veintidós",
    23: "veintitrés",
    24: "veinticuatro",
    25: "veinticinco",
    26: "veintiséis",
    27: "veintisiete",
    28: "veintiocho",
    29: "veintinueve",
}

DECENAS = {
    30: "treinta",
    40: "cuarenta",
    50: "cincuenta",
    60: "sesenta",
    70: "setenta",
    80: "ochenta",
    90: "noventa",
}

CENTENAS = {
    200: "doscientos",
    300: "trescientos",
    400: "cuatrocientos",
    500: "quinientos",
    600: "seiscientos",
    700: "setecientos",
    800: "ochocientos",
    900: "novecientos",
}


def numero_entero_a_palabras(numero: int) -> str:
    """Convierte un número entero a palabras en español."""
    if numero < 0:
        return "menos " + numero_entero_a_palabras(
            abs(numero)
        )

    if numero < 30:
        return NUMEROS_0_29[numero]

    if numero < 100:
        decena = numero // 10 * 10
        unidad = numero % 10

        if unidad == 0:
            return DECENAS[decena]

        return (
            f"{DECENAS[decena]} y "
            f"{NUMEROS_0_29[unidad]}"
        )

    if numero == 100:
        return "cien"

    if numero < 200:
        return (
            "ciento "
            + numero_entero_a_palabras(
                numero - 100
            )
        )

    if numero < 1000:
        centena = numero // 100 * 100
        resto = numero % 100

        resultado = CENTENAS[centena]

        if resto:
            resultado += (
                " "
                + numero_entero_a_palabras(resto)
            )

        return resultado

    if numero < 1_000_000:
        miles = numero // 1000
        resto = numero % 1000

        if miles == 1:
            resultado = "mil"
        else:
            resultado = (
                numero_entero_a_palabras(miles)
                + " mil"
            )

        if resto:
            resultado += (
                " "
                + numero_entero_a_palabras(resto)
            )

        return resultado

    if numero < 1_000_000_000:
        millones = numero // 1_000_000
        resto = numero % 1_000_000

        if millones == 1:
            resultado = "un millón"
        else:
            resultado = (
                numero_entero_a_palabras(millones)
                + " millones"
            )

        if resto:
            resultado += (
                " "
                + numero_entero_a_palabras(resto)
            )

        return resultado

    miles_millones = numero // 1_000_000_000
    resto = numero % 1_000_000_000

    if miles_millones == 1:
        resultado = "mil millones"
    else:
        resultado = (
            numero_entero_a_palabras(
                miles_millones
            )
            + " mil millones"
        )

    if resto:
        resultado += (
            " "
            + numero_entero_a_palabras(resto)
        )

    return resultado


def numero_decimal_a_palabras(
    texto: str,
) -> str:
    """Convierte un decimal a una lectura clara."""
    negativo = texto.startswith("-")

    if negativo:
        texto = texto[1:]

    separador = (
        ","
        if "," in texto
        else "."
    )

    parte_entera, parte_decimal = texto.split(
        separador,
        maxsplit=1,
    )

    palabra_separador = (
        "coma"
        if separador == ","
        else "punto"
    )

    resultado = numero_entero_a_palabras(
        int(parte_entera)
    )

    decimales = " ".join(
        numero_entero_a_palabras(
            int(digito)
        )
        for digito in parte_decimal
    )

    resultado = (
        f"{resultado} "
        f"{palabra_separador} "
        f"{decimales}"
    )

    if negativo:
        resultado = "menos " + resultado

    return resultado


def normalizar_texto_voz(
    texto: str,
) -> str:
    """Convierte números escritos con dígitos a español."""
    texto = str(texto)

    def reemplazar_porcentaje(
        coincidencia: re.Match[str],
    ) -> str:
        valor = coincidencia.group(1)

        if "." in valor or "," in valor:
            palabras = numero_decimal_a_palabras(
                valor
            )
        else:
            palabras = numero_entero_a_palabras(
                int(valor)
            )

        return f"{palabras} por ciento"

    texto = re.sub(
        r"(?<![\w])(-?\d+(?:[.,]\d+)?)\s*%",
        reemplazar_porcentaje,
        texto,
    )

    texto = re.sub(
        r"(?<![\w])(-?\d+[.,]\d+)(?![\w])",
        lambda coincidencia: numero_decimal_a_palabras(
            coincidencia.group(1)
        ),
        texto,
    )

    texto = re.sub(
        r"(?<![\w])(-?\d+)(?![\w])",
        lambda coincidencia: numero_entero_a_palabras(
            int(coincidencia.group(1))
        ),
        texto,
    )

    reemplazos_pronunciacion = [
        (
            r"este tutorial completo",
            "esta guía práctica completa",
        ),
        (
            r"este tutorial",
            "esta guía práctica",
        ),
        (
            r"un tutorial completo",
            "una guía práctica completa",
        ),
        (
            r"un tutorial",
            "una guía práctica",
        ),
        (
            r"el tutorial completo",
            "la guía práctica completa",
        ),
        (
            r"el tutorial",
            "la guía práctica",
        ),
        (
            r"tutoriales completos",
            "guías prácticas completas",
        ),
        (
            r"tutorial completo",
            "guía práctica completa",
        ),
        (
            r"tutoriales",
            "guías prácticas",
        ),
        (
            r"tutorial",
            "guía práctica",
        ),
    ]

    for patron, pronunciacion in reemplazos_pronunciacion:
        texto = re.sub(
            patron,
            pronunciacion,
            texto,
            flags=re.IGNORECASE,
        )

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


def cargar_guion_audio(
    data_dir: Path,
    archivo: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Carga el guion más reciente o un archivo indicado."""
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

    escenas = guion.get("escenas")

    if not isinstance(escenas, list) or not escenas:
        raise RuntimeError(
            "El guion no contiene escenas válidas."
        )

    return contenido, ruta


def limpiar_nombre(texto: str) -> str:
    """Convierte un título en un nombre seguro para archivos."""
    texto = texto.lower().strip()
    texto = re.sub(r"[^\w\s-]", "", texto, flags=re.UNICODE)
    texto = re.sub(r"[\s_-]+", "_", texto)
    return texto.strip("_")[:50] or "segmento"


def obtener_duracion_audio(ruta: Path) -> float:
    """Obtiene la duración real utilizando ffprobe."""
    if shutil.which("ffprobe") is None:
        raise RuntimeError(
            "ffprobe no está disponible en el sistema."
        )

    resultado = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(ruta),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    return round(float(resultado.stdout.strip()), 2)


class GeneradorVoz:
    """Genera narraciones con Edge TTS."""

    def __init__(
        self,
        voz: str | None = None,
        velocidad: str | None = None,
        tono: str | None = None,
        volumen: str | None = None,
        intentos: int = 3,
    ) -> None:
        self.voz = (
            voz
            or os.getenv("EDGE_TTS_VOICE")
            or VOZ_PREDETERMINADA
        ).strip()

        self.velocidad = (
            velocidad
            or os.getenv("EDGE_TTS_RATE")
            or VELOCIDAD_PREDETERMINADA
        ).strip()

        self.tono = (
            tono
            or os.getenv("EDGE_TTS_PITCH")
            or TONO_PREDETERMINADO
        ).strip()

        self.volumen = (
            volumen
            or os.getenv("EDGE_TTS_VOLUME")
            or VOLUMEN_PREDETERMINADO
        ).strip()

        self.intentos = max(1, intentos)

    def construir_segmentos(
        self,
        guion: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Prepara introducción, escenas y llamada a la acción."""
        segmentos: list[dict[str, Any]] = []

        introduccion = str(
            guion.get("introduccion", "")
        ).strip()

        if introduccion:
            segmentos.append(
                {
                    "tipo": "introduccion",
                    "numero": 0,
                    "titulo": "Introducción",
                    "texto": introduccion,
                }
            )

        escenas = guion.get("escenas", [])

        for posicion, escena in enumerate(
            escenas,
            start=1,
        ):
            if not isinstance(escena, dict):
                continue

            narracion = str(
                escena.get("narracion", "")
            ).strip()

            if not narracion:
                continue

            segmentos.append(
                {
                    "tipo": "escena",
                    "numero": escena.get(
                        "numero",
                        posicion,
                    ),
                    "titulo": escena.get(
                        "titulo",
                        f"Escena {posicion}",
                    ),
                    "texto": narracion,
                    "duracion_declarada_segundos": escena.get(
                        "duracion_segundos",
                        0,
                    ),
                }
            )

        llamada_accion = str(
            guion.get("llamada_accion", "")
        ).strip()

        if llamada_accion:
            segmentos.append(
                {
                    "tipo": "cta",
                    "numero": len(segmentos),
                    "titulo": "Llamada a la acción",
                    "texto": llamada_accion,
                }
            )

        if not segmentos:
            raise RuntimeError(
                "No se encontraron textos para generar la voz."
            )

        return segmentos

    async def generar_segmento(
        self,
        texto: str,
        destino: Path,
    ) -> list[dict[str, Any]]:
        """
        Genera MP3 y captura WordBoundary reales de Edge TTS.

        Los tiempos se guardan relativos al inicio del segmento.
        """
        ultimo_error: Exception | None = None

        for intento in range(1, self.intentos + 1):
            try:
                destino.unlink(missing_ok=True)

                comunicador = edge_tts.Communicate(
                    text=texto,
                    voice=self.voz,
                    rate=self.velocidad,
                    pitch=self.tono,
                    volume=self.volumen,
                    boundary="WordBoundary",
                )

                async def descargar() -> list[dict[str, Any]]:
                    marcas: list[dict[str, Any]] = []

                    with destino.open("wb") as salida:
                        async for evento in comunicador.stream():
                            tipo = evento.get("type")

                            if tipo == "audio":
                                datos = evento.get("data")

                                if datos:
                                    salida.write(datos)

                            elif tipo == "WordBoundary":
                                try:
                                    offset = float(
                                        evento.get("offset", 0)
                                    )
                                    duracion = float(
                                        evento.get("duration", 0)
                                    )
                                except (TypeError, ValueError):
                                    continue

                                inicio_segundos = (
                                    offset / 10_000_000
                                )

                                duracion_segundos = (
                                    duracion / 10_000_000
                                )

                                final_segundos = (
                                    inicio_segundos
                                    + duracion_segundos
                                )

                                palabra = str(
                                    evento.get("text", "")
                                ).strip()

                                if palabra:
                                    marcas.append(
                                        {
                                            "texto": palabra,
                                            "inicio_segundos": round(
                                                inicio_segundos,
                                                4,
                                            ),
                                            "duracion_segundos": round(
                                                duracion_segundos,
                                                4,
                                            ),
                                            "final_segundos": round(
                                                final_segundos,
                                                4,
                                            ),
                                        }
                                    )

                    return marcas

                marcas = await asyncio.wait_for(
                    descargar(),
                    timeout=TIEMPO_MAXIMO_SEGMENTO,
                )

                if (
                    not destino.is_file()
                    or destino.stat().st_size == 0
                ):
                    raise RuntimeError(
                        "Edge TTS no gener? un archivo v?lido."
                    )

                if not marcas:
                    logger.warning(
                        "Edge TTS no devolvi? WordBoundary "
                        "para el segmento."
                    )

                await asyncio.sleep(
                    PAUSA_ENTRE_SEGMENTOS
                )

                return marcas

            except Exception as error:
                ultimo_error = error

                destino.unlink(missing_ok=True)

                if intento >= self.intentos:
                    break

                espera = 2 ** intento

                logger.warning(
                    "Error generando voz | intento=%s/%s | "
                    "reintento en %s segundos",
                    intento,
                    self.intentos,
                    espera,
                )

                await asyncio.sleep(espera)

        raise RuntimeError(
            "No fue posible generar el segmento de voz."
        ) from ultimo_error

    def combinar_audios(
        self,
        archivos: list[Path],
        destino: Path,
    ) -> None:
        """Combina todos los MP3 utilizando FFmpeg."""
        if shutil.which("ffmpeg") is None:
            raise RuntimeError(
                "FFmpeg no está disponible en el sistema."
            )

        lista = destino.parent / "lista_audio.txt"

        lineas = []

        for archivo in archivos:
            ruta = archivo.resolve().as_posix()
            ruta = ruta.replace("'", r"'\''")
            lineas.append(f"file '{ruta}'")

        lista.write_text(
            "\n".join(lineas) + "\n",
            encoding="utf-8",
        )

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(lista),
                    "-vn",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    str(destino),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                "FFmpeg no pudo combinar los archivos de voz.\n"
                + error.stderr[-1500:]
            ) from error
        finally:
            lista.unlink(missing_ok=True)

    async def generar_async(
        self,
        contenido: dict[str, Any],
        ruta_guion: Path,
        output_dir: Path,
    ) -> dict[str, Any]:
        """Genera los segmentos y la narración completa."""
        guion = contenido["guion"]
        segmentos = self.construir_segmentos(guion)

        marca_tiempo = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        carpeta = (
            output_dir
            / "audio"
            / f"narracion_{marca_tiempo}"
        )

        carpeta.mkdir(
            parents=True,
            exist_ok=True,
        )

        resultados: list[dict[str, Any]] = []
        archivos_audio: list[Path] = []

        for posicion, segmento in enumerate(
            segmentos,
            start=1,
        ):
            nombre = limpiar_nombre(
                str(segmento["titulo"])
            )

            archivo = (
                carpeta
                / f"{posicion:02d}_{nombre}.mp3"
            )

            print(
                f"Generando {posicion}/{len(segmentos)}: "
                f"{segmento['titulo']}"
            )

            texto_original = str(
                segmento["texto"]
            )

            texto_voz_normalizado = (
                normalizar_texto_voz(
                    texto_original
                )
            )

            marcas_palabras = await self.generar_segmento(
                texto=texto_voz_normalizado,
                destino=archivo,
            )

            duracion = obtener_duracion_audio(
                archivo
            )

            archivos_audio.append(archivo)

            resultados.append(
                {
                    **segmento,
                    "texto_voz": texto_voz_normalizado,
                    "archivo": archivo.name,
                    "duracion_real_segundos": duracion,
                    "marcas_palabras": marcas_palabras,
                }
            )

        audio_completo = (
            carpeta / "narracion_completa.mp3"
        )

        self.combinar_audios(
            archivos=archivos_audio,
            destino=audio_completo,
        )

        duracion_total = obtener_duracion_audio(
            audio_completo
        )

        manifiesto = {
            "generado_en": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "titulo": guion.get(
                "titulo",
                "Sin título",
            ),
            "guion_origen": str(
                ruta_guion.resolve()
            ),
            "voz": self.voz,
            "velocidad": self.velocidad,
            "tono": self.tono,
            "volumen": self.volumen,
            "cantidad_segmentos": len(resultados),
            "duracion_total_segundos": duracion_total,
            "audio_completo": audio_completo.name,
            "segmentos": resultados,
        }

        ruta_manifiesto = (
            carpeta / "manifest.json"
        )

        ruta_manifiesto.write_text(
            json.dumps(
                manifiesto,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "carpeta": carpeta,
            "audio_completo": audio_completo,
            "manifiesto": ruta_manifiesto,
            "duracion_total_segundos": duracion_total,
            "segmentos": resultados,
        }

    def generar(
        self,
        contenido: dict[str, Any],
        ruta_guion: Path,
        output_dir: Path,
    ) -> dict[str, Any]:
        """Ejecuta la generación asíncrona desde la consola."""
        return asyncio.run(
            self.generar_async(
                contenido=contenido,
                ruta_guion=ruta_guion,
                output_dir=output_dir,
            )
        )