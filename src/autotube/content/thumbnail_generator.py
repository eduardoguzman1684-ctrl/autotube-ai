from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from autotube.content.channel_profiles import (
    DEFAULT_CHANNEL,
    channel_profile,
    normalize_channel_slug,
)


class GeneradorMiniaturaYouTube:
    """Crea una miniatura 1280x720 con la marca del canal elegido."""

    ANCHO = 1280
    ALTO = 720

    def __init__(
        self,
        project_root: Path,
        channel_slug: str = DEFAULT_CHANNEL,
    ) -> None:
        self.project_root = Path(project_root)
        self.channel_slug = normalize_channel_slug(channel_slug)
        self.profile = channel_profile(self.channel_slug)

    def _latest(self, pattern: str) -> Path:
        archivos = [
            p for p in self.project_root.glob(pattern)
            if p.is_file()
        ]
        if not archivos:
            raise FileNotFoundError(
                f"No se encontró ningún archivo para: {pattern}"
            )
        return max(archivos, key=lambda p: p.stat().st_mtime)

    def _metadata(self) -> dict:
        ruta = self.project_root / "data" / "publish" / "metadata.json"
        if not ruta.exists():
            raise FileNotFoundError(
                "No existe data/publish/metadata.json. "
                "Genera primero los metadatos."
            )
        data = json.loads(ruta.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("metadata.json no contiene un objeto JSON.")
        return data

    def _video(self) -> Path:
        patrones = (
            "output/videos/render_*/video_final_subtitulado_musica.mp4",
            "output/videos/render_*/video_final.mp4",
        )
        candidatos: list[Path] = []
        for pattern in patrones:
            candidatos.extend(
                p for p in self.project_root.glob(pattern)
                if p.is_file()
            )
        if not candidatos:
            raise FileNotFoundError("No se encontró un video para la miniatura.")
        return max(candidatos, key=lambda p: p.stat().st_mtime)

    @staticmethod
    def _duracion(video: Path) -> float:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return 60.0
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            return max(1.0, float(proc.stdout.strip()))
        except (TypeError, ValueError):
            return 60.0

    def _extraer_frame(self, video: Path, salida: Path) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise FileNotFoundError("FFmpeg no está disponible en PATH.")

        duracion = self._duracion(video)
        instante = min(max(15.0, duracion * 0.22), max(1.0, duracion - 2.0))

        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{instante:.2f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                f"scale={self.ANCHO}:{self.ALTO}:force_original_aspect_ratio=increase,"
                f"crop={self.ANCHO}:{self.ALTO}",
                str(salida),
            ],
            cwd=self.project_root,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if not salida.exists():
            raise RuntimeError("No se pudo extraer un frame del video.")

    @staticmethod
    def _fuente(tamano: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidatos = []
        if bold:
            candidatos.extend([
                Path(r"C:\Windows\Fonts\arialbd.ttf"),
                Path(r"C:\Windows\Fonts\segoeuib.ttf"),
            ])
        else:
            candidatos.extend([
                Path(r"C:\Windows\Fonts\arial.ttf"),
                Path(r"C:\Windows\Fonts\segoeui.ttf"),
            ])

        for ruta in candidatos:
            if ruta.exists():
                try:
                    return ImageFont.truetype(str(ruta), tamano)
                except OSError:
                    pass
        return ImageFont.load_default()

    @staticmethod
    def _texto_corto(titulo: str) -> str:
        """Crea un gancho breve para la miniatura."""
        limpio = " ".join(
            str(titulo)
            .replace("|", " ")
            .split()
        )

        normalizado = "".join(
            caracter
            for caracter in unicodedata.normalize(
                "NFD",
                limpio.lower(),
            )
            if not unicodedata.combining(
                caracter
            )
        )

        reglas = [
            (
                ("agente", "autonom", "rebelion"),
                "IA SIN CONTROL",
            ),
            (
                ("web", "internet", "navegador", "buscador"),
                "ADIÓS A LA WEB",
            ),
            (
                ("robot", "humanoid"),
                "ROBOTS ENTRE NOSOTROS",
            ),
            (
                ("medicina", "salud", "enfermedad", "biologia"),
                "IA QUE SALVA VIDAS",
            ),
            (
                ("deepfake", "verdad", "falsificacion"),
                "¿QUÉ ES REAL?",
            ),
            (
                ("trabajo", "empleo", "laboral"),
                "¿TU EMPLEO EN RIESGO?",
            ),
            (
                ("energia", "electrica", "consumo"),
                "EL PRECIO DE LA IA",
            ),
            (
                ("mente", "cerebro", "neuro"),
                "¿LEERÁ TU MENTE?",
            ),
            (
                ("soledad", "pareja", "afecto", "relaciones"),
                "AMOR ARTIFICIAL",
            ),
            (
                ("militar", "guerra", "armas"),
                "GUERRA SIN HUMANOS",
            ),
        ]

        for palabras_clave, gancho in reglas:
            if any(
                palabra in normalizado
                for palabra in palabras_clave
            ):
                return gancho

        base = limpio.split(":", 1)[0]

        palabras = [
            palabra.strip("¿?¡!.,;:-")
            for palabra in base.split()
            if palabra.strip("¿?¡!.,;:-")
        ]

        articulos = {
            "el",
            "la",
            "los",
            "las",
            "un",
            "una",
        }

        while (
            palabras
            and palabras[0].lower()
            in articulos
        ):
            palabras.pop(0)

        return (
            " ".join(palabras[:4]).upper()
            or "EL FUTURO DE LA IA"
        )

    @staticmethod
    def _wrap(draw: ImageDraw.ImageDraw, texto: str, fuente, ancho_max: int) -> list[str]:
        palabras = texto.split()
        lineas: list[str] = []
        actual: list[str] = []

        for palabra in palabras:
            prueba = " ".join(actual + [palabra])
            bbox = draw.textbbox((0, 0), prueba, font=fuente, stroke_width=2)
            if bbox[2] - bbox[0] <= ancho_max:
                actual.append(palabra)
            else:
                if actual:
                    lineas.append(" ".join(actual))
                actual = [palabra]

        if actual:
            lineas.append(" ".join(actual))

        return lineas[:3]

    def generar(
        self,
        forzar: bool = False,
        titulo_override: str | None = None,
        gancho_override: str | None = None,
        nombre_salida: str | None = None,
    ) -> tuple[Path, bool]:
        """Genera la miniatura principal o una variante experimental."""
        metadata = self._metadata()
        metadata_channel = normalize_channel_slug(
            str(
                metadata.get(
                    "channel_slug",
                    DEFAULT_CHANNEL,
                )
            )
        )

        if metadata_channel != self.channel_slug:
            raise RuntimeError(
                "BLOQUEO EDITORIAL: la metadata pertenece a "
                f"{metadata_channel}, no a {self.channel_slug}."
            )

        video = self._video()
        colores = self.profile["colors"]
        primario = tuple(colores["primary"])
        acento = tuple(colores["accent"])
        panel = tuple(colores["panel"])

        output_dir = (
            self.project_root
            / "output"
            / "thumbnails"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        nombre_archivo = (
            nombre_salida
            or "miniatura_youtube_autotube.jpg"
        )
        nombre_archivo = Path(nombre_archivo).name

        if not nombre_archivo.lower().endswith(".jpg"):
            nombre_archivo += ".jpg"

        salida = output_dir / nombre_archivo

        entradas = [
            (
                self.project_root
                / "data"
                / "publish"
                / "metadata.json"
            ),
            video,
        ]

        if (
            salida.exists()
            and not forzar
            and salida.stat().st_size > 0
            and salida.stat().st_mtime
            >= max(
                entrada.stat().st_mtime
                for entrada in entradas
            )
        ):
            return salida, False

        frame = (
            output_dir
            / "_thumb_frame_tmp.jpg"
        )

        self._extraer_frame(
            video,
            frame,
        )

        imagen = Image.open(
            frame
        ).convert("RGB")

        imagen = imagen.resize(
            (
                self.ANCHO,
                self.ALTO,
            )
        )

        imagen = ImageEnhance.Brightness(
            imagen
        ).enhance(0.82)

        imagen = ImageEnhance.Contrast(
            imagen
        ).enhance(1.30)

        imagen = ImageEnhance.Color(
            imagen
        ).enhance(1.25)

        imagen = ImageEnhance.Sharpness(
            imagen
        ).enhance(1.15)

        overlay = Image.new(
            "RGBA",
            imagen.size,
            (
                0,
                0,
                0,
                0,
            ),
        )

        draw_overlay = ImageDraw.Draw(
            overlay
        )

        # Gradiente oscuro solo en la zona del gancho.
        for x in range(
            0,
            900,
            3,
        ):
            proporcion = (
                1
                - x / 900
            )

            alpha = int(
                238
                * proporcion
                * proporcion
            )

            draw_overlay.rectangle(
                (
                    x,
                    0,
                    x + 3,
                    self.ALTO,
                ),
                fill=(
                    2,
                    5,
                    16,
                    alpha,
                ),
            )

        # Franja inferior para el titulo completo.
        draw_overlay.rectangle(
            (
                0,
                470,
                self.ANCHO,
                self.ALTO,
            ),
            fill=(
                2,
                5,
                15,
                255,
            ),
        )

        # Identidad visual del canal seleccionado.
        draw_overlay.rounded_rectangle(
            (
                42,
                32,
                252,
                94,
            ),
            radius=16,
            fill=(*panel, 235),
            outline=(*primario, 245),
            width=3,
        )

        # Linea de tension visual.
        draw_overlay.rounded_rectangle(
            (
                47,
                155,
                59,
                474,
            ),
            radius=6,
            fill=(*acento, 245),
        )

        imagen = Image.alpha_composite(
            imagen.convert("RGBA"),
            overlay,
        )

        draw = ImageDraw.Draw(
            imagen
        )

        fuente_marca = self._fuente(
            31,
            bold=True,
        )

        draw.text(
            (
                72,
                47,
            ),
            self.profile["brand_label"],
            font=fuente_marca,
            fill=(
                255,
                255,
                255,
            ),
        )

        titulo_fuente = (
            titulo_override
            if titulo_override is not None
            else metadata.get(
                "title",
                self.profile["default_niche"],
            )
        )

        titulo_completo = " ".join(
            str(titulo_fuente).split()
        )

        gancho = (
            " ".join(
                str(gancho_override).split()
            ).upper()
            if gancho_override
            else self._texto_corto(
                titulo_completo
            )
        )

        tamano_gancho = 112
        fuente_gancho = self._fuente(
            tamano_gancho,
            bold=True,
        )

        lineas_gancho = self._wrap(
            draw,
            gancho,
            fuente_gancho,
            590,
        )

        while (
            len(lineas_gancho) > 2
            and tamano_gancho > 72
        ):
            tamano_gancho -= 6

            fuente_gancho = self._fuente(
                tamano_gancho,
                bold=True,
            )

            lineas_gancho = self._wrap(
                draw,
                gancho,
                fuente_gancho,
                590,
            )

        lineas_gancho = (
            lineas_gancho[:2]
        )

        y = 174

        for indice, linea in enumerate(
            lineas_gancho
        ):
            es_ultima = (
                indice
                == len(lineas_gancho) - 1
            )

            draw.text(
                (
                    82,
                    y,
                ),
                linea,
                font=fuente_gancho,
                fill=(
                    (
                        *acento,
                    )
                    if es_ultima
                    else (
                        255,
                        255,
                        255,
                    )
                ),
                stroke_width=4,
                stroke_fill=(
                    0,
                    0,
                    0,
                ),
            )

            y += (
                tamano_gancho
                + 18
            )

        fuente_sello = self._fuente(
            25,
            bold=True,
        )

        draw.rounded_rectangle(
            (
                82,
                498,
                320,
                554,
            ),
            radius=15,
            fill=primario,
        )

        draw.text(
            (
                108,
                512,
            ),
            "DOCUMENTAL",
            font=fuente_sello,
            fill=(
                255,
                255,
                255,
            ),
        )

        tamano_pie = 38
        fuente_pie = self._fuente(
            tamano_pie,
            bold=True,
        )

        lineas_pie = self._wrap(
            draw,
            titulo_completo,
            fuente_pie,
            940,
        )

        while (
            len(lineas_pie) > 2
            and tamano_pie > 28
        ):
            tamano_pie -= 2

            fuente_pie = self._fuente(
                tamano_pie,
                bold=True,
            )

            lineas_pie = self._wrap(
                draw,
                titulo_completo,
                fuente_pie,
                940,
            )

        lineas_pie = lineas_pie[:2]
        y_pie = 586

        for linea in lineas_pie:
            caja = draw.textbbox(
                (
                    0,
                    0,
                ),
                linea,
                font=fuente_pie,
                stroke_width=2,
            )

            ancho_linea = (
                caja[2]
                - caja[0]
            )

            x_pie = max(
                55,
                (
                    self.ANCHO
                    - ancho_linea
                )
                // 2,
            )

            draw.text(
                (
                    x_pie,
                    y_pie,
                ),
                linea,
                font=fuente_pie,
                fill=(
                    247,
                    248,
                    255,
                ),
                stroke_width=2,
                stroke_fill=(
                    0,
                    0,
                    0,
                ),
            )

            y_pie += (
                tamano_pie
                + 8
            )

        imagen = imagen.convert(
            "RGB"
        )

        imagen.save(
            salida,
            "JPEG",
            quality=91,
            optimize=True,
            progressive=True,
        )

        if frame.exists():
            frame.unlink(
                missing_ok=True
            )

        if (
            salida.stat().st_size
            > 2 * 1024 * 1024
        ):
            imagen.save(
                salida,
                "JPEG",
                quality=82,
                optimize=True,
            )

        if (
            salida.stat().st_size
            > 2 * 1024 * 1024
        ):
            raise RuntimeError(
                "La miniatura automatica supera 2 MB."
            )

        return salida, True
