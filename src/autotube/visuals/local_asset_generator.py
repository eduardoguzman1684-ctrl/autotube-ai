from __future__ import annotations

import hashlib
import json
import math
import shutil
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ANCHO = 1920
ALTO = 1080

TIPOS_LOCALES = {
    "captura_interfaz",
    "grafico",
    "texto_animado",
}

FONDO_1 = (9, 15, 30)
FONDO_2 = (18, 31, 55)
PANEL = (23, 36, 61)
PANEL_CLARO = (35, 52, 82)
BLANCO = (241, 245, 249)
GRIS = (167, 180, 198)
AZUL = (63, 135, 245)
CIAN = (56, 205, 220)
VERDE = (61, 210, 151)
AMARILLO = (245, 190, 70)
ROJO = (239, 91, 109)


def localizar_manifiesto_assets(
    output_dir: Path,
    archivo: Path | None = None,
) -> Path:
    """Localiza el manifiesto de recursos más reciente."""
    if archivo is not None:
        ruta = archivo.expanduser().resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe el manifiesto indicado: {ruta}"
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


def cargar_manifiesto_assets(
    output_dir: Path,
    archivo: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Carga un manifiesto de recursos."""
    ruta = localizar_manifiesto_assets(
        output_dir=output_dir,
        archivo=archivo,
    )

    contenido = json.loads(
        ruta.read_text(encoding="utf-8")
    )

    elementos = contenido.get("elementos")

    if not isinstance(elementos, list):
        raise RuntimeError(
            "El manifiesto no contiene elementos válidos."
        )

    return contenido, ruta


def nombre_seguro(texto: str) -> str:
    """Crea un nombre de archivo corto y estable."""
    limpio = "".join(
        caracter.lower()
        if caracter.isalnum()
        else "_"
        for caracter in texto
    )

    partes = [
        parte
        for parte in limpio.split("_")
        if parte
    ]

    return "_".join(partes)[:45] or "recurso"


def obtener_fuente(
    tamano: int,
    negrita: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Carga una fuente de Windows con respaldo interno."""
    candidatos = []

    if negrita:
        candidatos.extend(
            [
                Path(r"C:\Windows\Fonts\seguisb.ttf"),
                Path(r"C:\Windows\Fonts\arialbd.ttf"),
                Path(r"C:\Windows\Fonts\calibrib.ttf"),
            ]
        )
    else:
        candidatos.extend(
            [
                Path(r"C:\Windows\Fonts\segoeui.ttf"),
                Path(r"C:\Windows\Fonts\arial.ttf"),
                Path(r"C:\Windows\Fonts\calibri.ttf"),
            ]
        )

    for candidato in candidatos:
        if candidato.is_file():
            try:
                return ImageFont.truetype(
                    str(candidato),
                    tamano,
                )
            except OSError:
                continue

    return ImageFont.load_default()


def crear_fondo() -> Image.Image:
    """Crea un fondo vertical degradado."""
    imagen = Image.new(
        "RGB",
        (ANCHO, ALTO),
        FONDO_1,
    )

    dibujo = ImageDraw.Draw(imagen)

    for y in range(ALTO):
        proporcion = y / max(1, ALTO - 1)

        color = tuple(
            round(
                FONDO_1[indice]
                + (
                    FONDO_2[indice]
                    - FONDO_1[indice]
                )
                * proporcion
            )
            for indice in range(3)
        )

        dibujo.line(
            [(0, y), (ANCHO, y)],
            fill=color,
        )

    return imagen


def texto_ajustado(
    dibujo: ImageDraw.ImageDraw,
    texto: str,
    fuente: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ancho_maximo: int,
    max_lineas: int = 4,
) -> list[str]:
    """Divide texto respetando el ancho en píxeles."""
    palabras = texto.strip().split()

    if not palabras:
        return [""]

    lineas: list[str] = []
    actual = ""

    for palabra in palabras:
        candidato = (
            f"{actual} {palabra}".strip()
        )

        caja = dibujo.textbbox(
            (0, 0),
            candidato,
            font=fuente,
        )

        ancho = caja[2] - caja[0]

        if ancho <= ancho_maximo:
            actual = candidato
            continue

        if actual:
            lineas.append(actual)

        actual = palabra

        if len(lineas) >= max_lineas:
            break

    if actual and len(lineas) < max_lineas:
        lineas.append(actual)

    texto_original = " ".join(palabras)
    texto_resultante = " ".join(lineas)

    if (
        texto_resultante != texto_original
        and lineas
    ):
        ultima = lineas[-1].rstrip(".,;:!?")

        while ultima:
            candidato = ultima + "…"

            caja = dibujo.textbbox(
                (0, 0),
                candidato,
                font=fuente,
            )

            if caja[2] - caja[0] <= ancho_maximo:
                lineas[-1] = candidato
                break

            ultima = ultima[:-1].rstrip()

    return lineas


def dibujar_lineas_centradas(
    dibujo: ImageDraw.ImageDraw,
    lineas: list[str],
    centro_x: int,
    inicio_y: int,
    fuente: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    color: tuple[int, int, int],
    separacion: int = 18,
) -> int:
    """Dibuja líneas centradas y devuelve la posición final."""
    y = inicio_y

    for linea in lineas:
        caja = dibujo.textbbox(
            (0, 0),
            linea,
            font=fuente,
        )

        ancho = caja[2] - caja[0]
        alto = caja[3] - caja[1]

        dibujo.text(
            (centro_x - ancho // 2, y),
            linea,
            font=fuente,
            fill=color,
        )

        y += alto + separacion

    return y


def color_acento(texto: str) -> tuple[int, int, int]:
    """Selecciona un color estable según el contenido."""
    colores = [
        AZUL,
        CIAN,
        VERDE,
        AMARILLO,
        ROJO,
    ]

    resumen = hashlib.sha256(
        texto.encode("utf-8")
    ).digest()

    return colores[
        resumen[0] % len(colores)
    ]


def contenido_principal(
    elemento: dict[str, Any],
) -> str:
    """Selecciona el texto principal del recurso."""
    texto_pantalla = str(
        elemento.get("texto_pantalla", "")
    ).strip()

    if texto_pantalla:
        return texto_pantalla

    descripcion = str(
        elemento.get("descripcion", "")
    ).strip()

    return descripcion or str(
        elemento.get(
            "segmento_titulo",
            "Nexo IA",
        )
    )


def dibujar_encabezado(
    dibujo: ImageDraw.ImageDraw,
    titulo: str,
    etiqueta: str,
    acento: tuple[int, int, int],
) -> None:
    """Dibuja identidad visual superior."""
    fuente_marca = obtener_fuente(
        31,
        negrita=True,
    )

    fuente_etiqueta = obtener_fuente(
        24,
        negrita=True,
    )

    dibujo.rounded_rectangle(
        (80, 55, 286, 112),
        radius=20,
        fill=acento,
    )

    dibujo.text(
        (112, 68),
        "NEXO IA",
        font=fuente_marca,
        fill=FONDO_1,
    )

    dibujo.text(
        (ANCHO - 80, 72),
        etiqueta.upper(),
        font=fuente_etiqueta,
        fill=GRIS,
        anchor="ra",
    )

    dibujo.line(
        (80, 140, ANCHO - 80, 140),
        fill=PANEL_CLARO,
        width=2,
    )


def generar_captura_interfaz(
    elemento: dict[str, Any],
) -> Image.Image:
    """Genera una interfaz genérica ilustrativa."""
    imagen = crear_fondo()
    dibujo = ImageDraw.Draw(imagen)

    titulo = str(
        elemento.get(
            "segmento_titulo",
            "Automatización",
        )
    )

    principal = contenido_principal(
        elemento
    )

    acento = color_acento(
        titulo + principal
    )

    dibujar_encabezado(
        dibujo,
        titulo,
        "Interfaz ilustrativa",
        acento,
    )

    ventana = (
        95,
        185,
        ANCHO - 95,
        ALTO - 70,
    )

    dibujo.rounded_rectangle(
        ventana,
        radius=34,
        fill=PANEL,
        outline=PANEL_CLARO,
        width=3,
    )

    dibujo.rounded_rectangle(
        (
            95,
            185,
            ANCHO - 95,
            260,
        ),
        radius=34,
        fill=(29, 44, 72),
    )

    dibujo.rectangle(
        (
            95,
            225,
            ANCHO - 95,
            260,
        ),
        fill=(29, 44, 72),
    )

    for indice, color in enumerate(
        [ROJO, AMARILLO, VERDE]
    ):
        x = 135 + indice * 38

        dibujo.ellipse(
            (x, 211, x + 18, 229),
            fill=color,
        )

    fuente_url = obtener_fuente(22)

    dibujo.rounded_rectangle(
        (
            310,
            204,
            ANCHO - 165,
            241,
        ),
        radius=14,
        fill=(16, 27, 47),
    )

    dibujo.text(
        (340, 211),
        "workspace.nexo-ia.local/automatizacion",
        font=fuente_url,
        fill=GRIS,
    )

    dibujo.rounded_rectangle(
        (
            120,
            285,
            390,
            ALTO - 100,
        ),
        radius=24,
        fill=(18, 30, 52),
    )

    fuente_menu = obtener_fuente(26)

    opciones = [
        "Panel general",
        "Entradas",
        "Procesamiento IA",
        "Resultados",
        "Historial",
    ]

    for indice, opcion in enumerate(
        opciones
    ):
        y = 340 + indice * 88

        if indice == 2:
            dibujo.rounded_rectangle(
                (145, y - 15, 365, y + 48),
                radius=16,
                fill=acento,
            )

            color_texto = FONDO_1
        else:
            color_texto = GRIS

        dibujo.text(
            (170, y),
            opcion,
            font=fuente_menu,
            fill=color_texto,
        )

    fuente_titulo = obtener_fuente(
        45,
        negrita=True,
    )

    dibujo.text(
        (455, 305),
        titulo[:58],
        font=fuente_titulo,
        fill=BLANCO,
    )

    nodos = [
        (
            475,
            470,
            800,
            690,
            "1",
            "Entrada",
            "Recibe datos",
        ),
        (
            900,
            470,
            1225,
            690,
            "2",
            "Procesamiento IA",
            "Analiza y transforma",
        ),
        (
            1325,
            470,
            1650,
            690,
            "3",
            "Resultado",
            "Entrega la salida",
        ),
    ]

    fuente_numero = obtener_fuente(
        35,
        negrita=True,
    )

    fuente_nodo = obtener_fuente(
        30,
        negrita=True,
    )

    fuente_detalle = obtener_fuente(23)

    for (
        izquierda,
        arriba,
        derecha,
        abajo,
        numero,
        nombre,
        detalle,
    ) in nodos:
        dibujo.rounded_rectangle(
            (
                izquierda,
                arriba,
                derecha,
                abajo,
            ),
            radius=28,
            fill=PANEL_CLARO,
            outline=acento,
            width=3,
        )

        dibujo.ellipse(
            (
                izquierda + 25,
                arriba + 25,
                izquierda + 83,
                arriba + 83,
            ),
            fill=acento,
        )

        dibujo.text(
            (
                izquierda + 54,
                arriba + 53,
            ),
            numero,
            font=fuente_numero,
            fill=FONDO_1,
            anchor="mm",
        )

        dibujo.text(
            (
                izquierda + 30,
                arriba + 115,
            ),
            nombre,
            font=fuente_nodo,
            fill=BLANCO,
        )

        dibujo.text(
            (
                izquierda + 30,
                arriba + 164,
            ),
            detalle,
            font=fuente_detalle,
            fill=GRIS,
        )

    for x1, x2 in [
        (800, 900),
        (1225, 1325),
    ]:
        centro_y = 580

        dibujo.line(
            (x1 + 12, centro_y, x2 - 20, centro_y),
            fill=acento,
            width=8,
        )

        dibujo.polygon(
            [
                (x2 - 20, centro_y - 14),
                (x2, centro_y),
                (x2 - 20, centro_y + 14),
            ],
            fill=acento,
        )

    fuente_principal = obtener_fuente(
        29,
        negrita=True,
    )

    lineas = texto_ajustado(
        dibujo,
        principal,
        fuente_principal,
        1110,
        max_lineas=2,
    )

    dibujo.rounded_rectangle(
        (
            455,
            770,
            1650,
            930,
        ),
        radius=24,
        fill=(15, 26, 45),
    )

    dibujar_lineas_centradas(
        dibujo,
        lineas,
        1052,
        805,
        fuente_principal,
        BLANCO,
        separacion=12,
    )

    fuente_aviso = obtener_fuente(20)

    dibujo.text(
        (ANCHO - 125, ALTO - 92),
        "Representación visual, no captura real",
        font=fuente_aviso,
        fill=GRIS,
        anchor="ra",
    )

    return imagen


def generar_grafico(
    elemento: dict[str, Any],
) -> Image.Image:
    """Genera un gráfico o diagrama educativo."""
    imagen = crear_fondo()
    dibujo = ImageDraw.Draw(imagen)

    titulo = str(
        elemento.get(
            "segmento_titulo",
            "Análisis",
        )
    )

    principal = contenido_principal(
        elemento
    )

    acento = color_acento(
        titulo + principal
    )

    dibujar_encabezado(
        dibujo,
        titulo,
        "Gráfico explicativo",
        acento,
    )

    fuente_titulo = obtener_fuente(
        54,
        negrita=True,
    )

    lineas = texto_ajustado(
        dibujo,
        principal,
        fuente_titulo,
        1500,
        max_lineas=2,
    )

    dibujar_lineas_centradas(
        dibujo,
        lineas,
        ANCHO // 2,
        190,
        fuente_titulo,
        BLANCO,
        separacion=12,
    )

    variante = hashlib.sha256(
        principal.encode("utf-8")
    ).digest()[0] % 3

    if variante == 0:
        _dibujar_barras(
            dibujo,
            acento,
        )
    elif variante == 1:
        _dibujar_flujo(
            dibujo,
            acento,
        )
    else:
        _dibujar_linea(
            dibujo,
            acento,
        )

    fuente_pie = obtener_fuente(22)

    dibujo.text(
        (ANCHO // 2, ALTO - 68),
        "Visualización conceptual para acompañar la narración",
        font=fuente_pie,
        fill=GRIS,
        anchor="mm",
    )

    return imagen


def _dibujar_barras(
    dibujo: ImageDraw.ImageDraw,
    acento: tuple[int, int, int],
) -> None:
    izquierda = 290
    arriba = 430
    derecha = 1630
    abajo = 900

    dibujo.rounded_rectangle(
        (
            izquierda,
            arriba,
            derecha,
            abajo,
        ),
        radius=30,
        fill=PANEL,
    )

    for indice in range(5):
        y = abajo - 80 - indice * 82

        dibujo.line(
            (
                izquierda + 110,
                y,
                derecha - 80,
                y,
            ),
            fill=PANEL_CLARO,
            width=2,
        )

    valores = [34, 52, 71, 91]
    etiquetas = [
        "Manual",
        "Organizado",
        "Automatizado",
        "Optimizado",
    ]

    colores = [
        ROJO,
        AMARILLO,
        CIAN,
        acento,
    ]

    fuente_valor = obtener_fuente(
        28,
        negrita=True,
    )

    fuente_etiqueta = obtener_fuente(24)

    ancho_barra = 180
    separacion = 90

    for indice, valor in enumerate(
        valores
    ):
        x = (
            izquierda
            + 190
            + indice
            * (ancho_barra + separacion)
        )

        altura = round(
            valor / 100 * 320
        )

        y = abajo - 85 - altura

        dibujo.rounded_rectangle(
            (
                x,
                y,
                x + ancho_barra,
                abajo - 85,
            ),
            radius=22,
            fill=colores[indice],
        )

        dibujo.text(
            (
                x + ancho_barra // 2,
                y - 35,
            ),
            f"{valor}%",
            font=fuente_valor,
            fill=BLANCO,
            anchor="mm",
        )

        dibujo.text(
            (
                x + ancho_barra // 2,
                abajo - 48,
            ),
            etiquetas[indice],
            font=fuente_etiqueta,
            fill=GRIS,
            anchor="mm",
        )


def _dibujar_flujo(
    dibujo: ImageDraw.ImageDraw,
    acento: tuple[int, int, int],
) -> None:
    fuente_numero = obtener_fuente(
        42,
        negrita=True,
    )

    fuente_titulo = obtener_fuente(
        30,
        negrita=True,
    )

    fuente_texto = obtener_fuente(23)

    nodos = [
        (
            220,
            "1",
            "Capturar",
            "Recibir información",
            CIAN,
        ),
        (
            680,
            "2",
            "Procesar",
            "Aplicar inteligencia",
            acento,
        ),
        (
            1140,
            "3",
            "Entregar",
            "Enviar el resultado",
            VERDE,
        ),
    ]

    for indice, (
        x,
        numero,
        titulo,
        detalle,
        color,
    ) in enumerate(nodos):
        dibujo.rounded_rectangle(
            (
                x,
                480,
                x + 360,
                790,
            ),
            radius=35,
            fill=PANEL,
            outline=color,
            width=4,
        )

        dibujo.ellipse(
            (
                x + 125,
                515,
                x + 235,
                625,
            ),
            fill=color,
        )

        dibujo.text(
            (
                x + 180,
                570,
            ),
            numero,
            font=fuente_numero,
            fill=FONDO_1,
            anchor="mm",
        )

        dibujo.text(
            (
                x + 180,
                680,
            ),
            titulo,
            font=fuente_titulo,
            fill=BLANCO,
            anchor="mm",
        )

        dibujo.text(
            (
                x + 180,
                730,
            ),
            detalle,
            font=fuente_texto,
            fill=GRIS,
            anchor="mm",
        )

        if indice < len(nodos) - 1:
            inicio = x + 375
            final = x + 445
            y = 635

            dibujo.line(
                (inicio, y, final, y),
                fill=acento,
                width=8,
            )

            dibujo.polygon(
                [
                    (final, y),
                    (final - 22, y - 17),
                    (final - 22, y + 17),
                ],
                fill=acento,
            )


def _dibujar_linea(
    dibujo: ImageDraw.ImageDraw,
    acento: tuple[int, int, int],
) -> None:
    izquierda = 260
    arriba = 430
    derecha = 1660
    abajo = 890

    dibujo.rounded_rectangle(
        (
            izquierda,
            arriba,
            derecha,
            abajo,
        ),
        radius=30,
        fill=PANEL,
    )

    for indice in range(5):
        y = arriba + 70 + indice * 78

        dibujo.line(
            (
                izquierda + 90,
                y,
                derecha - 80,
                y,
            ),
            fill=PANEL_CLARO,
            width=2,
        )

    puntos = [
        (360, 775),
        (590, 720),
        (820, 640),
        (1050, 665),
        (1280, 540),
        (1510, 475),
    ]

    dibujo.line(
        puntos,
        fill=acento,
        width=12,
        joint="curve",
    )

    for indice, (x, y) in enumerate(
        puntos,
        start=1,
    ):
        dibujo.ellipse(
            (
                x - 16,
                y - 16,
                x + 16,
                y + 16,
            ),
            fill=BLANCO,
            outline=acento,
            width=7,
        )

    fuente = obtener_fuente(24)

    etiquetas = [
        "Inicio",
        "Datos",
        "IA",
        "Prueba",
        "Mejora",
        "Resultado",
    ]

    for (x, _), etiqueta in zip(
        puntos,
        etiquetas,
    ):
        dibujo.text(
            (
                x,
                abajo - 35,
            ),
            etiqueta,
            font=fuente,
            fill=GRIS,
            anchor="mm",
        )


def generar_texto_animado(
    elemento: dict[str, Any],
) -> Image.Image:
    """Genera una tarjeta diseñada para animación posterior."""
    estilo_editorial = str(
        elemento.get("estilo_tarjeta", "")
    ).strip()
    if estilo_editorial:
        return generar_tarjeta_editorial(
            elemento,
            estilo_editorial,
        )

    imagen = crear_fondo()
    dibujo = ImageDraw.Draw(imagen)

    titulo = str(
        elemento.get(
            "segmento_titulo",
            "Nexo IA",
        )
    )

    principal = contenido_principal(
        elemento
    )

    acento = color_acento(
        titulo + principal
    )

    dibujar_encabezado(
        dibujo,
        titulo,
        "Texto destacado",
        acento,
    )

    dibujo.ellipse(
        (
            -180,
            710,
            390,
            1280,
        ),
        fill=(
            acento[0] // 3,
            acento[1] // 3,
            acento[2] // 3,
        ),
    )

    dibujo.ellipse(
        (
            1480,
            120,
            2110,
            750,
        ),
        fill=(20, 57, 85),
    )

    dibujo.rounded_rectangle(
        (
            220,
            255,
            ANCHO - 220,
            ALTO - 180,
        ),
        radius=55,
        fill=PANEL,
        outline=acento,
        width=5,
    )

    fuente_texto = obtener_fuente(
        80,
        negrita=True,
    )

    lineas = texto_ajustado(
        dibujo,
        principal,
        fuente_texto,
        1250,
        max_lineas=4,
    )

    altura_linea = 105
    altura_total = (
        len(lineas) * altura_linea
    )

    inicio_y = (
        ALTO // 2
        - altura_total // 2
        + 15
    )

    dibujar_lineas_centradas(
        dibujo,
        lineas,
        ANCHO // 2,
        inicio_y,
        fuente_texto,
        BLANCO,
        separacion=22,
    )

    dibujo.rounded_rectangle(
        (
            ANCHO // 2 - 165,
            ALTO - 255,
            ANCHO // 2 + 165,
            ALTO - 205,
        ),
        radius=20,
        fill=acento,
    )

    fuente_nexo = obtener_fuente(
        24,
        negrita=True,
    )

    dibujo.text(
        (
            ANCHO // 2,
            ALTO - 230,
        ),
        "NEXO IA",
        font=fuente_nexo,
        fill=FONDO_1,
        anchor="mm",
    )

    return imagen


def generar_tarjeta_editorial(
    elemento: dict[str, Any],
    estilo: str,
) -> Image.Image:
    """Genera tarjetas factuales con geometrías perceptualmente distintas."""
    imagen = crear_fondo()
    dibujo = ImageDraw.Draw(imagen)
    titulo = str(elemento.get("segmento_titulo", "Nexo IA"))
    principal = contenido_principal(elemento)
    acento = color_acento(estilo + principal)
    variantes = {
        "perfil_mccarthy": 0,
        "perfil_minsky": 1,
        "dupla_newell_simon": 2,
        "perfil_shannon": 3,
        "circuito_electromecanico": 4,
        "mesa_dartmouth": 5,
        "fundadores_dartmouth": 1,
        "flujo_inteligencia": 4,
        "documento_dartmouth": 6,
    }
    variante = variantes.get(
        estilo,
        hashlib.sha256(estilo.encode("utf-8")).digest()[0] % 7,
    )

    dibujar_encabezado(
        dibujo,
        titulo,
        "Evidencia histórica · tarjeta editorial",
        acento,
    )

    # Cada variante altera grandes masas claras y oscuras. Esto evita que dos
    # tarjetas consecutivas sean equivalentes para el hash perceptual, incluso
    # cuando comparten tipografía, cabecera o una fecha histórica.
    if variante == 0:
        dibujo.rectangle((0, 245, 330, ALTO), fill=acento)
        caja_texto = (430, 285, 1760, 865)
        centro_x = 1095
    elif variante == 1:
        dibujo.rounded_rectangle(
            (110, 245, 1810, 465), radius=42, fill=acento
        )
        dibujo.ellipse((1430, 560, 1900, 1030), fill=PANEL_CLARO)
        caja_texto = (165, 515, 1510, 930)
        centro_x = 835
    elif variante == 2:
        dibujo.polygon(
            ((0, 300), (760, 220), (1020, ALTO), (0, ALTO)),
            fill=(acento[0] // 2, acento[1] // 2, acento[2] // 2),
        )
        dibujo.ellipse((160, 390, 470, 700), outline=BLANCO, width=12)
        dibujo.ellipse((500, 565, 810, 875), outline=acento, width=12)
        caja_texto = (870, 300, 1810, 900)
        centro_x = 1340
    elif variante == 3:
        dibujo.rectangle((890, 235, 1030, ALTO), fill=acento)
        dibujo.rounded_rectangle(
            (105, 330, 790, 900), radius=50, fill=PANEL_CLARO
        )
        caja_texto = (1110, 315, 1810, 900)
        centro_x = 1460
    elif variante == 4:
        for x, y in ((190, 360), (460, 720), (760, 430), (1070, 760)):
            dibujo.line((x, y, x + 270, y + 130), fill=acento, width=18)
            dibujo.ellipse((x - 28, y - 28, x + 28, y + 28), fill=BLANCO)
        caja_texto = (1010, 260, 1830, 700)
        centro_x = 1420
    elif variante == 5:
        dibujo.ellipse((120, 285, 980, 1035), outline=acento, width=55)
        dibujo.ellipse((330, 470, 600, 740), fill=PANEL_CLARO)
        dibujo.ellipse((620, 610, 890, 880), fill=acento)
        caja_texto = (910, 300, 1810, 900)
        centro_x = 1360
    else:
        dibujo.polygon(
            ((285, 245), (1210, 245), (1480, 515), (1480, 955), (285, 955)),
            fill=(232, 225, 207),
        )
        dibujo.polygon(
            ((1210, 245), (1210, 515), (1480, 515)),
            fill=(174, 166, 148),
        )
        for y in (610, 690, 770, 850):
            dibujo.line((455, y, 1120, y), fill=(86, 91, 96), width=8)
        caja_texto = (1030, 325, 1835, 885)
        centro_x = 1430

    if variante != 6:
        dibujo.rounded_rectangle(
            caja_texto,
            radius=45,
            fill=PANEL,
            outline=acento,
            width=5,
        )
    else:
        dibujo.rounded_rectangle(
            caja_texto,
            radius=45,
            fill=PANEL,
            outline=acento,
            width=6,
        )

    ancho_texto = max(560, caja_texto[2] - caja_texto[0] - 120)
    fuente_texto = obtener_fuente(68, negrita=True)
    lineas = texto_ajustado(
        dibujo,
        principal,
        fuente_texto,
        ancho_texto,
        max_lineas=5,
    )
    altura_total = len(lineas) * 88
    inicio_y = max(
        caja_texto[1] + 55,
        (caja_texto[1] + caja_texto[3] - altura_total) // 2,
    )
    dibujar_lineas_centradas(
        dibujo,
        lineas,
        centro_x,
        inicio_y,
        fuente_texto,
        BLANCO,
        separacion=20,
    )

    fuente_marca = obtener_fuente(24, negrita=True)
    dibujo.rounded_rectangle(
        (ANCHO - 360, ALTO - 120, ANCHO - 90, ALTO - 68),
        radius=18,
        fill=acento,
    )
    dibujo.text(
        (ANCHO - 225, ALTO - 94),
        "NEXO IA · DOCUMENTAL",
        font=fuente_marca,
        fill=FONDO_1,
        anchor="mm",
    )
    return imagen


def crear_vista_previa(
    archivos: list[tuple[Path, str]],
    destino: Path,
) -> None:
    """Crea una hoja de contacto con recursos locales."""
    if not archivos:
        return

    columnas = 4
    ancho_miniatura = 320
    alto_miniatura = 180
    margen = 22
    alto_etiqueta = 48

    filas = math.ceil(
        len(archivos) / columnas
    )

    ancho_total = (
        columnas * ancho_miniatura
        + (columnas + 1) * margen
    )

    alto_total = (
        filas
        * (alto_miniatura + alto_etiqueta)
        + (filas + 1) * margen
    )

    lienzo = Image.new(
        "RGB",
        (ancho_total, alto_total),
        FONDO_1,
    )

    dibujo = ImageDraw.Draw(lienzo)
    fuente = obtener_fuente(18)

    for indice, (ruta, etiqueta) in enumerate(
        archivos
    ):
        fila = indice // columnas
        columna = indice % columnas

        x = (
            margen
            + columna
            * (ancho_miniatura + margen)
        )

        y = (
            margen
            + fila
            * (
                alto_miniatura
                + alto_etiqueta
                + margen
            )
        )

        with Image.open(ruta) as imagen:
            miniatura = imagen.convert(
                "RGB"
            ).resize(
                (
                    ancho_miniatura,
                    alto_miniatura,
                ),
                Image.Resampling.LANCZOS,
            )

        lienzo.paste(
            miniatura,
            (x, y),
        )

        etiqueta_corta = textwrap.shorten(
            etiqueta,
            width=38,
            placeholder="…",
        )

        dibujo.text(
            (
                x,
                y + alto_miniatura + 10,
            ),
            etiqueta_corta,
            font=fuente,
            fill=GRIS,
        )

    lienzo.save(
        destino,
        format="JPEG",
        quality=88,
        optimize=True,
    )


class GeneradorRecursosLocales:
    """Genera imágenes para los clips no cubiertos por Pixabay."""

    def generar(
        self,
        manifiesto: dict[str, Any],
        ruta_manifiesto: Path,
        forzar: bool = False,
    ) -> dict[str, Any]:
        """Genera recursos y actualiza el manifiesto."""
        elementos = manifiesto.get(
            "elementos",
            [],
        )

        carpeta_raiz = ruta_manifiesto.parent

        respaldo = carpeta_raiz / "assets_manifest.backup.json"

        if not respaldo.is_file():
            shutil.copy2(
                ruta_manifiesto,
                respaldo,
            )

        generados = 0
        omitidos = 0
        errores = 0
        vistas: list[tuple[Path, str]] = []

        for indice, elemento in enumerate(
            elementos,
            start=1,
        ):
            if not isinstance(elemento, dict):
                continue

            tipo = str(
                elemento.get(
                    "tipo_recurso",
                    "",
                )
            )

            if tipo not in TIPOS_LOCALES:
                continue

            estado = str(
                elemento.get(
                    "estado",
                    "",
                )
            )

            if (
                estado == "generado_local"
                and not forzar
            ):
                omitidos += 1
                continue

            if (
                estado != "pendiente_generacion"
                and not forzar
            ):
                continue

            segmento_indice = int(
                elemento.get(
                    "segmento_indice",
                    0,
                )
                or 0
            )

            clip_orden = int(
                elemento.get(
                    "clip_orden",
                    indice,
                )
                or indice
            )

            titulo_segmento = str(
                elemento.get(
                    "segmento_titulo",
                    f"Segmento {segmento_indice}",
                )
            )

            carpeta_segmento = (
                carpeta_raiz
                / (
                    f"{segmento_indice:02d}_"
                    f"{nombre_seguro(titulo_segmento)}"
                )
            )

            carpeta_segmento.mkdir(
                parents=True,
                exist_ok=True,
            )

            destino = (
                carpeta_segmento
                / (
                    f"clip_{clip_orden:02d}_"
                    f"local_{tipo}.png"
                )
            )

            print(
                f"Generando recurso local "
                f"{generados + 1}: "
                f"{titulo_segmento} | {tipo}"
            )

            try:
                if tipo == "captura_interfaz":
                    imagen = generar_captura_interfaz(
                        elemento
                    )

                elif tipo == "grafico":
                    imagen = generar_grafico(
                        elemento
                    )

                else:
                    imagen = generar_texto_animado(
                        elemento
                    )

                imagen.save(
                    destino,
                    format="PNG",
                    optimize=True,
                )

                elemento["estado"] = "generado_local"
                elemento["fuente"] = "generador_local"
                elemento["archivo"] = str(
                    destino.resolve()
                )

                elemento["generacion_local"] = {
                    "tipo": tipo,
                    "ancho": ANCHO,
                    "alto": ALTO,
                    "formato": "png",
                    "estilo_tarjeta": str(
                        elemento.get("estilo_tarjeta", "")
                    ),
                    "interfaz_ilustrativa": (
                        tipo == "captura_interfaz"
                    ),
                }

                elemento.pop(
                    "motivo",
                    None,
                )

                generados += 1

                vistas.append(
                    (
                        destino,
                        (
                            f"{segmento_indice:02d}."
                            f"{clip_orden:02d} "
                            f"{tipo}"
                        ),
                    )
                )

                print(
                    f"  OK: {destino.name}"
                )

            except Exception as error:
                errores += 1
                elemento["estado"] = "error_generacion_local"
                elemento["error"] = str(error)

                print(
                    f"  ERROR: {error}"
                )

        descargados = sum(
            1
            for elemento in elementos
            if isinstance(elemento, dict)
            and elemento.get("estado") == "descargado"
        )

        total_generados_locales = sum(
            1
            for elemento in elementos
            if isinstance(elemento, dict)
            and elemento.get("estado") == "generado_local"
        )

        pendientes = sum(
            1
            for elemento in elementos
            if isinstance(elemento, dict)
            and elemento.get("estado") == "pendiente_generacion"
        )

        errores_totales = sum(
            1
            for elemento in elementos
            if isinstance(elemento, dict)
            and str(
                elemento.get("estado", "")
            ).startswith("error")
        )

        manifiesto["actualizado_en"] = (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        )

        manifiesto["resumen"] = {
            "descargados": descargados,
            "generados_localmente": total_generados_locales,
            "pendientes_generacion": pendientes,
            "omitidos_por_limite": 0,
            "errores": errores_totales,
            "total_elementos": len(elementos),
        }

        temporal = ruta_manifiesto.with_suffix(
            ".json.tmp"
        )

        temporal.write_text(
            json.dumps(
                manifiesto,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporal.replace(
            ruta_manifiesto
        )

        vista_previa = (
            carpeta_raiz
            / "preview_local_assets.jpg"
        )

        archivos_vista = []

        for elemento in elementos:
            if not isinstance(elemento, dict):
                continue

            if elemento.get("estado") != "generado_local":
                continue

            ruta_archivo = Path(
                str(elemento.get("archivo", ""))
            )

            if not ruta_archivo.is_file():
                continue

            archivos_vista.append(
                (
                    ruta_archivo,
                    (
                        f"{elemento.get('segmento_indice', 0):02d}."
                        f"{elemento.get('clip_orden', 0):02d} "
                        f"{elemento.get('tipo_recurso', '')}"
                    ),
                )
            )

        crear_vista_previa(
            archivos=archivos_vista,
            destino=vista_previa,
        )

        return {
            "generados_esta_ejecucion": generados,
            "omitidos": omitidos,
            "errores_esta_ejecucion": errores,
            "descargados": descargados,
            "generados_localmente": total_generados_locales,
            "pendientes": pendientes,
            "errores_totales": errores_totales,
            "total": len(elementos),
            "vista_previa": vista_previa,
            "manifiesto": ruta_manifiesto,
        }
