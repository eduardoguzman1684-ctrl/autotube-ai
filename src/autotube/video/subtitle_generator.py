from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def localizar_manifiesto_audio_subtitulos(
    output_dir: Path,
    archivo: Path | None = None,
) -> Path:
    """Localiza el manifiesto de audio más reciente."""
    if archivo is not None:
        ruta = archivo.expanduser().resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe el manifiesto indicado: {ruta}"
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


def cargar_audio_para_subtitulos(
    output_dir: Path,
    archivo: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Carga y valida el manifiesto de narración."""
    ruta = localizar_manifiesto_audio_subtitulos(
        output_dir=output_dir,
        archivo=archivo,
    )

    contenido = json.loads(
        ruta.read_text(encoding="utf-8")
    )

    segmentos = contenido.get("segmentos")

    if not isinstance(segmentos, list) or not segmentos:
        raise RuntimeError(
            "El manifiesto no contiene segmentos de narración."
        )

    return contenido, ruta


def contar_palabras_texto(texto: str) -> int:
    """Cuenta palabras visibles de un texto."""
    return len(
        re.findall(
            r"\S+",
            texto.strip(),
        )
    )


def limpiar_texto_subtitulo(texto: str) -> str:
    """Limpia espacios sin modificar la narración."""
    texto = str(texto)

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


def dividir_texto_subtitulos(
    texto: str,
    max_palabras: int = 12,
    max_caracteres: int = 74,
) -> list[str]:
    """Divide una narración en subtítulos breves y legibles."""
    texto = limpiar_texto_subtitulo(
        texto
    )

    if not texto:
        return []

    palabras = texto.split()

    bloques: list[str] = []
    actual: list[str] = []

    for palabra in palabras:
        candidato = " ".join(
            [*actual, palabra]
        )

        supera_palabras = (
            len(actual) >= max_palabras
        )

        supera_caracteres = (
            len(candidato) > max_caracteres
        )

        if actual and (
            supera_palabras
            or supera_caracteres
        ):
            bloques.append(
                " ".join(actual)
            )

            actual = [palabra]
        else:
            actual.append(palabra)

        if (
            actual
            and actual[-1].endswith(
                (".", "?", "!", ":", ";")
            )
            and len(actual) >= 5
        ):
            bloques.append(
                " ".join(actual)
            )

            actual = []

    if actual:
        bloques.append(
            " ".join(actual)
        )

    if (
        len(bloques) >= 2
        and contar_palabras_texto(
            bloques[-1]
        ) <= 3
    ):
        combinado = (
            bloques[-2]
            + " "
            + bloques[-1]
        )

        if len(combinado) <= (
            max_caracteres + 20
        ):
            bloques[-2] = combinado
            bloques.pop()

    return bloques


def formatear_tiempo_srt(
    segundos: float,
) -> str:
    """Convierte segundos al formato HH:MM:SS,mmm."""
    milisegundos_totales = max(
        0,
        round(segundos * 1000),
    )

    horas = (
        milisegundos_totales
        // 3_600_000
    )

    restante = (
        milisegundos_totales
        % 3_600_000
    )

    minutos = restante // 60_000
    restante %= 60_000

    segundos_enteros = restante // 1000
    milisegundos = restante % 1000

    return (
        f"{horas:02d}:"
        f"{minutos:02d}:"
        f"{segundos_enteros:02d},"
        f"{milisegundos:03d}"
    )


class GeneradorSubtitulos:
    """Genera SRT sincronizado desde el manifiesto de voz."""

    def crear_eventos(
        self,
        manifiesto_audio: dict[str, Any],
        max_palabras: int = 12,
        max_caracteres: int = 74,
    ) -> list[dict[str, Any]]:
        """Calcula los tiempos de cada bloque de subtítulos."""
        segmentos = manifiesto_audio.get(
            "segmentos",
            [],
        )

        eventos: list[dict[str, Any]] = []
        tiempo_acumulado = 0.0

        for segmento in segmentos:
            if not isinstance(segmento, dict):
                continue

            texto = limpiar_texto_subtitulo(
                str(
                    segmento.get("texto_voz")
                    or segmento.get("texto")
                    or ""
                )
            )

            try:
                duracion = float(
                    segmento.get(
                        "duracion_real_segundos",
                        0,
                    )
                )
            except (TypeError, ValueError):
                duracion = 0.0

            inicio_segmento = tiempo_acumulado
            final_segmento = (
                inicio_segmento + duracion
            )

            tiempo_acumulado = final_segmento

            if not texto or duracion <= 0:
                continue

            bloques = dividir_texto_subtitulos(
                texto=texto,
                max_palabras=max_palabras,
                max_caracteres=max_caracteres,
            )

            if not bloques:
                continue

            pesos = [
                max(
                    1,
                    contar_palabras_texto(
                        bloque
                    ),
                )
                for bloque in bloques
            ]

            suma_pesos = sum(pesos)
            inicio_actual = inicio_segmento

            for posicion, (
                bloque,
                peso,
            ) in enumerate(
                zip(bloques, pesos),
                start=1,
            ):
                if posicion == len(bloques):
                    final_actual = final_segmento
                else:
                    proporcion = (
                        peso / suma_pesos
                    )

                    duracion_bloque = (
                        duracion * proporcion
                    )

                    final_actual = (
                        inicio_actual
                        + duracion_bloque
                    )

                    suma_pesos -= peso
                    duracion = (
                        final_segmento
                        - final_actual
                    )

                eventos.append(
                    {
                        "inicio_segundos": round(
                            inicio_actual,
                            3,
                        ),
                        "final_segundos": round(
                            final_actual,
                            3,
                        ),
                        "texto": bloque,
                        "segmento": segmento.get(
                            "titulo",
                            "",
                        ),
                    }
                )

                inicio_actual = final_actual

        return eventos

    def crear_srt(
        self,
        eventos: list[dict[str, Any]],
    ) -> str:
        """Convierte los eventos a formato SRT."""
        bloques: list[str] = []

        for indice, evento in enumerate(
            eventos,
            start=1,
        ):
            inicio = formatear_tiempo_srt(
                float(
                    evento["inicio_segundos"]
                )
            )

            final = formatear_tiempo_srt(
                float(
                    evento["final_segundos"]
                )
            )

            texto = str(
                evento["texto"]
            ).strip()

            bloques.append(
                "\n".join(
                    [
                        str(indice),
                        f"{inicio} --> {final}",
                        texto,
                    ]
                )
            )

        return "\n\n".join(bloques) + "\n"

    def crear_transcripcion(
        self,
        manifiesto_audio: dict[str, Any],
    ) -> str:
        """Crea una transcripción organizada por segmentos."""
        lineas: list[str] = []

        titulo = str(
            manifiesto_audio.get(
                "titulo",
                "Sin título",
            )
        )

        lineas.append(titulo)
        lineas.append("=" * len(titulo))
        lineas.append("")

        for segmento in manifiesto_audio.get(
            "segmentos",
            [],
        ):
            if not isinstance(segmento, dict):
                continue

            nombre = str(
                segmento.get(
                    "titulo",
                    "Segmento",
                )
            )

            texto = limpiar_texto_subtitulo(
                str(
                    segmento.get("texto_voz")
                    or segmento.get("texto")
                    or ""
                )
            )

            lineas.append(nombre)
            lineas.append("-" * len(nombre))
            lineas.append(texto)
            lineas.append("")

        return "\n".join(lineas).strip() + "\n"

    def generar(
        self,
        manifiesto_audio: dict[str, Any],
        ruta_audio_manifest: Path,
        output_dir: Path,
        max_palabras: int = 12,
        max_caracteres: int = 74,
    ) -> dict[str, Any]:
        """Genera SRT, transcripción y manifiesto."""
        if max_palabras < 4 or max_palabras > 25:
            raise ValueError(
                "El máximo de palabras debe estar entre 4 y 25."
            )

        if max_caracteres < 30 or max_caracteres > 120:
            raise ValueError(
                "El máximo de caracteres debe estar entre 30 y 120."
            )

        eventos = self.crear_eventos(
            manifiesto_audio=manifiesto_audio,
            max_palabras=max_palabras,
            max_caracteres=max_caracteres,
        )

        if not eventos:
            raise RuntimeError(
                "No fue posible crear eventos de subtítulos."
            )

        marca_tiempo = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        carpeta = (
            output_dir
            / "subtitles"
            / f"subtitulos_{marca_tiempo}"
        )

        carpeta.mkdir(
            parents=True,
            exist_ok=True,
        )

        ruta_srt = (
            carpeta
            / "subtitulos.srt"
        )

        ruta_transcripcion = (
            carpeta
            / "transcripcion.txt"
        )

        ruta_srt.write_text(
            self.crear_srt(eventos),
            encoding="utf-8",
        )

        ruta_transcripcion.write_text(
            self.crear_transcripcion(
                manifiesto_audio
            ),
            encoding="utf-8",
        )

        duracion_final = max(
            float(
                evento["final_segundos"]
            )
            for evento in eventos
        )

        manifiesto = {
            "generado_en": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "titulo": manifiesto_audio.get(
                "titulo",
                "Sin título",
            ),
            "audio_manifest_origen": str(
                ruta_audio_manifest.resolve()
            ),
            "cantidad_subtitulos": len(eventos),
            "duracion_segundos": round(
                duracion_final,
                3,
            ),
            "max_palabras": max_palabras,
            "max_caracteres": max_caracteres,
            "archivo_srt": str(
                ruta_srt.resolve()
            ),
            "transcripcion": str(
                ruta_transcripcion.resolve()
            ),
        }

        ruta_manifiesto = (
            carpeta
            / "subtitles_manifest.json"
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
            "srt": ruta_srt,
            "transcripcion": ruta_transcripcion,
            "manifiesto": ruta_manifiesto,
            "cantidad": len(eventos),
            "duracion": duracion_final,
        }