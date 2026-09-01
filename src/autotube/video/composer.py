from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.video.hardware_encoder import (
    ConfiguracionCodificador,
    describir_codificador,
    limpiar_salida_parcial,
    marcar_qsv_fallido,
    seleccionar_codificador,
)


EXTENSIONES_VIDEO = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
}

EXTENSIONES_IMAGEN = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}


def entero_seguro(
    valor: Any,
    predeterminado: int = 0,
) -> int:
    """Convierte un valor a entero sin detener el proceso."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return predeterminado


def flotante_seguro(
    valor: Any,
    predeterminado: float = 0.0,
) -> float:
    """Convierte un valor a decimal sin detener el proceso."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return predeterminado


def localizar_manifiesto_recursos(
    output_dir: Path,
    archivo: Path | None = None,
) -> Path:
    """Localiza el manifiesto de recursos más reciente."""
    if archivo is not None:
        ruta = archivo.expanduser().resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe el manifiesto de recursos: {ruta}"
            )

        return ruta

    archivos = sorted(
        (output_dir / "assets").glob(
            "coleccion_*/assets_manifest.json"
        ),
        key=lambda elemento: elemento.stat().st_mtime,
        reverse=True,
    )

    if not archivos:
        raise FileNotFoundError(
            "No se encontró ningún manifiesto de recursos."
        )

    return archivos[0]


def localizar_manifiesto_audio(
    output_dir: Path,
    archivo: Path | None = None,
) -> Path:
    """Localiza el manifiesto de audio más reciente."""
    if archivo is not None:
        ruta = archivo.expanduser().resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe el manifiesto de audio: {ruta}"
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


def cargar_contexto_render(
    output_dir: Path,
    archivo_assets: Path | None = None,
    archivo_audio: Path | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    Path,
    Path,
    Path,
]:
    """Carga recursos, audio y valida los archivos necesarios."""
    ruta_assets = localizar_manifiesto_recursos(
        output_dir=output_dir,
        archivo=archivo_assets,
    )

    ruta_audio_manifest = localizar_manifiesto_audio(
        output_dir=output_dir,
        archivo=archivo_audio,
    )

    assets = json.loads(
        ruta_assets.read_text(encoding="utf-8")
    )

    audio = json.loads(
        ruta_audio_manifest.read_text(encoding="utf-8")
    )

    elementos = assets.get("elementos")

    if not isinstance(elementos, list) or not elementos:
        raise RuntimeError(
            "El manifiesto no contiene recursos visuales."
        )

    audio_completo = str(
        audio.get(
            "audio_completo",
            "narracion_completa.mp3",
        )
    )

    ruta_audio = (
        ruta_audio_manifest.parent
        / audio_completo
    ).resolve()

    if not ruta_audio.is_file():
        raise FileNotFoundError(
            f"No existe la narración completa: {ruta_audio}"
        )

    disponibles = []

    for elemento in elementos:
        if not isinstance(elemento, dict):
            continue

        estado = str(
            elemento.get("estado", "")
        )

        if estado not in {
            "descargado",
            "generado_local",
        }:
            continue

        archivo = Path(
            str(elemento.get("archivo", ""))
        ).expanduser()

        if not archivo.is_file():
            raise FileNotFoundError(
                f"Falta el recurso visual: {archivo}"
            )

        duracion = flotante_seguro(
            elemento.get(
                "duracion_objetivo_segundos",
                0,
            )
        )

        if duracion <= 0:
            raise ValueError(
                f"Duración inválida para el recurso: {archivo}"
            )

        copia = dict(elemento)
        copia["archivo"] = str(
            archivo.resolve()
        )

        disponibles.append(copia)

    disponibles.sort(
        key=lambda elemento: (
            entero_seguro(
                elemento.get("segmento_indice")
            ),
            entero_seguro(
                elemento.get("clip_orden")
            ),
        )
    )

    if len(disponibles) != len(elementos):
        raise RuntimeError(
            "No todos los recursos del manifiesto están disponibles. "
            f"Disponibles: {len(disponibles)}/{len(elementos)}"
        )

    assets["elementos"] = disponibles

    titulo_assets = str(
        assets.get("titulo", "")
    ).strip()

    titulo_audio = str(
        audio.get("titulo", "")
    ).strip()

    if (
        titulo_assets
        and titulo_audio
        and titulo_assets != titulo_audio
    ):
        raise RuntimeError(
            "El manifiesto visual y el audio pertenecen "
            "a videos diferentes."
        )

    return (
        assets,
        audio,
        ruta_assets,
        ruta_audio_manifest,
        ruta_audio,
    )


