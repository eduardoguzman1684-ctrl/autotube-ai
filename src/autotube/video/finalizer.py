from __future__ import annotations

import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path


class FinalizadorVideo:
    """Quema subtítulos, añade música y crea el MP4 final para YouTube."""

    def __init__(
        self,
        project_root: Path,
        volumen_musica: float = 0.07,
    ) -> None:
        self.project_root = Path(project_root)
        self.volumen_musica = max(0.0, min(float(volumen_musica), 0.30))

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

    def _buscar_video(self) -> Path:
        return self._latest(
            "output/videos/render_*/video_final.mp4"
        )

    def _buscar_srt(self) -> Path:
        return self._latest(
            "output/subtitles/subtitulos_*/subtitulos.srt"
        )

    def _buscar_musica(self) -> Path:
        candidatos = [
            self.project_root / "assets" / "music" / "nexon_ambient.wav",
            self.project_root / "assets" / "music" / "nexon_ambient.mp3",
            self.project_root / "output" / "music_tests" / "musica_ambiental_melodica_45s.wav",
        ]
        for ruta in candidatos:
            if ruta.exists() and ruta.stat().st_size > 0:
                return ruta

        salida = (
            self.project_root
            / "assets"
            / "music"
            / "nexon_ambient.wav"
        )
        self._generar_musica_base(salida)
        return salida

    @staticmethod
    def _generar_musica_base(
        salida: Path,
        duracion: int = 45,
        sample_rate: int = 44100,
    ) -> None:
        """Genera un fondo ambiental suave y original como fallback."""
        salida.parent.mkdir(parents=True, exist_ok=True)

        acordes = [
            (110.00, 164.81, 220.00),
            (98.00, 146.83, 196.00),
            (130.81, 196.00, 261.63),
            (87.31, 130.81, 174.61),
        ]

        total = duracion * sample_rate
        amplitud = 0.10

        with wave.open(str(salida), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)

            frames = bytearray()

            for i in range(total):
                t = i / sample_rate
                bloque = int(t // 6) % len(acordes)
                frecs = acordes[bloque]

                fade_in = min(1.0, t / 2.5)
                fade_out = min(1.0, (duracion - t) / 2.5)
                env = max(0.0, min(fade_in, fade_out))

                modulacion = 0.82 + 0.18 * math.sin(2 * math.pi * 0.08 * t)

                valor = 0.0
                for idx, f in enumerate(frecs):
                    valor += math.sin(
                        2 * math.pi * f * t + idx * 0.7
                    )

                valor /= len(frecs)
                valor += 0.25 * math.sin(
                    2 * math.pi * (frecs[0] / 2.0) * t
                )

                muestra = int(
                    32767
                    * amplitud
                    * env
                    * modulacion
                    * max(-1.0, min(1.0, valor))
                )

                frames.extend(struct.pack("<hh", muestra, muestra))

            wav.writeframes(frames)

    @staticmethod
    def _ruta_subtitulos_ffmpeg(ruta: Path) -> str:
        texto = str(ruta.resolve()).replace("\\", "/")
        texto = texto.replace(":", r"\:")
        texto = texto.replace("'", r"\'")
        return texto

    def finalizar(
        self,
        forzar: bool = False,
    ) -> tuple[Path, bool]:
        ffmpeg = shutil.which("ffmpeg")

        if not ffmpeg:
            raise FileNotFoundError(
                "FFmpeg no está disponible en PATH."
            )

        video = self._buscar_video()
        srt = self._buscar_srt()
        musica = self._buscar_musica()

        salida = (
            video.parent
            / "video_final_subtitulado_musica.mp4"
        )

        entradas = [video, srt, musica]

        if (
            salida.exists()
            and not forzar
            and salida.stat().st_size > 0
            and salida.stat().st_mtime
            >= max(p.stat().st_mtime for p in entradas)
        ):
            return salida, False

        srt_ffmpeg = self._ruta_subtitulos_ffmpeg(srt)

        filtro_subtitulos = (
            f"subtitles='{srt_ffmpeg}':"
            "force_style='"
            "FontName=Arial,"
            "FontSize=22,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BorderStyle=1,"
            "Outline=2,"
            "Shadow=0,"
            "Alignment=2,"
            "MarginV=48"
            "'"
        )

        filtro_audio = (
            "[0:a]volume=1.0[voz];"
            f"[1:a]volume={self.volumen_musica:.3f}[musica];"
            "[voz][musica]"
            "amix=inputs=2:duration=first:dropout_transition=2[a]"
        )

        comando = [
            ffmpeg,
            "-y",
            "-i",
            str(video),
            "-stream_loop",
            "-1",
            "-i",
            str(musica),
            "-vf",
            filtro_subtitulos,
            "-filter_complex",
            filtro_audio,
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(salida),
        ]

        subprocess.run(
            comando,
            cwd=self.project_root,
            check=True,
        )

        if not salida.exists() or salida.stat().st_size == 0:
            raise RuntimeError(
                "FFmpeg terminó sin crear el video final."
            )

        return salida, True
