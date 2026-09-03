from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autotube.visuals.final_visual_auditor import _difference_hash, _hamming
from autotube.visuals.local_asset_generator import generar_texto_animado
from autotube.visuals.visual_repair import _repair_clip


HISTORICAL_CASES = [
    (
        3,
        2,
        "Fotografía real de archivo de Marvin Minsky en el laboratorio de "
        "inteligencia artificial del MIT.",
        "Marvin Minsky",
        "perfil_minsky",
    ),
    (
        3,
        3,
        "Fotografía real de archivo de Allen Newell y Herbert Simon trabajando "
        "en la Universidad Carnegie Mellon.",
        "Newell + Simon",
        "dupla_newell_simon",
    ),
    (
        3,
        4,
        "Fotografía real de archivo de Claude Shannon en su laboratorio de los "
        "laboratorios Bell.",
        "Claude Shannon",
        "perfil_shannon",
    ),
    (
        3,
        5,
        "Video de archivo de un sistema automatizado electromecánico complejo "
        "de época con relés y cables.",
        "Automatización electromecánica",
        "circuito_electromecanico",
    ),
    (
        3,
        6,
        "Fotografía real de archivo de académicos reunidos alrededor de una mesa "
        "de trabajo en una conferencia universitaria de los años 50.",
        "Ideas alrededor de una mesa",
        "mesa_dartmouth",
    ),
    (
        4,
        1,
        "Fotografía real de archivo de la portada del documento mecanografiado "
        "de la propuesta de Dartmouth con el título Artificial Intelligence.",
        "Propuesta fundacional de la IA",
        "documento_dartmouth",
    ),
]


def _element(segment: int, clip: int, description: str) -> dict:
    return {
        "segmento_indice": segment,
        "clip_orden": clip,
        "segmento_titulo": "Historia de la inteligencia artificial",
        "tipo_recurso": "imagen_stock",
        "descripcion": description,
        "texto_narrado": description,
        "estado": "descargado",
        "archivo": "recurso_rechazado.jpg",
    }


class HistoricalEvidenceV27Test(unittest.TestCase):
    def test_round_three_has_a_factual_distinct_contract_for_every_case(self) -> None:
        styles = set()
        for segment, clip, description, required_text, expected_style in HISTORICAL_CASES:
            with self.subTest(segment=segment, clip=clip):
                repaired = _repair_clip(
                    _element(segment, clip, description),
                    round_number=3,
                )
                self.assertEqual(repaired["tipo_recurso"], "texto_animado")
                self.assertIn(required_text, repaired["texto_pantalla"])
                self.assertEqual(repaired["estilo_tarjeta"], expected_style)
                self.assertIn("Tarjeta documental", repaired["descripcion"])
                self.assertNotIn("archivo", repaired.get("fuente", "").lower())
                styles.add(repaired["estilo_tarjeta"])
        self.assertEqual(len(styles), len(HISTORICAL_CASES))

    def test_round_two_still_prefers_authentic_archive(self) -> None:
        segment, clip, description, _, _ = HISTORICAL_CASES[0]
        repaired = _repair_clip(
            _element(segment, clip, description),
            round_number=2,
        )
        self.assertEqual(repaired["tipo_recurso"], "imagen_stock")
        self.assertNotIn("estilo_tarjeta", repaired)

    def test_adjacent_editorial_cards_are_not_perceptual_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = []
            for index, case in enumerate(HISTORICAL_CASES):
                segment, clip, description, _, _ = case
                repaired = _repair_clip(
                    _element(segment, clip, description),
                    round_number=3,
                )
                path = Path(temporary) / f"card_{index}.png"
                generar_texto_animado(repaired).save(path, format="PNG")
                paths.append(path)

            hashes = [_difference_hash(path) for path in paths]
            distances = [
                _hamming(first, second)
                for first, second in zip(hashes, hashes[1:])
            ]
            self.assertTrue(
                all(distance > 2 for distance in distances),
                msg=f"Distancias perceptuales adyacentes: {distances}",
            )


if __name__ == "__main__":
    unittest.main()
