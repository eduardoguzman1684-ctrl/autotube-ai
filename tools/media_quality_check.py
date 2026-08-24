from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]

PATRON_TIEMPO = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})"
    r"[,.](?P<ms>\d{3})"
)


def ultimo(
    patron: str,
) -> Path:
    archivos = [
        ruta
        for ruta in ROOT.glob(patron)
        if ruta.is_file()
    ]

    if not archivos:
        raise FileNotFoundError(
            f"No se encontro ningun archivo para: {patron}"
        )

    return max(
        archivos,
        key=lambda ruta: ruta.stat().st_mtime,
    )


def resolver_ruta(
    valor: str | None,
    patron: str,
) -> Path:
    if valor:
        ruta = Path(valor).expanduser()

        if not ruta.is_absolute():
            ruta = ROOT / ruta

        ruta = ruta.resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe el archivo: {ruta}"
            )

        return ruta

    return ultimo(patron)


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


def calcular_fps(
    valor: str,
) -> float:
    texto = str(valor or "0")

    if "/" in texto:
        numerador, denominador = texto.split(
            "/",
            1,
        )

        divisor = numero(
            denominador,
            1.0,
        )

        if divisor == 0:
            return 0.0

        return numero(
            numerador
        ) / divisor

    return numero(
        texto
    )


def analizar_multimedia(
    archivo: Path,
) -> dict[str, Any]:
    ffprobe = shutil.which(
        "ffprobe"
    )

    if not ffprobe:
        raise FileNotFoundError(
            "FFprobe no esta disponible en PATH."
        )

    proceso = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(archivo),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    if proceso.returncode != 0:
        raise RuntimeError(
            "FFprobe no pudo analizar el video:\n"
            + proceso.stderr[-1500:]
        )

    datos = json.loads(
        proceso.stdout
    )

    if not isinstance(datos, dict):
        raise RuntimeError(
            "FFprobe no devolvio datos validos."
        )

    return datos


def registrar(
    informe: dict[str, Any],
    nivel: str,
    codigo: str,
    mensaje: str,
) -> None:
    informe[nivel].append(
        {
            "codigo": codigo,
            "mensaje": mensaje,
        }
    )


def buscar_stream(
    streams: list[dict[str, Any]],
    tipo: str,
) -> dict[str, Any] | None:
    for stream in streams:
        if (
            isinstance(stream, dict)
            and stream.get("codec_type") == tipo
        ):
            return stream

    return None


def tiempo_srt(
    texto: str,
) -> float:
    coincidencia = PATRON_TIEMPO.fullmatch(
        texto.strip()
    )

    if not coincidencia:
        raise ValueError(
            f"Tiempo SRT invalido: {texto}"
        )

    return (
        int(coincidencia.group("h")) * 3600
        + int(coincidencia.group("m")) * 60
        + int(coincidencia.group("s"))
        + int(coincidencia.group("ms")) / 1000
    )


def analizar_srt(
    ruta: Path,
) -> dict[str, Any]:
    contenido = ruta.read_text(
        encoding="utf-8-sig"
    ).strip()

    bloques = re.split(
        r"\r?\n\s*\r?\n",
        contenido,
    )

    eventos: list[dict[str, Any]] = []
    invalidos = 0

    for bloque in bloques:
        lineas = [
            linea.strip()
            for linea in bloque.splitlines()
            if linea.strip()
        ]

        linea_tiempo = next(
            (
                linea
                for linea in lineas
                if "-->" in linea
            ),
            None,
        )

        if not linea_tiempo:
            invalidos += 1
            continue

        partes = [
            parte.strip()
            for parte in linea_tiempo.split(
                "-->",
                1,
            )
        ]

        try:
            inicio = tiempo_srt(
                partes[0]
            )
            final = tiempo_srt(
                partes[1]
            )
        except (
            IndexError,
            ValueError,
        ):
            invalidos += 1
            continue

        indice_tiempo = lineas.index(
            linea_tiempo
        )

        texto = " ".join(
            lineas[indice_tiempo + 1:]
        ).strip()

        eventos.append(
            {
                "inicio": inicio,
                "final": final,
                "texto": texto,
            }
        )

    solapamientos = 0
    duraciones_invalidas = 0
    textos_vacios = 0
    subtitulos_largos = 0

    for posicion, evento in enumerate(
        eventos
    ):
        if evento["final"] <= evento["inicio"]:
            duraciones_invalidas += 1

        if not evento["texto"]:
            textos_vacios += 1

        if (
            evento["final"]
            - evento["inicio"]
            > 15
        ):
            subtitulos_largos += 1

        if (
            posicion > 0
            and evento["inicio"]
            < eventos[posicion - 1]["final"]
            - 0.05
        ):
            solapamientos += 1

    return {
        "cantidad": len(eventos),
        "invalidos": invalidos,
        "solapamientos": solapamientos,
        "duraciones_invalidas": duraciones_invalidas,
        "textos_vacios": textos_vacios,
        "subtitulos_largos": subtitulos_largos,
        "inicio": (
            eventos[0]["inicio"]
            if eventos
            else 0.0
        ),
        "final": (
            eventos[-1]["final"]
            if eventos
            else 0.0
        ),
    }


