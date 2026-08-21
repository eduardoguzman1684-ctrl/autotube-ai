from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PATRON_PALABRAS = re.compile(
    r"\b[\wÁÉÍÓÚÜÑáéíóúüñ'-]+\b",
    flags=re.UNICODE,
)


def contar_palabras(texto: str) -> int:
    """Cuenta aproximadamente las palabras de una narración."""
    return len(PATRON_PALABRAS.findall(texto or ""))


def localizar_guion(
    data_dir: Path,
    archivo: Path | None = None,
) -> Path:
    """Localiza un guion específico o el más reciente."""
    if archivo is not None:
        ruta = archivo.expanduser()

        if not ruta.is_absolute():
            ruta = Path.cwd() / ruta

        ruta = ruta.resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No se encontró el guion: {ruta}"
            )

        return ruta

    scripts_dir = data_dir / "scripts"

    archivos = sorted(
        scripts_dir.glob("guion_*.json"),
        key=lambda elemento: elemento.stat().st_mtime,
        reverse=True,
    )

    if not archivos:
        raise FileNotFoundError(
            "No existen guiones. Ejecuta primero 'autotube script'."
        )

    return archivos[0]


def validar_archivo_guion(
    data_dir: Path,
    archivo: Path | None = None,
    palabras_por_minuto: int = 145,
) -> tuple[dict[str, Any], Path]:
    """Analiza la duración, estructura y narración de un guion."""
    if palabras_por_minuto < 100 or palabras_por_minuto > 220:
        raise ValueError(
            "Las palabras por minuto deben estar entre 100 y 220."
        )

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
            "El archivo no contiene un objeto 'guion' válido."
        )

    escenas = guion.get("escenas")

    if not isinstance(escenas, list) or not escenas:
        raise RuntimeError(
            "El guion no contiene escenas válidas."
        )

    errores: list[str] = []
    advertencias: list[str] = []
    detalle_escenas: list[dict[str, Any]] = []

    partes_narracion = [
        str(guion.get("introduccion", "")),
    ]

    duracion_declarada_segundos = 0

    for posicion, escena in enumerate(escenas, start=1):
        if not isinstance(escena, dict):
            errores.append(
                f"La escena {posicion} no tiene un formato válido."
            )
            continue

        numero = escena.get("numero", posicion)
        titulo = str(
            escena.get("titulo", f"Escena {posicion}")
        )
        narracion = str(escena.get("narracion", "")).strip()

        try:
            duracion_declarada = int(
                escena.get("duracion_segundos", 0)
            )
        except (TypeError, ValueError):
            duracion_declarada = 0

        palabras = contar_palabras(narracion)

        duracion_narracion = round(
            palabras / palabras_por_minuto * 60,
            1,
        )

        duracion_declarada_segundos += max(
            duracion_declarada,
            0,
        )

        partes_narracion.append(narracion)

        if numero != posicion:
            advertencias.append(
                f"La escena en posición {posicion} utiliza "
                f"el número {numero}."
            )

        if not narracion:
            errores.append(
                f"La escena {numero} no tiene narración."
            )

        if duracion_declarada <= 0:
            errores.append(
                f"La escena {numero} no tiene una duración válida."
            )

        if (
            duracion_declarada > 0
            and duracion_narracion
            < duracion_declarada * 0.85
        ):
            advertencias.append(
                f"La escena {numero} declara "
                f"{duracion_declarada} segundos, pero su narración "
                f"dura aproximadamente {duracion_narracion} segundos."
            )

        if (
            duracion_declarada > 0
            and duracion_narracion
            > duracion_declarada * 1.15
        ):
            advertencias.append(
                f"La narración de la escena {numero} excede "
                f"considerablemente su duración declarada."
            )

        detalle_escenas.append(
            {
                "numero": numero,
                "titulo": titulo,
                "palabras": palabras,
                "duracion_declarada_segundos": duracion_declarada,
                "duracion_narracion_segundos": duracion_narracion,
            }
        )

    partes_narracion.append(
        str(guion.get("llamada_accion", ""))
    )

    narracion_completa = "\n".join(
        parte
        for parte in partes_narracion
        if parte.strip()
    )

    palabras_totales = contar_palabras(
        narracion_completa
    )

    duracion_real_segundos = round(
        palabras_totales
        / palabras_por_minuto
        * 60,
        1,
    )

    try:
        minutos_objetivo = int(
            guion.get(
                "duracion_estimada_minutos",
                0,
            )
        )
    except (TypeError, ValueError):
        minutos_objetivo = 0

    duracion_objetivo_segundos = (
        minutos_objetivo * 60
    )

    if duracion_objetivo_segundos <= 0:
        errores.append(
            "El guion no tiene una duración objetivo válida."
        )
    else:
        porcentaje_real = (
            duracion_real_segundos
            / duracion_objetivo_segundos
        )

        if porcentaje_real < 0.95:
            errores.append(
                "La narración es demasiado corta para la duración "
                "objetivo del video."
            )

        if porcentaje_real > 1.05:
            errores.append(
                "La narración es demasiado larga para la duración "
                "objetivo del video."
            )

    diferencia_declarada = abs(
        duracion_declarada_segundos
        - duracion_objetivo_segundos
    )

    if (
        duracion_objetivo_segundos > 0
        and diferencia_declarada
        > duracion_objetivo_segundos * 0.15
    ):
        advertencias.append(
            "La suma de las escenas no coincide con la duración "
            "objetivo del video."
        )

    aprobado = not errores

    reporte = {
        "aprobado": aprobado,
        "titulo": guion.get("titulo", "Sin título"),
        "palabras_por_minuto": palabras_por_minuto,
        "palabras_totales": palabras_totales,
        "duracion_objetivo_segundos": duracion_objetivo_segundos,
        "duracion_declarada_segundos": duracion_declarada_segundos,
        "duracion_narracion_segundos": duracion_real_segundos,
        "escenas": detalle_escenas,
        "errores": errores,
        "advertencias": advertencias,
    }

    return reporte, ruta


