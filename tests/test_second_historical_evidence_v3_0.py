from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autotube.visuals.final_visual_auditor import _difference_hash, _hamming
from autotube.visuals.local_asset_generator import generar_texto_animado
from autotube.visuals.visual_repair import _repair_clip


SECOND_HISTORICAL_CASES = [
    (
        4,
        2,
        "Fotografía real de archivo de Norbert Wiener trabajando en su "
        "despacho académico.",
        "Norbert Wiener",
        "perfil_wiener",
    ),
    (
        4,
        3,
        "Video de archivo real de componentes electrónicos antiguos procesando "
        "señales eléctricas en un laboratorio de investigación.",
        "Componentes y circuitos de época",
        "componentes_electronicos_historicos",
    ),
    (
        4,
        4,
        "Fotografía real de archivo de una revista científica de los años 50 "
        "con artículos sobre máquinas pensantes.",
        "Máquinas pensantes",
        "revista_maquinas_pensantes",
    ),
    (
        4,
        5,
        "Fotografía real de archivo de un libro clásico de filosofía y "
        "tecnología de mediados del siglo XX en una biblioteca universitaria.",
        "Impacto filosófico",
        "libro_filosofia_tecnologia",
    ),
    (
        5,
        2,
        "Fotografía real de archivo de investigadores sentados alrededor de "
        "una mesa al aire libre en el campus de Dartmouth.",
        "Dartmouth · verano de 1956",
        "mesa_dartmouth_exterior",
    ),
    (
        5,
        3,
        "Fotografía real de archivo de un tablero de ajedrez tradicional junto "
        "a una computadora central de los años 50.",
        "Ajedrez + computadora",
        "ajedrez_computadora_historica",
    ),
]


def _element(segment: int, clip: int, description: str) -> dict:
    return {
        "segmento_indice": segment,
        "clip_orden": clip,
        "segmento_titulo": "Historia de la inteligencia artificial",
        "tipo_recurso": "imagen_stock",
        "descripcion": description,
        "descripcion_editorial_original": "",
        "texto_narrado": description,
        "estado": "descargado",
        "archivo": "recurso_rechazado.jpg",
    }


class SecondHistoricalEvidenceV30Test(unittest.TestCase):
    def test_round_three_creates_six_exact_distinct_contracts(self) -> None:
        styles = set()
        for segment, clip, description, required_text, expected_style in (
            SECOND_HISTORICAL_CASES
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
        self.assertEqual(len(styles), len(SECOND_HISTORICAL_CASES))

    def test_round_two_keeps_searching_for_authentic_archive(self) -> None:
        for segment, clip, description, _, _ in SECOND_HISTORICAL_CASES:
            with self.subTest(segment=segment, clip=clip):
                repaired = _repair_clip(
                    _element(segment, clip, description),
                    round_number=2,
                )
                self.assertNotEqual(repaired["tipo_recurso"], "texto_animado")
                self.assertNotIn("estilo_tarjeta", repaired)

    def test_visible_text_criteria_do_not_require_slashes(self) -> None:
        segment, clip, description, _, _ = SECOND_HISTORICAL_CASES[0]
        repaired = _repair_clip(
            _element(segment, clip, description),
            round_number=3,
        )
        criteria = " ".join(repaired["criterios_obligatorios"])

        self.assertNotIn(" / ", criteria)
        self.assertIn("no requieren barras", criteria)

    def test_adjacent_cards_are_not_perceptual_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hashes = []
            for index, case in enumerate(SECOND_HISTORICAL_CASES):
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
                msg=f"Distancias perceptuales adyacentes: {distances}",
            )


if __name__ == "__main__":
    unittest.main()
