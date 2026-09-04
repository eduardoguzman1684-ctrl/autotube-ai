from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autotube.visuals.final_visual_auditor import _difference_hash, _hamming
from autotube.visuals.local_asset_generator import generar_texto_animado
from autotube.visuals.visual_repair import _repair_clip


LOGIC_THEORIST_CASES = [
    (
        5,
        5,
        "Fotografía real de archivo de un modelo anatómico del cerebro humano "
        "en un laboratorio de neurología de los años 50.",
        "Cerebro y mente",
        "cerebro_anatomico_historico",
    ),
    (
        5,
        6,
        "Fotografía real de archivo de tarjetas perforadas apiladas en cajas "
        "de almacenamiento de cartón.",
        "Datos almacenados en papel",
        "tarjetas_perforadas_archivadas",
    ),
    (
        6,
        1,
        "Fotografía real de archivo de Allen Newell y Herbert Simon revisando "
        "impresiones de software lógico.",
        "Logic Theorist",
        "logic_theorist_1956",
    ),
    (
        6,
        2,
        "Fotografía real de archivo de listados de código fuente impresos en "
        "papel continuo de computadora de 1956.",
        "Código impreso · 1956",
        "codigo_impreso_1956",
    ),
    (
        6,
        3,
        "Fotografía real de archivo del libro Principia Mathematica en una "
        "biblioteca universitaria.",
        "Principia Mathematica",
        "principia_mathematica",
    ),
    (
        6,
        5,
        "Fotografía real de archivo de un auditorio universitario lleno de "
        "investigadores durante una conferencia científica de los años 50.",
        "La IA gana respaldo",
        "auditorio_cientifico_1950",
    ),
    (
        6,
        6,
        "Video de archivo real de científicos revisando documentos de "
        "financiación e informes en una oficina de la administración universitaria.",
        "Financiamiento científico",
        "financiamiento_ia_inicial",
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


class LogicTheoristFallbackV32Test(unittest.TestCase):
    def test_round_three_creates_seven_exact_factual_cards(self) -> None:
        styles = set()
        for segment, clip, description, required_text, expected_style in (
            LOGIC_THEORIST_CASES
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
        self.assertEqual(len(styles), len(LOGIC_THEORIST_CASES))

    def test_round_two_keeps_the_real_archive_contracts(self) -> None:
        for segment, clip, description, _, _ in LOGIC_THEORIST_CASES:
            with self.subTest(segment=segment, clip=clip):
                repaired = _repair_clip(
                    _element(segment, clip, description),
                    round_number=2,
                )
                self.assertNotEqual(repaired["tipo_recurso"], "texto_animado")
                self.assertNotIn("estilo_tarjeta", repaired)

    def test_logic_theorist_card_is_not_the_generic_newell_simon_card(self) -> None:
        segment, clip, description, _, _ = LOGIC_THEORIST_CASES[2]
        repaired = _repair_clip(
            _element(segment, clip, description),
            round_number=3,
        )

        self.assertEqual(repaired["estilo_tarjeta"], "logic_theorist_1956")
        self.assertNotEqual(repaired["estilo_tarjeta"], "dupla_newell_simon")
        self.assertIn("1956", repaired["texto_pantalla"])

    def test_generated_cards_are_not_perceptual_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hashes = []
            for index, case in enumerate(LOGIC_THEORIST_CASES):
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