def imprimir_reporte(
    reporte: dict[str, Any],
    ruta: Path,
) -> None:
    """Muestra el resultado del control de calidad."""
    print("\nCONTROL DE CALIDAD DEL GUION")
    print("=" * 72)
    print(f"Archivo: {ruta}")
    print(f"Título: {reporte['titulo']}")
    print(f"Escenas: {len(reporte['escenas'])}")
    print(f"Palabras totales: {reporte['palabras_totales']}")
    print(
        "Duración objetivo: "
        f"{reporte['duracion_objetivo_segundos']} segundos"
    )
    print(
        "Duración declarada en escenas: "
        f"{reporte['duracion_declarada_segundos']} segundos"
    )
    print(
        "Duración aproximada de la narración: "
        f"{reporte['duracion_narracion_segundos']} segundos"
    )
    print(
        "Velocidad utilizada: "
        f"{reporte['palabras_por_minuto']} palabras por minuto"
    )

    print("\nDETALLE DE ESCENAS")
    print("-" * 72)

    for escena in reporte["escenas"]:
        print(
            f"{escena['numero']}. {escena['titulo']} | "
            f"{escena['palabras']} palabras | "
            f"declarada: "
            f"{escena['duracion_declarada_segundos']} s | "
            f"narración: "
            f"{escena['duracion_narracion_segundos']} s"
        )

    if reporte["errores"]:
        print("\nERRORES")
        print("-" * 72)

        for error in reporte["errores"]:
            print(f"[ERROR] {error}")

    if reporte["advertencias"]:
        print("\nADVERTENCIAS")
        print("-" * 72)

        for advertencia in reporte["advertencias"]:
            print(f"[AVISO] {advertencia}")

    print("\n" + "=" * 72)

    if reporte["aprobado"]:
        print("RESULTADO: GUION APROBADO")
    else:
        print("RESULTADO: GUION REQUIERE CORRECCIONES")

    print("=" * 72)