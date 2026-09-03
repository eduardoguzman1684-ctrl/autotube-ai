from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autotube.visuals.final_visual_auditor import _difference_hash, _hamming
from autotube.visuals.local_asset_generator import generar_texto_animado
from autotube.visuals.visual_repair import _repair_clip


MAINFRAME_SYMBOLIC_CASES = [
    (
        2,
        2,
        "Video de archivo real mostrando el funcionamiento de una lectora de "
        "tarjetas perforadas en una sala de servidores de los años 50.",
        "Tarjetas perforadas",
        "lectora_tarjetas_perforadas",
    ),
    (
        2,
        7,
        "Video de archivo real de un investigador operando los interruptores "
        "de una computadora central en la década de 1950.",
        "Operación mediante interruptores",
        "operador_mainframe_interruptores",
    ),
    (
        5,
        1,
        "Diagrama técnico histórico en papel de archivo que muestra reglas "
        "lógicas simbólicas de los años 50.",
        "Reglas simbólicas",
        "diagrama_reglas_simbolicas",
    ),
    (
        5,
        4,
        "Video de archivo real mostrando las luces parpadeantes de una consola "
        "central de procesamiento en funcionamiento.",
        "Consola central",
        "consola_mainframe_luces",
    ),
]


def _element(segment: int, clip: int, description: str) -> dict:
    return {
        "segmento_indice": segment,
        "clip_orden": clip,
        "segmento_titulo": "Historia de la inteligencia artificial",
        "tipo_recurso": "video_stock",
        "descripcion": description,
        "descripcion_editorial_original": "",
        "texto_narrado": description,
        "estado": "descargado",
        "archivo": "recurso_rechazado.mp4",
    }


class MainframeSymbolicFallbackV31Test(unittest.TestCase):
    def test_round_three_creates_four_exact_factual_cards(self) -> None:
        styles = set()
        for segment, clip, description, required_text, expected_style in (
            MAINFRAME_SYMBOLIC_CASES
        ):
            with self.subTest(segment=segment, clip=clip):
                repaired = _repair_clip(
                    _element(segment, clip, description),
                    round_number=3,
                )
                self.assertEqual(repaired["tipo_recurso"], "texto_animado")
                self.assertIn(required_text, repaired["texto_pantalla"])
                self.assertEqual(repaired["estilo_tarjeta"], expected_style)
                self.assertEqual(
                    repaired["descripcion_editorial_original"], description
                )
                self.assertIn("Tarjeta documental", repaired["descripcion"])
                styles.add(repaired["estilo_tarjeta"])
        self.assertEqual(len(styles), len(MAINFRAME_SYMBOLIC_CASES))

    def test_round_two_preserves_the_authentic_archive_search(self) -> None:
        for segment, clip, description, _, _ in MAINFRAME_SYMBOLIC_CASES:
            with self.subTest(segment=segment, clip=clip):
                repaired = _repair_clip(
                    _element(segment, clip, description),
                    round_number=2,
                )
                self.assertNotEqual(repaired["tipo_recurso"], "texto_animado")
                self.assertNotIn("estilo_tarjeta", repaired)

    def test_visible_text_contract_does_not_require_separators(self) -> None:
        segment, clip, description, _, _ = MAINFRAME_SYMBOLIC_CASES[0]
        repaired = _repair_clip(
            _element(segment, clip, description),
            round_number=3,
        )
        criteria = " ".join(repaired["criterios_obligatorios"])

        self.assertNotIn(" / ", criteria)
        self.assertIn("no requieren barras", criteria)

    def test_generated_cards_are_not_perceptual_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hashes = []
            for index, case in enumerate(MAINFRAME_SYMBOLIC_CASES):
                segment, clip, description, _, _ = case
                repaired = _repair_clip(
                    _element(segment, clip, description),
                    round_number=3,
                )
                path = Path(temporary) / f"card_{index}.png"
                generar_texto_animado(repaired).save(path, format="PNG")
                hashes.append(_difference_hash(path))

            distances = [
                _hamming(first, second)
                for first, second in zip(hashes, hashes[1:])
            ]
            self.assertTrue(
                all(distance > 2 for distance in distances),
                msg=f"Distancias perceptuales: {distances}",
            )


if __name__ == "__main__":
    unittest.main()
