from __future__ import annotations

import unittest

from autotube.visuals.visual_repair import _repair_clip


class EditorialContractRecoveryV29Test(unittest.TestCase):
    def test_original_description_recovers_claude_from_contaminated_card(self) -> None:
        contaminated = {
            "segmento_indice": 3,
            "clip_orden": 4,
            "segmento_titulo": "Las mentes detrás del proyecto",
            "tipo_recurso": "texto_animado",
            "descripcion": (
                "Tarjeta documental animada que identifica a Marvin Minsky "
                "como pionero de la inteligencia artificial vinculado al MIT."
            ),
            "descripcion_editorial_original": (
                "Fotografía real de archivo de Claude Shannon en su laboratorio "
                "de los laboratorios Bell."
            ),
            "texto_narrado": (
                "Claude Shannon demostró la aplicación del álgebra booleana "
                "mientras Marvin Minsky estudiaba el aprendizaje."
            ),
            "texto_pantalla": "Marvin Minsky\nPionero de la IA · MIT",
            "estilo_tarjeta": "perfil_minsky",
        }

        repaired = _repair_clip(contaminated, round_number=3)

        self.assertEqual(
            repaired["texto_pantalla"],
            "Claude Shannon\nInformación, lógica y máquinas",
        )
        self.assertEqual(repaired["estilo_tarjeta"], "perfil_shannon")
        self.assertIn("Claude Shannon", repaired["descripcion"])
        self.assertNotIn("Marvin Minsky", repaired["descripcion"])
        self.assertEqual(
            repaired["descripcion_editorial_original"],
            contaminated["descripcion_editorial_original"],
        )

    def test_line_break_contract_does_not_require_a_slash_character(self) -> None:
        element = {
            "segmento_indice": 3,
            "clip_orden": 2,
            "segmento_titulo": "Las mentes detrás del proyecto",
            "tipo_recurso": "imagen_stock",
            "descripcion": (
                "Fotografía real de archivo de Marvin Minsky en el laboratorio "
                "de inteligencia artificial del MIT."
            ),
        }

        repaired = _repair_clip(element, round_number=3)
        criteria = " ".join(repaired["criterios_obligatorios"])

        self.assertNotIn(" / ", criteria)
        self.assertIn("no requieren barras", criteria)
        self.assertIn('"Marvin Minsky"', criteria)
        self.assertIn('"Pionero de la IA · MIT"', criteria)


if __name__ == "__main__":
    unittest.main()
