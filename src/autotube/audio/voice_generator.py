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

logger = logging.getLogger("autotube.voice")


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
    ) -> None:
        """Genera un archivo MP3 con reintentos."""
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
                )

                await comunicador.save(str(destino))

                if (
                    not destino.is_file()
                    or destino.stat().st_size == 0
                ):
                    raise RuntimeError(
                        "Edge TTS no generó un archivo válido."
                    )

                return

            except Exception as error:
                ultimo_error = error

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

            await self.generar_segmento(
                texto=str(segmento["texto"]),
                destino=archivo,
            )

            duracion = obtener_duracion_audio(
                archivo
            )

            archivos_audio.append(archivo)

            resultados.append(
                {
                    **segmento,
                    "archivo": archivo.name,
                    "duracion_real_segundos": duracion,
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