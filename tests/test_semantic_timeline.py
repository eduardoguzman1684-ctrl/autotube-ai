from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autotube.timeline.semantic_timeline import (
    GeneradorTimelineSemantica,
    TimelineValidationError,
)


class TimelineSemanticaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.assets_path = self.root / "assets_manifest.json"
        self.audio_path = self.root / "audio_manifest.json"

        self.files = []
        for index in range(1, 4):
            path = self.root / f"visual_{index}.jpg"
            path.write_bytes(b"visual")
            self.files.append(path)

        self.audio = {
            "titulo": "Prueba",
            "duracion_total_segundos": 9.0,
            "segmentos": [
                {"duracion_real_segundos": 5.0},
                {"duracion_real_segundos": 4.0},
            ],
        }
        self.assets = {
            "titulo": "Prueba",
            "channel_slug": "nexon_ia",
            "elementos": [
                self._asset(1, 1, 0.0, 3.0, self.files[0]),
                self._asset(1, 2, 3.0, 5.0, self.files[1]),
                self._asset(2, 1, 5.0, 9.0, self.files[2]),
            ],
        }
        self.generator = GeneradorTimelineSemantica(self.output)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _asset(
        segment: int,
        order: int,
        start: float,
        end: float,
        path: Path,
    ) -> dict[str, object]:
        return {
            "segmento_indice": segment,
            "clip_orden": order,
            "estado": "descargado",
            "archivo": str(path),
            "inicio_segundos": start,
            "final_segundos": end,
            "texto_narrado": f"Narracion {segment}-{order}",
            "tipo_recurso": "imagen_stock",
            "descripcion": "Visual directamente relacionado",
            "movimiento": "zoom lento",
            "concepto_central": "concepto",
            "criterios_obligatorios": ["sujeto"],
            "elementos_prohibidos": ["relleno"],
        }

    def test_crea_cobertura_exacta_en_milisegundos(self) -> None:
        timeline = self.generator.construir(
            assets_manifest=self.assets,
            audio_manifest=self.audio,
            assets_path=self.assets_path,
            audio_path=self.audio_path,
            channel_slug="nexon_ia",
        )

        self.assertEqual(timeline["duration_ms"], 9000)
        self.assertEqual(len(timeline["events"]), 3)
        self.assertEqual(timeline["events"][0]["start_ms"], 0)
        self.assertEqual(timeline["events"][-1]["end_ms"], 9000)
        self.assertEqual(
            timeline["events"][1]["speech_text"],
            "Narracion 1-2",
        )

    def test_rechaza_huecos_entre_visuales(self) -> None:
        self.assets["elementos"][1]["inicio_segundos"] = 3.5

        with self.assertRaises(TimelineValidationError):
            self.generator.construir(
                assets_manifest=self.assets,
                audio_manifest=self.audio,
                assets_path=self.assets_path,
                audio_path=self.audio_path,
                channel_slug="nexon_ia",
            )

    def test_rechaza_recurso_pendiente(self) -> None:
        self.assets["elementos"][0]["estado"] = "pendiente_sin_recurso"

        with self.assertRaises(TimelineValidationError):
            self.generator.construir(
                assets_manifest=self.assets,
                audio_manifest=self.audio,
                assets_path=self.assets_path,
                audio_path=self.audio_path,
                channel_slug="nexon_ia",
            )


if __name__ == "__main__":
    unittest.main()