def validar_video(
    informe: dict[str, Any],
    video: Path,
) -> float:
    datos = analizar_multimedia(
        video
    )

    formato = datos.get(
        "format",
        {},
    )

    streams = datos.get(
        "streams",
        [],
    )

    if not isinstance(streams, list):
        streams = []

    duracion = numero(
        formato.get(
            "duration",
            0,
        )
    )

    bitrate = int(
        numero(
            formato.get(
                "bit_rate",
                0,
            )
        )
    )

    video_stream = buscar_stream(
        streams,
        "video",
    )

    audio_stream = buscar_stream(
        streams,
        "audio",
    )

    informe["video"] = {
        "archivo": str(
            video.resolve()
        ),
        "tamano_bytes": video.stat().st_size,
        "duracion_segundos": round(
            duracion,
            3,
        ),
        "bitrate_total": bitrate,
    }

    if video.stat().st_size < 1024 * 1024:
        registrar(
            informe,
            "errores",
            "VIDEO_DEMASIADO_PEQUENO",
            "El archivo de video pesa menos de 1 MB.",
        )

    if duracion < 60:
        registrar(
            informe,
            "errores",
            "DURACION_INVALIDA",
            "El documental dura menos de 60 segundos.",
        )

    if video_stream is None:
        registrar(
            informe,
            "errores",
            "SIN_VIDEO",
            "El archivo no contiene una pista de video.",
        )
    else:
        ancho = int(
            numero(
                video_stream.get(
                    "width",
                    0,
                )
            )
        )

        alto = int(
            numero(
                video_stream.get(
                    "height",
                    0,
                )
            )
        )

        fps = calcular_fps(
            str(
                video_stream.get(
                    "avg_frame_rate",
                    "0",
                )
            )
        )

        codec = str(
            video_stream.get(
                "codec_name",
                "",
            )
        )

        pix_fmt = str(
            video_stream.get(
                "pix_fmt",
                "",
            )
        )

        informe["video"].update(
            {
                "ancho": ancho,
                "alto": alto,
                "fps": round(
                    fps,
                    3,
                ),
                "codec_video": codec,
                "pixel_format": pix_fmt,
            }
        )

        if ancho < 1280 or alto < 720:
            registrar(
                informe,
                "errores",
                "RESOLUCION_BAJA",
                f"Resolucion insuficiente: {ancho}x{alto}.",
            )

        if fps < 23:
            registrar(
                informe,
                "errores",
                "FPS_BAJO",
                f"Velocidad de cuadros insuficiente: {fps:.2f}.",
            )

        if codec not in {
            "h264",
            "hevc",
            "av1",
        }:
            registrar(
                informe,
                "advertencias",
                "CODEC_VIDEO_NO_RECOMENDADO",
                f"Codec de video detectado: {codec}.",
            )

        if pix_fmt not in {
            "yuv420p",
            "yuvj420p",
            "nv12",
        }:
            registrar(
                informe,
                "advertencias",
                "FORMATO_PIXEL",
                f"Formato de pixel detectado: {pix_fmt}.",
            )

    if audio_stream is None:
        registrar(
            informe,
            "errores",
            "SIN_AUDIO",
            "El archivo no contiene una pista de audio.",
        )
    else:
        codec_audio = str(
            audio_stream.get(
                "codec_name",
                "",
            )
        )

        frecuencia = int(
            numero(
                audio_stream.get(
                    "sample_rate",
                    0,
                )
            )
        )

        canales = int(
            numero(
                audio_stream.get(
                    "channels",
                    0,
                )
            )
        )

        informe["video"].update(
            {
                "codec_audio": codec_audio,
                "frecuencia_audio": frecuencia,
                "canales_audio": canales,
            }
        )

        if frecuencia < 44100:
            registrar(
                informe,
                "advertencias",
                "FRECUENCIA_AUDIO_BAJA",
                f"Frecuencia de audio detectada: {frecuencia} Hz.",
            )

        if canales < 1:
            registrar(
                informe,
                "errores",
                "CANALES_AUDIO_INVALIDOS",
                "No se detectaron canales de audio validos.",
            )

        if codec_audio != "aac":
            registrar(
                informe,
                "advertencias",
                "CODEC_AUDIO_NO_RECOMENDADO",
                f"Codec de audio detectado: {codec_audio}.",
            )

    return duracion


