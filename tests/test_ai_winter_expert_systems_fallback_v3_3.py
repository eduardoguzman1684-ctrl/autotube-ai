from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autotube.visuals.final_visual_auditor import _difference_hash, _hamming
from autotube.visuals.local_asset_generator import generar_texto_animado
from autotube.visuals.visual_repair import _repair_clip


AI_WINTER_CASES = [
    (
        7,
        1,
        "Fotografía real de archivo de grandes unidades de disco duro magnético "
        "de los años 60 con capacidad de almacenamiento muy limitada.",
        "Memoria magnética · años 60",
        "almacenamiento_magnetico_1960",
    ),
    (
        7,
        2,
        "Fotografía real de archivo de diccionarios multilingües y textos "
        "impresos en un centro de traducción lingüística de los años 60.",
        "La ambigüedad del lenguaje",
        "traduccion_automatica_1960",
    ),
    (
        7,
        3,
        "Fotografía real de archivo de un informe oficial gubernamental impreso "
        "sobre papel oficial británico de los años 70.",
        "Informe Lighthill · 1973",
        "informe_lighthill_1973",
    ),
    (
        7,
        4,
        "Fotografía real de archivo de un pasillo vacío en un departamento "
        "universitario de computación durante los recortes presupuestarios.",
        "Primer invierno de la IA",
        "invierno_ia_1970",
    ),
    (
        7,
        5,
        "Fotografía real de archivo de un investigador solitario analizando "
        "diagramas de flujo bajo una lámpara de escritorio en una oficina oscura.",
        "Reglas fijas no bastan",
        "limites_reglas_fijas",
    ),
    (
        8,
        2,
        "Fotografía real de archivo de manuales técnicos encuadernados y carpetas "
        "llenas de reglas lógicas en una estantería de oficina de los años 80.",
        "Sistemas expertos · años 80",
        "sistemas_expertos_reglas",
    ),
    (
        8,
        4,
        "Fotografía real de archivo de un investigador trabajando frente a una "
        "computadora personal de escritorio de finales de los 90 analizando "
        "gráficos de datos.",
        "Machine Learning · años 90",
        "machine_learning_datos_1990",
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


class AIWinterExpertSystemsFallbackV33Test(unittest.TestCase):
    def test_round_three_creates_seven_exact_factual_cards(self) -> None:
        styles = set()
        for segment, clip, description, required_text, expected_style in (
            AI_WINTER_CASES
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
        self.assertEqual(len(styles), len(AI_WINTER_CASES))

    def test_round_two_preserves_authentic_archive_search(self) -> None:
        for segment, clip, description, _, _ in AI_WINTER_CASES:
            with self.subTest(segment=segment, clip=clip):
                repaired = _repair_clip(
                    _element(segment, clip, description),
                    round_number=2,
                )
                self.assertNotEqual(repaired["tipo_recurso"], "texto_animado")
                self.assertNotIn("estilo_tarjeta", repaired)

    def test_visible_text_contract_uses_lines_not_slashes(self) -> None:
        for segment, clip, description, _, _ in AI_WINTER_CASES:
            repaired = _repair_clip(
                _element(segment, clip, description),
                round_number=3,
            )
            criterion = " ".join(repaired["criterios_obligatorios"])
            self.assertIn("no requieren barras", criterion)
            self.assertNotIn(" / ", repaired["texto_pantalla"])

    def test_generated_cards_are_not_perceptual_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hashes = []
            for index, case in enumerate(AI_WINTER_CASES):
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
