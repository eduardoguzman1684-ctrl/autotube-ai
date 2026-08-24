from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autotube.video import hardware_encoder
from autotube.video.finalizer import FinalizadorVideo
from autotube.video.hardware_encoder import (
    ConfiguracionCodificador,
    seleccionar_codificador,
)


class SelectorCodificadorTest(unittest.TestCase):
    def test_auto_prefiere_cpu_para_clips(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTOTUBE_VIDEO_ENCODER": "auto",
                "AUTOTUBE_QSV_QUALITY": "",
            },
            clear=False,
        ):
            with patch.object(
                hardware_encoder,
                "probar_qsv",
            ) as prueba:
                configuracion = seleccionar_codificador(
                    crf_cpu=27,
                    preset_cpu="veryfast",
                    preferir_qsv=False,
                )

        self.assertFalse(
            configuracion.hardware
        )
        self.assertEqual(
            configuracion.nombre,
            "libx264",
        )
        prueba.assert_not_called()

    def test_auto_usa_qsv_en_render_final(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTOTUBE_VIDEO_ENCODER": "auto",
                "AUTOTUBE_QSV_QUALITY": "",
            },
            clear=False,
        ):
            with patch.object(
                hardware_encoder,
                "probar_qsv",
                return_value=(
                    True,
                    "disponible",
                ),
            ):
                configuracion = seleccionar_codificador(
                    crf_cpu=18,
                    preset_cpu="fast",
                )

        self.assertTrue(
            configuracion.hardware
        )
        self.assertEqual(
            configuracion.nombre,
            "h264_qsv",
        )
        self.assertEqual(
            configuracion.calidad,
            20,
        )

    def test_qsv_forzado_supera_preferencia_cpu(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTOTUBE_VIDEO_ENCODER": "qsv",
                "AUTOTUBE_QSV_QUALITY": "24",
            },
            clear=False,
        ):
            with patch.object(
                hardware_encoder,
                "probar_qsv",
                return_value=(
                    True,
                    "disponible",
                ),
            ):
                configuracion = seleccionar_codificador(
                    crf_cpu=27,
                    preset_cpu="veryfast",
                    preferir_qsv=False,
                )

        self.assertTrue(
            configuracion.hardware
        )
        self.assertEqual(
            configuracion.calidad,
            24,
        )

    def test_qsv_no_disponible_vuelve_a_cpu(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTOTUBE_VIDEO_ENCODER": "auto",
                "AUTOTUBE_QSV_QUALITY": "",
            },
            clear=False,
        ):
            with patch.object(
                hardware_encoder,
                "probar_qsv",
                return_value=(
                    False,
                    "fallo",
                ),
            ):
                configuracion = seleccionar_codificador(
                    crf_cpu=20,
                    preset_cpu="fast",
                )

        self.assertFalse(
            configuracion.hardware
        )
        self.assertEqual(
            configuracion.nombre,
            "libx264",
        )


class RecuperacionFinalizadorTest(unittest.TestCase):
    def test_reintenta_por_cpu_si_qsv_falla(self) -> None:
        with tempfile.TemporaryDirectory() as temporal:
            root = Path(temporal)
            carpeta = root / "render"
            carpeta.mkdir(
                parents=True
            )

            video = carpeta / "video_final.mp4"
            srt = root / "subtitulos.srt"
            musica = root / "musica.wav"

            video.write_bytes(
                b"video"
            )
            srt.write_text(
                "1\n00:00:00,000 --> "
                "00:00:01,000\nPrueba\n",
                encoding="utf-8",
            )
            musica.write_bytes(
                b"audio"
            )

            class FinalizadorPrueba(
                FinalizadorVideo
            ):
                def _buscar_video(self) -> Path:
                    return video

                def _buscar_srt(self) -> Path:
                    return srt

                def _buscar_musica(self) -> Path:
                    return musica

            qsv = ConfiguracionCodificador(
                nombre="h264_qsv",
                hardware=True,
                calidad=20,
                opciones=(
                    "-c:v",
                    "h264_qsv",
                ),
            )

            cpu = ConfiguracionCodificador(
                nombre="libx264",
                hardware=False,
                calidad=18,
                opciones=(
                    "-c:v",
                    "libx264",
                ),
            )

            llamadas = 0

            def ejecutar(
                comando,
                **kwargs,
            ):
                nonlocal llamadas
                llamadas += 1

                if llamadas == 1:
                    raise subprocess.CalledProcessError(
                        1,
                        comando,
                    )

                salida = (
                    carpeta
                    / "video_final_subtitulado_musica.mp4"
                )
                salida.write_bytes(
                    b"resultado"
                )

                return subprocess.CompletedProcess(
                    comando,
                    0,
                )

            with patch(
                "autotube.video.finalizer."
                "seleccionar_codificador",
                side_effect=[
                    qsv,
                    cpu,
                ],
            ):
                with patch(
                    "autotube.video.finalizer."
                    "marcar_qsv_fallido"
                ) as marcar:
                    with patch(
                        "autotube.video.finalizer."
                        "subprocess.run",
                        side_effect=ejecutar,
                    ):
                        resultado, generado = (
                            FinalizadorPrueba(
                                project_root=root
                            ).finalizar(
                                forzar=True
                            )
                        )

            self.assertTrue(
                generado
            )
            self.assertTrue(
                resultado.is_file()
            )
            self.assertEqual(
                llamadas,
                2,
            )
            marcar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
