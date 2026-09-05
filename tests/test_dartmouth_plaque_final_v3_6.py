from __future__ import annotations

import unittest

from autotube.visuals.local_asset_generator import (
    ALTO,
    ANCHO,
    BRONCE,
    BRONCE_CLARO,
    BRONCE_OSCURO,
    generar_texto_animado,
)
from autotube.visuals.visual_repair import (
    FINAL_FACTUAL_CONTRACTS,
    _repair_clip,
)


DESCRIPTION = (
    "Fotografía real de archivo de una placa conmemorativa histórica en el "
    "campus de Dartmouth College dedicada a la conferencia de 1956."
)


def _element(segment: int = 12, clip: int = 1) -> dict:
    return {
        "segmento_indice": segment,
        "clip_orden": clip,
        "segmento_titulo": "El legado vivo de 1956",
        "tipo_recurso": "imagen_stock",
        "descripcion": DESCRIPTION,
        "descripcion_editorial_original": "",
        "texto_pantalla": "El Legado de Dartmouth",
        "texto_narrado": (
            "El legado intelectual de John McCarthy, Marvin Minsky y Claude "
            "Shannon sigue más vivo y relevante que nunca."
        ),
        "estado": "descargado",
        "archivo": "fotografia_historica_generica.jpg",
    }


class DartmouthPlaqueFinalV36Test(unittest.TestCase):
    def test_round_three_creates_exact_plaque_contract(self) -> None:
        expected = FINAL_FACTUAL_CONTRACTS["s12_c001"]
        repaired = _repair_clip(_element(), round_number=3)
        self.assertEqual(repaired["tipo_recurso"], "texto_animado")
        self.assertEqual(repaired["texto_pantalla"], expected["screen"])
        self.assertEqual(repaired["estilo_tarjeta"], "placa_dartmouth_1956")
        self.assertIn("placa conmemorativa", repaired["descripcion"])
        self.assertIn("Dartmouth College", repaired["descripcion"])
        self.assertIn("1956", repaired["descripcion"])

    def test_round_two_preserves_authentic_archive_search(self) -> None:
        repaired = _repair_clip(_element(), round_number=2)
        self.assertNotEqual(repaired["tipo_recurso"], "texto_animado")
        self.assertNotEqual(repaired.get("estilo_tarjeta"), "placa_dartmouth_1956")

    def test_contract_is_scoped_to_exact_event_id(self) -> None:
        repaired = _repair_clip(_element(segment=12, clip=2), round_number=3)
        self.assertNotEqual(repaired.get("estilo_tarjeta"), "placa_dartmouth_1956")

    def test_generated_card_contains_unmistakable_bronze_plaque(self) -> None:
        repaired = _repair_clip(_element(), round_number=3)
        image = generar_texto_animado(repaired)
        self.assertEqual(image.size, (ANCHO, ALTO))
        self.assertEqual(image.getpixel((120, 300)), BRONCE_OSCURO)
        self.assertEqual(image.getpixel((500, 330)), BRONCE)
        self.assertEqual(image.getpixel((175, 350)), BRONCE_OSCURO)
        self.assertEqual(image.getpixel((175, 340)), BRONCE_CLARO)


if __name__ == "__main__":
    unittest.main()