def validar_subtitulos(
    informe: dict[str, Any],
    srt: Path,
    duracion_video: float,
) -> None:
    resultado = analizar_srt(
        srt
    )

    informe["subtitulos"] = {
        "archivo": str(
            srt.resolve()
        ),
        **resultado,
    }

    if resultado["cantidad"] == 0:
        registrar(
            informe,
            "errores",
            "SRT_VACIO",
            "No se encontraron subtitulos validos.",
        )

    if resultado["invalidos"] > 0:
        registrar(
            informe,
            "errores",
            "SRT_INVALIDO",
            f"Bloques SRT invalidos: {resultado['invalidos']}.",
        )

    if resultado["duraciones_invalidas"] > 0:
        registrar(
            informe,
            "errores",
            "TIEMPOS_SRT_INVALIDOS",
            "Hay subtitulos con duracion igual o menor que cero.",
        )

    if resultado["textos_vacios"] > 0:
        registrar(
            informe,
            "errores",
            "SUBTITULOS_VACIOS",
            f"Subtitulos sin texto: {resultado['textos_vacios']}.",
        )

    if resultado["solapamientos"] > 0:
        registrar(
            informe,
            "advertencias",
            "SOLAPAMIENTOS_SRT",
            f"Solapamientos detectados: {resultado['solapamientos']}.",
        )

    if resultado["subtitulos_largos"] > 0:
        registrar(
            informe,
            "advertencias",
            "SUBTITULOS_MUY_LARGOS",
            f"Subtitulos visibles mas de 15 s: {resultado['subtitulos_largos']}.",
        )

    if resultado["final"] > duracion_video + 1.5:
        registrar(
            informe,
            "errores",
            "SRT_EXCEDE_VIDEO",
            "Los subtitulos terminan despues del video.",
        )

    diferencia_final = (
        duracion_video
        - resultado["final"]
    )

    if (
        resultado["cantidad"] > 0
        and diferencia_final > 20
    ):
        registrar(
            informe,
            "advertencias",
            "SRT_TERMINA_TEMPRANO",
            (
                "Los subtitulos terminan "
                f"{diferencia_final:.1f} s antes del video."
            ),
        )


def validar_miniatura(
    informe: dict[str, Any],
    miniatura: Path,
) -> None:
    with Image.open(
        miniatura
    ) as imagen:
        ancho, alto = imagen.size
        formato = str(
            imagen.format
            or ""
        )

        imagen.verify()

    tamano = miniatura.stat().st_size

    informe["miniatura"] = {
        "archivo": str(
            miniatura.resolve()
        ),
        "ancho": ancho,
        "alto": alto,
        "formato": formato,
        "tamano_bytes": tamano,
    }

    if (
        ancho != 1280
        or alto != 720
    ):
        registrar(
            informe,
            "errores",
            "MINIATURA_DIMENSIONES",
            (
                "La miniatura debe medir 1280x720; "
                f"se detecto {ancho}x{alto}."
            ),
        )

    if tamano > 2 * 1024 * 1024:
        registrar(
            informe,
            "errores",
            "MINIATURA_PESO",
            "La miniatura supera 2 MB.",
        )

    if formato.upper() not in {
        "JPEG",
        "PNG",
    }:
        registrar(
            informe,
            "errores",
            "MINIATURA_FORMATO",
            f"Formato de miniatura no permitido: {formato}.",
        )


