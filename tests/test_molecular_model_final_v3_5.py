from __future__ import annotations

import unittest

from autotube.visuals.local_asset_generator import (
    ALTO,
    AMARILLO,
    ANCHO,
    AZUL,
    CIAN,
    ROJO,
    VERDE,
    generar_texto_animado,
)
from autotube.visuals.visual_repair import (
    FINAL_FACTUAL_CONTRACTS,
    _repair_clip,
)


DESCRIPTION = (
    "Video real de científicos en un laboratorio de investigación médica "
    "observando modelos moleculares tridimensionales en una pantalla de "
    "alta tecnología."
)


def _element(segment: int = 10, clip: int = 3) -> dict:
    return {
        "segmento_indice": segment,
        "clip_orden": clip,
        "segmento_titulo": "El impacto transformador en la sociedad contemporánea",
        "tipo_recurso": "video_stock",
        "descripcion": DESCRIPTION,
        "descripcion_editorial_original": "",
        "texto_pantalla": "Ciencia y Medicina",
        "texto_narrado": (
            "Algoritmos hiperavanzados predicen la estructura tridimensional "
            "de las proteínas y aceleran la búsqueda de nuevos fármacos."
        ),
        "estado": "descargado",
        "archivo": "laboratorio_generico.mp4",
    }


class MolecularModelFinalV35Test(unittest.TestCase):
    def test_round_three_creates_exact_molecular_contract(self) -> None:
        expected = FINAL_FACTUAL_CONTRACTS["s10_c003"]
        repaired = _repair_clip(_element(), round_number=3)
        self.assertEqual(repaired["tipo_recurso"], "texto_animado")
        self.assertEqual(repaired["texto_pantalla"], expected["screen"])
        self.assertEqual(repaired["estilo_tarjeta"], "proteina_3d_medicina")
        self.assertIn("modelo molecular tridimensional", repaired["descripcion"])
        self.assertIn("proteína", repaired["descripcion"])

    def test_round_two_preserves_authentic_resource_search(self) -> None:
        repaired = _repair_clip(_element(), round_number=2)
        self.assertNotEqual(repaired["tipo_recurso"], "texto_animado")
        self.assertNotEqual(repaired.get("estilo_tarjeta"), "proteina_3d_medicina")

    def test_contract_is_scoped_to_exact_event_id(self) -> None:
        repaired = _repair_clip(_element(segment=10, clip=2), round_number=3)
        self.assertNotEqual(repaired.get("estilo_tarjeta"), "proteina_3d_medicina")

    def test_generated_card_contains_prominent_molecular_visual(self) -> None:
        repaired = _repair_clip(_element(), round_number=3)
        image = generar_texto_animado(repaired)
        self.assertEqual(image.size, (ANCHO, ALTO))
        molecular_colors = {
            image.getpixel((220, 600)),
            image.getpixel((300, 455)),
            image.getpixel((405, 555)),
            image.getpixel((500, 390)),
            image.getpixel((700, 365)),
        }
        self.assertEqual(
            molecular_colors,
            {AZUL, CIAN, VERDE, AMARILLO, ROJO},
        )


if __name__ == "__main__":
    unittest.main()