def obtener_duracion(ruta: Path) -> float:
    """Obtiene la duración real de audio o video."""
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
        timeout=60,
    )

    return round(
        float(resultado.stdout.strip()),
        3,
    )


def sincronizar_duraciones_con_audio(
    elementos: list[dict[str, Any]],
    audio_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Ajusta cada grupo de clips a su audio real."""
    segmentos_audio = audio_manifest.get(
        "segmentos",
        [],
    )

    copias = [
        dict(elemento)
        for elemento in elementos
    ]

    if not isinstance(
        segmentos_audio,
        list,
    ):
        return copias

    grupos: dict[
        int,
        list[dict[str, Any]],
    ] = {}

    for elemento in copias:
        indice = entero_seguro(
            elemento.get(
                "segmento_indice",
                0,
            )
        )

        grupos.setdefault(
            indice,
            [],
        ).append(elemento)

    for indice, segmento_audio in enumerate(
        segmentos_audio,
        start=1,
    ):
        if not isinstance(
            segmento_audio,
            dict,
        ):
            continue

        grupo = grupos.get(
            indice,
            [],
        )

        if not grupo:
            continue

        duracion_objetivo = flotante_seguro(
            segmento_audio.get(
                "duracion_real_segundos",
                0,
            )
        )

        duracion_actual = sum(
            flotante_seguro(
                elemento.get(
                    "duracion_objetivo_segundos",
                    0,
                )
            )
            for elemento in grupo
        )

        if (
            duracion_objetivo <= 0
            or duracion_actual <= 0
        ):
            continue

        nuevas_duraciones = [
            round(
                duracion_objetivo
                * flotante_seguro(
                    elemento.get(
                        "duracion_objetivo_segundos",
                        0,
                    )
                )
                / duracion_actual,
                3,
            )
            for elemento in grupo
        ]

        diferencia = round(
            duracion_objetivo
            - sum(nuevas_duraciones),
            3,
        )

        nuevas_duraciones[-1] = round(
            nuevas_duraciones[-1]
            + diferencia,
            3,
        )

        for elemento, duracion in zip(
            grupo,
            nuevas_duraciones,
        ):
            elemento[
                "duracion_objetivo_segundos"
            ] = max(
                0.1,
                duracion,
            )

    return copias


class CompositorVideo:
    """Compone recursos visuales y narración utilizando FFmpeg."""

    def __init__(
        self,
        output_dir: Path,
    ) -> None:
        self.output_dir = output_dir

        if shutil.which("ffmpeg") is None:
            raise RuntimeError(
                "FFmpeg no está disponible."
            )

        if shutil.which("ffprobe") is None:
            raise RuntimeError(
                "ffprobe no está disponible."
            )

    def ejecutar_ffmpeg(
        self,
        argumentos: list[str],
        timeout: int = 1800,
    ) -> None:
        """Ejecuta FFmpeg mostrando un error reducido."""
        comando = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *argumentos,
        ]

        try:
            subprocess.run(
                comando,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
            )

        except subprocess.CalledProcessError as error:
            mensaje = (
                error.stderr
                or error.stdout
                or str(error)
            )

            raise RuntimeError(
                "FFmpeg no pudo completar el proceso:\n"
                + mensaje[-2500:]
            ) from error

    def filtro_base(
        self,
        ancho: int,
        alto: int,
        fps: int,
    ) -> str:
        """Escala y recorta respetando la proporción."""
        return (
            f"scale={ancho}:{alto}:"
            "force_original_aspect_ratio=increase,"
            f"crop={ancho}:{alto},"
            f"fps={fps},"
            "setsar=1,"
            "format=yuv420p"
        )

    def filtro_imagen(
        self,
        ancho: int,
        alto: int,
        fps: int,
        movimiento: str,
        identificador: str = "",
    ) -> str:
        """Añade movimiento contextual, suave y determinista."""
        movimiento_normalizado = movimiento.lower()

        sin_movimiento = any(
            texto in movimiento_normalizado
            for texto in (
                "sin movimiento",
                "corte directo",
                "estático",
                "estatico",
            )
        )

        if sin_movimiento:
            return self.filtro_base(
                ancho=ancho,
                alto=alto,
                fps=fps,
            )

        ancho_preparacion = max(
            ancho + 320,
            round(ancho * 1.18),
        )

        alto_preparacion = max(
            alto + 180,
            round(alto * 1.18),
        )

        # La dirección se deriva de un identificador estable. Así se
        # alternan los recorridos sin depender del azar ni cambiar al
        # reanudar una producción.
        firma = sum(
            (indice + 1) * ord(caracter)
            for indice, caracter in enumerate(identificador)
        )
        direccion_inversa = bool(firma % 2)

        zoom_expression = "min(zoom+0.00038,1.070)"
        x_expression = "iw/2-(iw/zoom/2)"
        y_expression = "ih/2-(ih/zoom/2)"

        if "paneo horizontal" in movimiento_normalizado:
            zoom_expression = "1.060"

            if direccion_inversa:
                x_expression = (
                    "max(0,iw-iw/zoom-on*0.35)"
                )
            else:
                x_expression = (
                    "min(iw-iw/zoom,on*0.35)"
                )

        elif "desplazamiento vertical" in movimiento_normalizado:
            zoom_expression = "1.060"

            if direccion_inversa:
                y_expression = (
                    "max(0,ih-ih/zoom-on*0.20)"
                )
            else:
                y_expression = (
                    "min(ih-ih/zoom,on*0.20)"
                )

        elif "acercamiento" in movimiento_normalizado:
            zoom_expression = "min(zoom+0.00060,1.100)"

        elif "zoom lento" in movimiento_normalizado:
            zoom_expression = "min(zoom+0.00038,1.070)"

        return (
            f"scale={ancho_preparacion}:{alto_preparacion}:"
            "force_original_aspect_ratio=increase,"
            f"crop={ancho_preparacion}:{alto_preparacion},"
            "zoompan="
            f"z='{zoom_expression}':"
            f"x='{x_expression}':"
            f"y='{y_expression}':"
            "d=1:"
            f"s={ancho}x{alto}:"
            f"fps={fps},"
            "setsar=1,"
            "format=yuv420p"
        )

    def renderizar_clip(
        self,
        elemento: dict[str, Any],
        destino: Path,
        ancho: int,
        alto: int,
        fps: int,
        crf: int,
        preset: str,
    ) -> None:
        """Normaliza un recurso individual."""
        origen = Path(
            str(elemento["archivo"])
        )

        duracion = flotante_seguro(
            elemento.get(
                "duracion_objetivo_segundos",
                0,
            )
        )

        movimiento = str(
            elemento.get("movimiento", "")
        )

        extension = origen.suffix.lower()

        if extension in EXTENSIONES_IMAGEN:
            filtro = self.filtro_imagen(
                ancho=ancho,
                alto=alto,
                fps=fps,
                movimiento=movimiento,
                identificador=str(
                    elemento.get("clip_id")
                    or elemento.get("id")
                    or origen
                ),
            )

            entrada = [
                "-loop",
                "1",
                "-framerate",
                str(fps),
                "-i",
                str(origen),
            ]

        elif extension in EXTENSIONES_VIDEO:
            filtro = self.filtro_base(
                ancho=ancho,
                alto=alto,
                fps=fps,
            )

            entrada = [
                "-stream_loop",
                "-1",
                "-i",
                str(origen),
            ]

        else:
            raise ValueError(
                f"Formato visual no compatible: {origen}"
            )

        configuracion = seleccionar_codificador(
            crf_cpu=crf,
            preset_cpu=preset,
            preferir_qsv=False,
        )

        def argumentos_codificacion(
            seleccion: ConfiguracionCodificador,
        ) -> list[str]:
            filtro_salida = filtro

            if seleccion.hardware:
                filtro_salida += ",format=nv12"

            opciones_gop = [
                "-g",
                str(fps * 2),
            ]

            if not seleccion.hardware:
                opciones_gop.extend(
                    [
                        "-keyint_min",
                        str(fps * 2),
                        "-sc_threshold",
                        "0",
                    ]
                )

            return [
                *entrada,
                "-t",
                f"{duracion:.3f}",
                "-an",
                "-vf",
                filtro_salida,
                "-r",
                str(fps),
                *seleccion.opciones,
                *opciones_gop,
                "-video_track_timescale",
                "90000",
                "-movflags",
                "+faststart",
                str(destino),
            ]

        try:
            self.ejecutar_ffmpeg(
                argumentos_codificacion(
                    configuracion
                ),
                timeout=900,
            )

        except RuntimeError as error:
            if not configuracion.hardware:
                raise

            print(
                "AVISO: Quick Sync fallo en un clip. "
                "Reintentando por CPU..."
            )

            marcar_qsv_fallido(
                error
            )

            limpiar_salida_parcial(
                destino
            )

            configuracion = (
                seleccionar_codificador(
                    crf_cpu=crf,
                    preset_cpu=preset,
                )
            )

            self.ejecutar_ffmpeg(
                argumentos_codificacion(
                    configuracion
                ),
                timeout=900,
            )

        if (
            not destino.is_file()
            or destino.stat().st_size == 0
        ):
            raise RuntimeError(
                f"No se generó el clip normalizado: {destino}"
            )

    def concatenar(
        self,
        clips: list[Path],
        destino: Path,
        trabajo: Path,
        crf: int,
        preset: str,
    ) -> None:
        """Concatena todos los clips normalizados."""
        lista = trabajo / "lista_clips.txt"

        lineas = []

        for clip in clips:
            ruta = clip.resolve().as_posix()
            ruta = ruta.replace(
                "'",
                r"'\''",
            )

            lineas.append(
                f"file '{ruta}'"
            )

        lista.write_text(
            "\n".join(lineas) + "\n",
            encoding="utf-8",
        )

        try:
            self.ejecutar_ffmpeg(
                [
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(lista),
                    "-an",
                    "-c:v",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(destino),
                ],
                timeout=1800,
            )

        except RuntimeError:
            self.ejecutar_ffmpeg(
                [
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(lista),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    preset,
                    "-crf",
                    str(crf),
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(destino),
                ],
                timeout=3600,
            )

    def agregar_audio(
        self,
        video: Path,
        audio: Path,
        destino: Path,
        duracion: float,
    ) -> None:
        """Añade la narración al video."""
        self.ejecutar_ffmpeg(
            [
                "-i",
                str(video),
                "-i",
                str(audio),
                "-t",
                f"{duracion:.3f}",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                str(destino),
            ],
            timeout=1800,
        )

    def renderizar(
        self,
        assets: dict[str, Any],
        audio_manifest: dict[str, Any],
        ruta_assets: Path,
        ruta_audio_manifest: Path,
        ruta_audio: Path,
        preview: bool = False,
        limite_clips: int | None = None,
        conservar_temporales: bool = False,
    ) -> dict[str, Any]:
        """Renderiza una vista previa o el video completo."""
        elementos = list(
            assets["elementos"]
        )

        elementos = sincronizar_duraciones_con_audio(
            elementos=elementos,
            audio_manifest=audio_manifest,
        )

        if preview:
            limite_efectivo = (
                limite_clips
                if limite_clips is not None
                else 8
            )
        else:
            limite_efectivo = (
                limite_clips
                if limite_clips is not None
                else 0
            )

        if limite_efectivo < 0:
            raise ValueError(
                "El límite de clips no puede ser negativo."
            )

        if limite_efectivo > 0:
            elementos = elementos[
                :limite_efectivo
            ]

        if not elementos:
            raise RuntimeError(
                "No hay clips disponibles para renderizar."
            )

        if preview:
            ancho = 1280
            alto = 720
            fps = 24
            crf = 27
            preset = "veryfast"
            nombre_final = "preview.mp4"
        else:
            ancho = 1920
            alto = 1080
            fps = 30
            crf = 23
            preset = "veryfast"
            nombre_final = "video_final.mp4"

        configuracion_inicial = seleccionar_codificador(
            crf_cpu=crf,
            preset_cpu=preset,
            preferir_qsv=False,
        )

        print(
            "Codificacion de clips:",
            describir_codificador(
                configuracion_inicial
            ),
        )

        marca_tiempo = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        carpeta_salida = (
            self.output_dir
            / "videos"
            / f"render_{marca_tiempo}"
        )

        trabajo = carpeta_salida / "work"

        trabajo.mkdir(
            parents=True,
            exist_ok=True,
        )

        clips_normalizados: list[Path] = []

        for indice, elemento in enumerate(
            elementos,
            start=1,
        ):
            titulo = str(
                elemento.get(
                    "segmento_titulo",
                    "Sin título",
                )
            )

            orden = entero_seguro(
                elemento.get("clip_orden")
            )

            print(
                f"Renderizando clip "
                f"{indice}/{len(elementos)}: "
                f"{titulo} | clip {orden}"
            )

            destino_clip = (
                trabajo
                / f"clip_{indice:03d}.mp4"
            )

            self.renderizar_clip(
                elemento=elemento,
                destino=destino_clip,
                ancho=ancho,
                alto=alto,
                fps=fps,
                crf=crf,
                preset=preset,
            )

            clips_normalizados.append(
                destino_clip
            )

        duracion_visual_objetivo = round(
            sum(
                flotante_seguro(
                    elemento.get(
                        "duracion_objetivo_segundos",
                        0,
                    )
                )
                for elemento in elementos
            ),
            3,
        )

        video_sin_audio = (
            carpeta_salida
            / "video_sin_audio.mp4"
        )

        print("Concatenando clips...")

        self.concatenar(
            clips=clips_normalizados,
            destino=video_sin_audio,
            trabajo=trabajo,
            crf=crf,
            preset=preset,
        )

        duracion_video = obtener_duracion(
            video_sin_audio
        )

        duracion_audio = obtener_duracion(
            ruta_audio
        )

        duracion_final_objetivo = min(
            duracion_visual_objetivo,
            duracion_video,
            duracion_audio,
        )

        video_final = (
            carpeta_salida
            / nombre_final
        )

        print("Añadiendo narración...")

        self.agregar_audio(
            video=video_sin_audio,
            audio=ruta_audio,
            destino=video_final,
            duracion=duracion_final_objetivo,
        )

        duracion_final = obtener_duracion(
            video_final
        )

        manifiesto = {
            "generado_en": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "modo": (
                "preview"
                if preview
                else "completo"
            ),
            "titulo": assets.get(
                "titulo",
                audio_manifest.get(
                    "titulo",
                    "Sin título",
                ),
            ),
            "resolucion": f"{ancho}x{alto}",
            "fps": fps,
            "cantidad_clips": len(elementos),
            "duracion_visual_objetivo_segundos": (
                duracion_visual_objetivo
            ),
            "duracion_video_segundos": duracion_video,
            "duracion_audio_segundos": duracion_audio,
            "duracion_final_segundos": duracion_final,
            "video_final": str(
                video_final.resolve()
            ),
            "manifiesto_recursos": str(
                ruta_assets.resolve()
            ),
            "manifiesto_audio": str(
                ruta_audio_manifest.resolve()
            ),
            "conservar_temporales": conservar_temporales,
        }

        ruta_manifiesto = (
            carpeta_salida
            / "render_manifest.json"
        )

        ruta_manifiesto.write_text(
            json.dumps(
                manifiesto,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        if not conservar_temporales:
            shutil.rmtree(
                trabajo,
                ignore_errors=True,
            )

            video_sin_audio.unlink(
                missing_ok=True
            )

        return {
            "video": video_final,
            "manifiesto": ruta_manifiesto,
            "duracion": duracion_final,
            "clips": len(elementos),
            "resolucion": f"{ancho}x{alto}",
            "modo": manifiesto["modo"],
        }
