from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


class GeneradorMiniaturaYouTube:
    """Crea automáticamente una miniatura 1280x720 para NEXON IA."""

    ANCHO = 1280
    ALTO = 720

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)

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
        limpio = " ".join(str(titulo).replace("|", " ").split())
        if len(limpio) <= 58:
            return limpio
        palabras = limpio.split()
        salida: list[str] = []
        total = 0
        for palabra in palabras:
            extra = len(palabra) + (1 if salida else 0)
            if total + extra > 58:
                break
            salida.append(palabra)
            total += extra
        return " ".join(salida).rstrip(":-–—") or limpio[:58].rstrip()

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

    def generar(self, forzar: bool = False) -> tuple[Path, bool]:
        metadata = self._metadata()
        video = self._video()

        output_dir = self.project_root / "output" / "thumbnails"
        output_dir.mkdir(parents=True, exist_ok=True)

        salida = output_dir / "miniatura_youtube_autotube.jpg"

        entradas = [
            self.project_root / "data" / "publish" / "metadata.json",
            video,
        ]

        if (
            salida.exists()
            and not forzar
            and salida.stat().st_size > 0
            and salida.stat().st_mtime >= max(p.stat().st_mtime for p in entradas)
        ):
            return salida, False

        frame = output_dir / "_thumb_frame_tmp.jpg"
        self._extraer_frame(video, frame)

        imagen = Image.open(frame).convert("RGB")
        imagen = imagen.resize((self.ANCHO, self.ALTO))
        imagen = ImageEnhance.Brightness(imagen).enhance(0.42)
        imagen = ImageEnhance.Contrast(imagen).enhance(1.15)
        imagen = imagen.filter(ImageFilter.GaussianBlur(radius=1.2))

        overlay = Image.new("RGBA", imagen.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        # Franja superior de marca.
        draw_overlay.rounded_rectangle(
            (42, 34, 250, 92),
            radius=16,
            fill=(8, 12, 28, 235),
            outline=(0, 230, 255, 230),
            width=3,
        )

        # Panel oscuro para legibilidad del título.
        draw_overlay.rounded_rectangle(
            (40, 122, 860, 615),
            radius=34,
            fill=(4, 8, 24, 210),
            outline=(124, 58, 237, 220),
            width=4,
        )

        # Acento inferior.
        draw_overlay.rounded_rectangle(
            (40, 630, 1238, 690),
            radius=18,
            fill=(14, 18, 38, 235),
        )

        imagen = Image.alpha_composite(imagen.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(imagen)

        fuente_marca = self._fuente(31, bold=True)
        fuente_titulo = self._fuente(67, bold=True)
        fuente_sello = self._fuente(29, bold=True)
        fuente_pie = self._fuente(27, bold=True)

        draw.text(
            (72, 47),
            "NEXON IA",
            font=fuente_marca,
            fill=(255, 255, 255),
        )

        titulo = self._texto_corto(metadata.get("title", "El futuro de la IA"))
        lineas = self._wrap(draw, titulo, fuente_titulo, 720)

        y = 170
        for linea in lineas:
            draw.text(
                (86, y),
                linea,
                font=fuente_titulo,
                fill=(255, 255, 255),
                stroke_width=3,
                stroke_fill=(0, 0, 0),
            )
            y += 88

        # Sello "DOCUMENTAL IA".
        draw.rounded_rectangle(
            (86, 500, 392, 566),
            radius=16,
            fill=(118, 55, 238),
        )
        draw.text(
            (116, 516),
            "DOCUMENTAL IA",
            font=fuente_sello,
            fill=(255, 255, 255),
        )

        # Sello "AVANCES IA".
        draw.rounded_rectangle(
            (418, 500, 690, 566),
            radius=16,
            fill=(0, 174, 214),
        )
        draw.text(
            (456, 516),
            "AVANCES IA",
            font=fuente_sello,
            fill=(255, 255, 255),
        )

        draw.text(
            (70, 646),
            "CIENCIA ? TECNOLOG?A ? FUTURO",
            font=fuente_pie,
            fill=(242, 244, 255),
        )

        imagen = imagen.convert("RGB")
        imagen.save(
            salida,
            "JPEG",
            quality=91,
            optimize=True,
            progressive=True,
        )

        if frame.exists():
            frame.unlink(missing_ok=True)

        if salida.stat().st_size > 2 * 1024 * 1024:
            imagen.save(
                salida,
                "JPEG",
                quality=82,
                optimize=True,
            )

        if salida.stat().st_size > 2 * 1024 * 1024:
            raise RuntimeError(
                "La miniatura automática supera 2 MB."
            )

        return salida, True
