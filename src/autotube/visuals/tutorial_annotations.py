from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


COLOR_BORDE = (242, 201, 0, 255)
COLOR_RELLENO = (242, 201, 0, 28)


def normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize(
        "NFKD",
        texto or "",
    )

    return "".join(
        c
        for c in texto.lower()
        if not unicodedata.combining(c)
    )


def _rect_rel(
    width: int,
    height: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> tuple[int, int, int, int]:
    return (
        int(round(width * x1)),
        int(round(height * y1)),
        int(round(width * x2)),
        int(round(height * y2)),
    )


def _dibujar_cajas(
    ruta_imagen: Path,
    cajas: list[dict[str, Any]],
) -> None:
    with Image.open(ruta_imagen) as original:
        base = original.convert("RGBA")

    overlay = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(overlay)

    min_dim = min(base.size)
    grosor = max(
        4,
        int(round(min_dim * 0.0045)),
    )
    radio = max(
        10,
        int(round(min_dim * 0.012)),
    )

    width, height = base.size

    for caja in cajas:
        x1, y1, x2, y2 = _rect_rel(
            width,
            height,
            *caja["coords_rel"],
        )

        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            outline=COLOR_BORDE,
            fill=COLOR_RELLENO,
            width=grosor,
            radius=radio,
        )

    salida = Image.alpha_composite(
        base,
        overlay,
    )

    salida.save(ruta_imagen)


def _es_clip_make_barras(
    elemento: dict[str, Any],
) -> bool:
    texto = " ".join(
        str(elemento.get(clave, ""))
        for clave in (
            "plataforma",
            "pantalla_objetivo",
            "accion_visual",
            "descripcion_visual",
            "texto_narrado",
        )
    )

    texto = normalizar_texto(texto)

    if "make" not in texto:
        return False

    if (
        "vista general de interfaz del editor"
        in texto
    ):
        return True

    if (
        "resaltado con cajas amarillas"
        in texto
        and "barras de herramientas"
        in texto
    ):
        return True

    return False


def _anotacion_make_barras(
) -> list[dict[str, Any]]:
    return [
        {
            "nombre": "barra_lateral_izquierda",
            "coords_rel": (
                0.006,
                0.012,
                0.074,
                0.982,
            ),
        },
        {
            "nombre": "barra_superior_principal",
            "coords_rel": (
                0.090,
                0.026,
                0.592,
                0.104,
            ),
        },
        {
            "nombre": "barra_superior_derecha",
            "coords_rel": (
                0.758,
                0.026,
                0.968,
                0.102,
            ),
        },
        {
            "nombre": "barra_inferior",
            "coords_rel": (
                0.099,
                0.848,
                0.969,
                0.958,
            ),
        },
    ]


def aplicar_anotaciones_tutorial(
    ruta_imagen: str | Path,
    elemento: dict[str, Any],
) -> list[dict[str, Any]]:
    ruta = Path(ruta_imagen)

    if not ruta.is_file():
        return []

    if not _es_clip_make_barras(
        elemento
    ):
        return []

    cajas = _anotacion_make_barras()

    _dibujar_cajas(
        ruta,
        cajas,
    )

    return [
        {
            "tipo": "rectangulo_redondeado",
            "nombre": caja["nombre"],
            "coords_rel": caja["coords_rel"],
            "color_borde": "#F2C900",
        }
        for caja in cajas
    ]
