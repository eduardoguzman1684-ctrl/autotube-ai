from __future__ import annotations

import unittest

from autotube.visuals.visual_repair import (
    _enrich_contract,
    _repair_clip,
)


class VisualContractV24Test(unittest.TestCase):
    def test_real_rejected_contracts_receive_specific_search_queries(self) -> None:
        cases = [
            (
                "Fotografia historica de los investigadores fundadores en "
                "Dartmouth College en 1956.",
                "1956 Dartmouth artificial intelligence workshop participants archive",
            ),
            (
                "Fotografia real de archivo de una computadora central de la "
                "decada de 1950 con operadores trabajando.",
                "1950s mainframe computer operators historical photograph",
            ),
            (
                "Video de archivo real mostrando una lectora de tarjetas "
                "perforadas en una sala de servidores de los anos 50.",
                "1950s punch card reader operator historical photograph",
            ),
            (
                "Fotografia real de archivo de John McCarthy trabajando en "
                "una pizarra con ecuaciones matematicas.",
                "John McCarthy computer scientist blackboard photograph",
            ),
            (
                "Video de archivo de cientificos de la computacion analizando "
                "diagramas de flujo en una oficina de los anos 50.",
                "1950s computer scientists flowchart office historical photograph",
            ),
            (
                "Fotografia real del documento original de la propuesta de la "
                "Conferencia de Dartmouth de 1955.",
                "Dartmouth proposal artificial intelligence 1955 original document",
            ),
        ]

        for description, expected_query in cases:
            with self.subTest(expected_query=expected_query):
                enriched = _enrich_contract(
                    {
                        "tipo_recurso": "imagen_stock",
                        "descripcion": description,
                        "criterios_obligatorios": [],
                        "elementos_prohibidos": [],
                        "consultas_alternativas": [],
                    }
                )
                self.assertIn(expected_query, enriched["consultas_alternativas"])

    def test_converts_explicit_animated_text_to_local_resource(self) -> None:
        clip = {
            "tipo_recurso": "imagen_stock",
            "texto_pantalla": "¿Es posible replicar la mente humana?",
            "descripcion": (
                "Texto animado central con la pregunta fundamental sobre "
                "la replicacion de la mente humana mediante circuitos y codigo."
            ),
            "texto_narrado": "Es posible replicar la mente humana.",
            "criterios_obligatorios": [],
            "elementos_prohibidos": [],
            "consultas_alternativas": [],
        }

        enriched = _enrich_contract(clip)

        self.assertEqual(enriched["tipo_recurso"], "texto_animado")
        self.assertIn(
            'El texto visible debe decir exactamente: "¿Es posible replicar la mente humana?".',
            enriched["criterios_obligatorios"],
        )
        self.assertTrue(enriched["concepto_central"])
        self.assertTrue(enriched["elementos_prohibidos"])

    def test_adds_directed_queries_for_dartmouth_document(self) -> None:
        clip = {
            "tipo_recurso": "imagen_stock",
            "texto_pantalla": "Manifiesto Fundador",
            "descripcion": (
                "Fotografia real del documento original de la propuesta de "
                "la Conferencia de Dartmouth de 1955."
            ),
            "texto_narrado": "Esta afirmacion se convirtio en el manifiesto fundador.",
            "criterios_obligatorios": [],
            "elementos_prohibidos": [],
            "consultas_alternativas": [],
        }

        enriched = _enrich_contract(clip)

        self.assertIn(
            "Dartmouth proposal artificial intelligence 1955 original document",
            enriched["consultas_alternativas"],
        )
        self.assertIn(
            "Tecnologia, ropa, oficinas o infraestructura modernas.",
            enriched["elementos_prohibidos"],
        )
        self.assertIn(
            "Ilustracion ficticia presentada como una fotografia real.",
            enriched["elementos_prohibidos"],
        )

    def test_historical_video_prefers_exact_archive_image_from_first_round(self) -> None:
        clip = {
            "segmento_indice": 2,
            "clip_orden": 5,
            "tipo_recurso": "video_stock",
            "descripcion": (
                "Video de archivo de cientificos de la computacion analizando "
                "diagramas de flujo en una oficina de los anos 50."
            ),
            "texto_narrado": "Cada aspecto del aprendizaje puede describirse.",
            "criterios_obligatorios": [],
            "elementos_prohibidos": [],
            "consultas_alternativas": [],
        }

        repaired = _repair_clip(clip, round_number=1)

        self.assertEqual(repaired["tipo_recurso"], "imagen_stock")
        self.assertEqual(
            repaired["busqueda_en"],
            "1950s computer scientists flowchart office historical photograph",
        )
        self.assertTrue(repaired["criterios_obligatorios"])

    def test_preserves_existing_editorial_rules_and_adds_missing_safety(self) -> None:
        clip = {
            "tipo_recurso": "imagen_stock",
            "descripcion": "Fotografia real de John McCarthy en una pizarra.",
            "texto_narrado": "John McCarthy organizo el taller.",
            "criterios_obligatorios": ["Debe aparecer John McCarthy."],
            "elementos_prohibidos": ["No usar otra persona."],
            "consultas_alternativas": ["John McCarthy blackboard"],
        }

        enriched = _enrich_contract(clip)

        self.assertEqual(
            enriched["criterios_obligatorios"][0],
            "Debe aparecer John McCarthy.",
        )
        self.assertEqual(
            enriched["elementos_prohibidos"][0],
            "No usar otra persona.",
        )
        self.assertEqual(
            enriched["consultas_alternativas"][0],
            "John McCarthy blackboard",
        )
        self.assertIn(
            "John McCarthy computer scientist blackboard photograph",
            enriched["consultas_alternativas"],
        )


if __name__ == "__main__":
    unittest.main()