def validar_metadata(
    informe: dict[str, Any],
    metadata: Path,
) -> None:
    datos = json.loads(
        metadata.read_text(
            encoding="utf-8-sig"
        )
    )

    titulo = str(
        datos.get(
            "title",
            "",
        )
    ).strip()

    descripcion = str(
        datos.get(
            "description",
            "",
        )
    ).strip()

    etiquetas = datos.get(
        "tags",
        [],
    )

    informe["metadata"] = {
        "archivo": str(
            metadata.resolve()
        ),
        "titulo": titulo,
        "longitud_titulo": len(
            titulo
        ),
        "longitud_descripcion": len(
            descripcion
        ),
        "cantidad_etiquetas": (
            len(etiquetas)
            if isinstance(etiquetas, list)
            else 0
        ),
    }

    if not titulo:
        registrar(
            informe,
            "errores",
            "TITULO_VACIO",
            "La metadata no contiene titulo.",
        )
    elif len(titulo) > 100:
        registrar(
            informe,
            "errores",
            "TITULO_LARGO",
            "El titulo supera 100 caracteres.",
        )

    if not descripcion:
        registrar(
            informe,
            "advertencias",
            "DESCRIPCION_VACIA",
            "La descripcion de YouTube esta vacia.",
        )
    elif len(descripcion) > 5000:
        registrar(
            informe,
            "errores",
            "DESCRIPCION_LARGA",
            "La descripcion supera 5000 caracteres.",
        )


def validar_shorts(
    informe: dict[str, Any],
    manifiesto: Path,
) -> None:
    """Valida los videos verticales incluidos en un manifiesto."""
    datos = json.loads(
        manifiesto.read_text(
            encoding="utf-8-sig"
        )
    )

    elementos = datos.get(
        "shorts",
        [],
    )

    if (
        not isinstance(elementos, list)
        or not elementos
    ):
        registrar(
            informe,
            "errores",
            "SHORTS_MANIFIESTO_VACIO",
            "El manifiesto no contiene Shorts validos.",
        )
        return

    informe["manifiesto_shorts"] = str(
        manifiesto.resolve()
    )

    resultados: list[
        dict[str, Any]
    ] = []

    for posicion, elemento in enumerate(
        elementos,
        start=1,
    ):
        if not isinstance(
            elemento,
            dict,
        ):
            registrar(
                informe,
                "errores",
                "SHORT_INVALIDO",
                f"El Short {posicion} no contiene datos validos.",
            )
            continue

        orden = int(
            numero(
                elemento.get(
                    "orden",
                    posicion,
                ),
                posicion,
            )
        )

        archivo = Path(
            str(
                elemento.get(
                    "archivo",
                    "",
                )
            )
        ).expanduser()

        if not archivo.is_absolute():
            archivo = (
                manifiesto.parent
                / archivo
            )

        archivo = archivo.resolve()

        if not archivo.is_file():
            registrar(
                informe,
                "errores",
                "SHORT_NO_EXISTE",
                f"No existe el Short {orden}: {archivo}",
            )
            continue

        datos_media = analizar_multimedia(
            archivo
        )

        formato = datos_media.get(
            "format",
            {},
        )

        streams = datos_media.get(
            "streams",
            [],
        )

        if not isinstance(
            streams,
            list,
        ):
            streams = []

        video_stream = buscar_stream(
            streams,
            "video",
        )

        audio_stream = buscar_stream(
            streams,
            "audio",
        )

        duracion = numero(
            formato.get(
                "duration",
                0,
            )
        )

        resultado = {
            "orden": orden,
            "archivo": str(
                archivo
            ),
            "tamano_bytes": archivo.stat().st_size,
            "duracion_segundos": round(
                duracion,
                3,
            ),
        }

        if archivo.stat().st_size < 100 * 1024:
            registrar(
                informe,
                "errores",
                "SHORT_DEMASIADO_PEQUENO",
                f"El Short {orden} pesa menos de 100 KB.",
            )

        if duracion < 10:
            registrar(
                informe,
                "errores",
                "SHORT_MUY_CORTO",
                f"El Short {orden} dura menos de 10 segundos.",
            )

        if duracion > 180.5:
            registrar(
                informe,
                "errores",
                "SHORT_MUY_LARGO",
                f"El Short {orden} supera 180 segundos.",
            )

        if video_stream is None:
            registrar(
                informe,
                "errores",
                "SHORT_SIN_VIDEO",
                f"El Short {orden} no contiene pista de video.",
            )
        else:
            ancho = int(
                numero(
                    video_stream.get(
                        "width",
                        0,
                    )
                )
            )

            alto = int(
                numero(
                    video_stream.get(
                        "height",
                        0,
                    )
                )
            )

            fps = calcular_fps(
                str(
                    video_stream.get(
                        "avg_frame_rate",
                        "0",
                    )
                )
            )

            resultado.update(
                {
                    "ancho": ancho,
                    "alto": alto,
                    "fps": round(
                        fps,
                        3,
                    ),
                    "codec_video": str(
                        video_stream.get(
                            "codec_name",
                            "",
                        )
                    ),
                }
            )

            if alto <= ancho:
                registrar(
                    informe,
                    "errores",
                    "SHORT_NO_VERTICAL",
                    (
                        f"El Short {orden} no es vertical: "
                        f"{ancho}x{alto}."
                    ),
                )

            if ancho < 720 or alto < 1280:
                registrar(
                    informe,
                    "errores",
                    "SHORT_RESOLUCION_BAJA",
                    (
                        f"Resolucion insuficiente en Short {orden}: "
                        f"{ancho}x{alto}."
                    ),
                )

            if fps < 23:
                registrar(
                    informe,
                    "errores",
                    "SHORT_FPS_BAJO",
                    (
                        f"El Short {orden} tiene "
                        f"{fps:.2f} FPS."
                    ),
                )

        if audio_stream is None:
            registrar(
                informe,
                "errores",
                "SHORT_SIN_AUDIO",
                f"El Short {orden} no contiene audio.",
            )
        else:
            resultado.update(
                {
                    "codec_audio": str(
                        audio_stream.get(
                            "codec_name",
                            "",
                        )
                    ),
                    "frecuencia_audio": int(
                        numero(
                            audio_stream.get(
                                "sample_rate",
                                0,
                            )
                        )
                    ),
                }
            )

        resultados.append(
            resultado
        )

    informe["shorts"] = resultados


