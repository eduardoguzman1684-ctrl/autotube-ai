from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfiguracionCodificador:
    """Describe el codificador seleccionado para FFmpeg."""

    nombre: str
    hardware: bool
    opciones: tuple[str, ...]
    calidad: int


_ESTADO_QSV: bool | None = None
_MOTIVO_QSV = ""


def _modo_solicitado() -> str:
    modo = os.getenv(
        "AUTOTUBE_VIDEO_ENCODER",
        "auto",
    ).strip().lower()

    alias = {
        "h264_qsv": "qsv",
        "intel": "qsv",
        "quick_sync": "qsv",
        "libx264": "cpu",
        "x264": "cpu",
    }

    modo = alias.get(
        modo,
        modo,
    )

    if modo not in {
        "auto",
        "qsv",
        "cpu",
    }:
        raise ValueError(
            "AUTOTUBE_VIDEO_ENCODER debe ser "
            "auto, qsv o cpu."
        )

    return modo


def probar_qsv(
    forzar_prueba: bool = False,
) -> tuple[bool, str]:
    """Comprueba QSV mediante una codificacion corta real."""
    global _ESTADO_QSV
    global _MOTIVO_QSV

    if (
        _ESTADO_QSV is not None
        and not forzar_prueba
    ):
        return _ESTADO_QSV, _MOTIVO_QSV

    ffmpeg = shutil.which(
        "ffmpeg"
    )

    if not ffmpeg:
        _ESTADO_QSV = False
        _MOTIVO_QSV = (
            "FFmpeg no esta disponible."
        )
        return _ESTADO_QSV, _MOTIVO_QSV

    comando = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x360:rate=30",
        "-frames:v",
        "12",
        "-an",
        "-c:v",
        "h264_qsv",
        "-global_quality",
        "25",
        "-look_ahead",
        "0",
        "-f",
        "null",
        "-",
    ]

    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    except (
        OSError,
        subprocess.TimeoutExpired,
    ) as error:
        _ESTADO_QSV = False
        _MOTIVO_QSV = str(error)
        return _ESTADO_QSV, _MOTIVO_QSV

    if resultado.returncode == 0:
        _ESTADO_QSV = True
        _MOTIVO_QSV = (
            "Intel Quick Sync supero "
            "la prueba de codificacion."
        )
    else:
        _ESTADO_QSV = False
        _MOTIVO_QSV = (
            resultado.stderr
            or resultado.stdout
            or "La prueba QSV fallo."
        )[-1200:]

    return _ESTADO_QSV, _MOTIVO_QSV


def marcar_qsv_fallido(
    error: BaseException | str,
) -> None:
    """Desactiva QSV durante el resto del proceso."""
    global _ESTADO_QSV
    global _MOTIVO_QSV

    _ESTADO_QSV = False
    _MOTIVO_QSV = str(
        error
    )[-1200:]


def _calidad_qsv(
    crf_cpu: int,
) -> int:
    configurada = os.getenv(
        "AUTOTUBE_QSV_QUALITY",
        "",
    ).strip()

    if configurada:
        try:
            calidad = int(
                configurada
            )
        except ValueError as error:
            raise ValueError(
                "AUTOTUBE_QSV_QUALITY debe ser entero."
            ) from error
    else:
        calidad = int(
            crf_cpu
        ) + 2

    return min(
        31,
        max(
            18,
            calidad,
        ),
    )


def configuracion_cpu(
    crf: int,
    preset: str,
) -> ConfiguracionCodificador:
    return ConfiguracionCodificador(
        nombre="libx264",
        hardware=False,
        calidad=int(crf),
        opciones=(
            "-c:v",
            "libx264",
            "-preset",
            str(preset),
            "-crf",
            str(int(crf)),
            "-pix_fmt",
            "yuv420p",
        ),
    )


def seleccionar_codificador(
    crf_cpu: int,
    preset_cpu: str,
    preferir_qsv: bool = True,
) -> ConfiguracionCodificador:
    """Selecciona QSV automaticamente o devuelve CPU."""
    modo = _modo_solicitado()

    if (
        modo == "cpu"
        or (
            modo == "auto"
            and not preferir_qsv
        )
    ):
        return configuracion_cpu(
            crf=crf_cpu,
            preset=preset_cpu,
        )

    disponible, _ = probar_qsv()

    if disponible:
        calidad = _calidad_qsv(
            crf_cpu
        )

        return ConfiguracionCodificador(
            nombre="h264_qsv",
            hardware=True,
            calidad=calidad,
            opciones=(
                "-c:v",
                "h264_qsv",
                "-preset",
                "veryfast",
                "-global_quality",
                str(calidad),
                "-look_ahead",
                "0",
                "-pix_fmt",
                "nv12",
            ),
        )

    return configuracion_cpu(
        crf=crf_cpu,
        preset=preset_cpu,
    )


def describir_codificador(
    configuracion: ConfiguracionCodificador,
) -> str:
    if configuracion.hardware:
        return (
            "Intel Quick Sync "
            f"(h264_qsv, calidad "
            f"{configuracion.calidad})"
        )

    return (
        "CPU "
        f"(libx264, CRF "
        f"{configuracion.calidad})"
    )


def limpiar_salida_parcial(
    ruta: Path,
) -> None:
    try:
        ruta.unlink(
            missing_ok=True
        )
    except OSError:
        pass