def validar_analisis_profundo(
    informe: dict[str, Any],
    video: Path,
    duracion_video: float,
) -> None:
    """Busca negro, silencio y niveles anormales con FFmpeg."""
    ffmpeg = shutil.which(
        "ffmpeg"
    )

    if not ffmpeg:
        raise FileNotFoundError(
            "FFmpeg no esta disponible en PATH."
        )

    timeout = int(
        max(
            600,
            min(
                3600,
                duracion_video * 4,
            ),
        )
    )

    proceso = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-vf",
            "blackdetect=d=3:pix_th=0.10",
            "-af",
            (
                "silencedetect=noise=-45dB:d=8,"
                "volumedetect"
            ),
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )

    salida = (
        proceso.stderr
        or ""
    )

    if proceso.returncode != 0:
        raise RuntimeError(
            "FFmpeg no pudo completar el analisis profundo:\n"
            + salida[-1500:]
        )

    negros = [
        numero(valor)
        for valor in re.findall(
            r"black_duration:([0-9.]+)",
            salida,
        )
    ]

    silencios = [
        numero(valor)
        for valor in re.findall(
            r"silence_duration:\s*([0-9.]+)",
            salida,
        )
    ]

    coincidencia_media = re.findall(
        r"mean_volume:\s*(-?[0-9.]+)\s*dB",
        salida,
    )

    coincidencia_maxima = re.findall(
        r"max_volume:\s*(-?[0-9.]+)\s*dB",
        salida,
    )

    volumen_medio = (
        numero(
            coincidencia_media[-1]
        )
        if coincidencia_media
        else None
    )

    volumen_maximo = (
        numero(
            coincidencia_maxima[-1]
        )
        if coincidencia_maxima
        else None
    )

    negro_maximo = max(
        negros,
        default=0.0,
    )

    silencio_maximo = max(
        silencios,
        default=0.0,
    )

    informe["analisis_profundo"] = {
        "tramos_negros": len(
            negros
        ),
        "negro_maximo_segundos": round(
            negro_maximo,
            3,
        ),
        "negro_total_segundos": round(
            sum(negros),
            3,
        ),
        "tramos_silenciosos": len(
            silencios
        ),
        "silencio_maximo_segundos": round(
            silencio_maximo,
            3,
        ),
        "silencio_total_segundos": round(
            sum(silencios),
            3,
        ),
        "volumen_medio_db": volumen_medio,
        "volumen_maximo_db": volumen_maximo,
    }

    if negro_maximo >= 30:
        registrar(
            informe,
            "errores",
            "TRAMO_NEGRO_CRITICO",
            (
                "Se detecto un tramo negro de "
                f"{negro_maximo:.1f} segundos."
            ),
        )
    elif negro_maximo >= 5:
        registrar(
            informe,
            "advertencias",
            "TRAMO_NEGRO",
            (
                "Se detecto un tramo negro de "
                f"{negro_maximo:.1f} segundos."
            ),
        )

    if silencio_maximo >= 30:
        registrar(
            informe,
            "errores",
            "SILENCIO_CRITICO",
            (
                "Se detecto un silencio de "
                f"{silencio_maximo:.1f} segundos."
            ),
        )
    elif silencio_maximo >= 12:
        registrar(
            informe,
            "advertencias",
            "SILENCIO_PROLONGADO",
            (
                "Se detecto un silencio de "
                f"{silencio_maximo:.1f} segundos."
            ),
        )

    if (
        volumen_medio is not None
        and volumen_medio < -35
    ):
        registrar(
            informe,
            "advertencias",
            "VOLUMEN_MUY_BAJO",
            (
                "El volumen medio es bajo: "
                f"{volumen_medio:.1f} dB."
            ),
        )

    if (
        volumen_medio is not None
        and volumen_medio > -12
    ):
        registrar(
            informe,
            "advertencias",
            "VOLUMEN_MEDIO_ALTO",
            (
                "El volumen medio es alto: "
                f"{volumen_medio:.1f} dB."
            ),
        )

    if (
        volumen_maximo is not None
        and volumen_maximo > -0.1
    ):
        registrar(
            informe,
            "advertencias",
            "PICO_AUDIO_ALTO",
            (
                "El pico de audio esta cerca de saturacion: "
                f"{volumen_maximo:.1f} dB."
            ),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Control tecnico previo a la publicacion en YouTube."
        )
    )

    parser.add_argument(
        "--video",
        default=None,
    )
    parser.add_argument(
        "--subtitulos",
        default=None,
    )
    parser.add_argument(
        "--miniatura",
        default=None,
    )
    parser.add_argument(
        "--metadata",
        default=None,
    )
    parser.add_argument(
        "--validar-shorts",
        action="store_true",
        help="Valida tambien el lote de Shorts mas reciente.",
    )
    parser.add_argument(
        "--manifiesto-shorts",
        default=None,
        help="Ruta opcional del shorts_manifest.json.",
    )

    parser.add_argument(
        "--profundo",
        action="store_true",
        help=(
            "Analiza tramos negros, silencios "
            "y niveles de volumen."
        ),
    )

    args = parser.parse_args()

    video = resolver_ruta(
        args.video,
        (
            "output/videos/render_*/"
            "video_final_subtitulado_musica.mp4"
        ),
    )

    subtitulos = resolver_ruta(
        args.subtitulos,
        (
            "output/subtitles/"
            "subtitulos_*/subtitulos.srt"
        ),
    )

    if args.miniatura:
        miniatura = resolver_ruta(
            args.miniatura,
            "output/thumbnails/*.jpg",
        )
    else:
        preferida = (
            ROOT
            / "output"
            / "thumbnails"
            / "miniatura_youtube_autotube.jpg"
        )

        miniatura = (
            preferida
            if preferida.is_file()
            else ultimo(
                "output/thumbnails/*.jpg"
            )
        )

    metadata = resolver_ruta(
        args.metadata,
        "data/publish/metadata.json",
    )

    informe: dict[str, Any] = {
        "generado_en": (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        ),
        "estado": "pendiente",
        "errores": [],
        "advertencias": [],
        "video": {},
        "subtitulos": {},
        "miniatura": {},
        "metadata": {},
        "shorts": [],
    }

    print()
    print("CONTROL TECNICO MULTIMEDIA")
    print("=" * 72)
    print("Video:", video)
    print("Subtitulos:", subtitulos)
    print("Miniatura:", miniatura)
    print("Metadata:", metadata)
    print("=" * 72)

    try:
        duracion_video = validar_video(
            informe,
            video,
        )

        validar_subtitulos(
            informe,
            subtitulos,
            duracion_video,
        )

        validar_miniatura(
            informe,
            miniatura,
        )

        validar_metadata(
            informe,
            metadata,
        )

        if args.validar_shorts:
            manifiesto_shorts = resolver_ruta(
                args.manifiesto_shorts,
                (
                    "output/shorts/shorts_*/"
                    "shorts_manifest.json"
                ),
            )

            print(
                "Validando lote de Shorts..."
            )

            validar_shorts(
                informe,
                manifiesto_shorts,
            )

        if args.profundo:
            print(
                "Ejecutando analisis profundo con FFmpeg..."
            )
            validar_analisis_profundo(
                informe,
                video,
                duracion_video,
            )

    except Exception as error:
        registrar(
            informe,
            "errores",
            "FALLO_INSPECCION",
            str(error),
        )

    informe["estado"] = (
        "rechazado"
        if informe["errores"]
        else "aprobado"
    )

    carpeta = (
        ROOT
        / "data"
        / "quality"
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
        / f"media_quality_{marca}.json"
    )

    contenido = json.dumps(
        informe,
        ensure_ascii=False,
        indent=2,
    )

    salida.write_text(
        contenido,
        encoding="utf-8",
    )

    (
        carpeta
        / "media_quality_latest.json"
    ).write_text(
        contenido,
        encoding="utf-8",
    )

    print()
    print("RESULTADOS")
    print("-" * 72)
    print(
        "Duracion:",
        f"{informe['video'].get('duracion_segundos', 0):.1f} s",
    )
    print(
        "Resolucion:",
        (
            f"{informe['video'].get('ancho', 0)}x"
            f"{informe['video'].get('alto', 0)}"
        ),
    )
    print(
        "FPS:",
        informe["video"].get(
            "fps",
            0,
        ),
    )
    print(
        "Subtitulos:",
        informe["subtitulos"].get(
            "cantidad",
            0,
        ),
    )
    print(
        "Miniatura:",
        (
            f"{informe['miniatura'].get('ancho', 0)}x"
            f"{informe['miniatura'].get('alto', 0)}"
        ),
    )

    if args.validar_shorts:
        print(
            "Shorts validados:",
            len(
                informe.get(
                    "shorts",
                    [],
                )
            ),
        )

    if informe.get(
        "analisis_profundo"
    ):
        profundo = informe[
            "analisis_profundo"
        ]

        print(
            "Negro maximo:",
            (
                f"{profundo.get('negro_maximo_segundos', 0):.1f} s"
            ),
        )
        print(
            "Silencio maximo:",
            (
                f"{profundo.get('silencio_maximo_segundos', 0):.1f} s"
            ),
        )
        print(
            "Volumen medio:",
            profundo.get(
                "volumen_medio_db"
            ),
            "dB",
        )
        print(
            "Pico de audio:",
            profundo.get(
                "volumen_maximo_db"
            ),
            "dB",
        )

    if informe["errores"]:
        print()
        print("ERRORES")
        print("-" * 72)

        for elemento in informe["errores"]:
            print(
                f"[ERROR] {elemento['mensaje']}"
            )

    if informe["advertencias"]:
        print()
        print("ADVERTENCIAS")
        print("-" * 72)

        for elemento in informe["advertencias"]:
            print(
                f"[AVISO] {elemento['mensaje']}"
            )

    print()
    print("=" * 72)
    print(
        "RESULTADO:",
        informe["estado"].upper(),
    )
    print("Informe:", salida)
    print("=" * 72)

    return (
        1
        if informe["errores"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
