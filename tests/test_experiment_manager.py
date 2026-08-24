from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from autotube.content.experiment_manager import (
    GestorExperimentosYouTube,
)


class ClienteFalso:
    def generar_json(
        self,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "variantes": [
                {
                    "titulo": (
                        "Titulo alternativo B sobre "
                        "inteligencia artificial"
                    ),
                    "texto_miniatura": "CAMBIO TOTAL",
                    "gancho_inicial": (
                        "Una consecuencia sorprendente "
                        "aparece desde el primer segundo."
                    ),
                    "duracion_objetivo_minutos": 10,
                    "angulo": "Consecuencia",
                    "hipotesis": (
                        "La variante B puede mejorar "
                        "la metrica principal."
                    ),
                },
                {
                    "titulo": (
                        "Titulo alternativo C con "
                        "una pregunta central"
                    ),
                    "texto_miniatura": "NUEVO RIESGO",
                    "gancho_inicial": (
                        "Una pregunta directa revela "
                        "el conflicto inmediatamente."
                    ),
                    "duracion_objetivo_minutos": 11,
                    "angulo": "Pregunta",
                    "hipotesis": (
                        "La variante C puede mejorar "
                        "la metrica principal."
                    ),
                },
            ]
        }


class ExperimentosYouTubeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.root = Path(self.temporal.name)

        publish = self.root / "data" / "publish"
        scripts = self.root / "data" / "scripts"
        analytics = self.root / "data" / "analytics"

        publish.mkdir(parents=True)
        scripts.mkdir(parents=True)
        analytics.mkdir(parents=True)

        metadata = {
            "title": (
                "Algoritmos de Guerra y "
                "Decisiones de Inteligencia Artificial"
            ),
        }

        guion = {
            "guion": {
                "titulo": metadata["title"],
                "gancho_inicial": (
                    "Este es el gancho original que debe "
                    "permanecer igual durante la prueba."
                ),
                "duracion_estimada_minutos": 15,
                "objetivo": "Explicar un riesgo tecnologico.",
                "introduccion": "Introduccion del documental.",
                "escenas": [],
            }
        }

        perfil = {
            "nivel_confianza": "exploratoria",
            "contexto_prompt": [
                "Cambiar una sola variable.",
            ],
        }

        (publish / "metadata.json").write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )

        (
            scripts
            / "guion_corregido_20260824_000000.json"
        ).write_text(
            json.dumps(guion),
            encoding="utf-8",
        )

        (
            analytics
            / "strategy_profile.json"
        ).write_text(
            json.dumps(perfil),
            encoding="utf-8",
        )

        self.gestor = GestorExperimentosYouTube(
            project_root=self.root,
            cliente=ClienteFalso(),
        )

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def test_cambia_una_sola_variable(self) -> None:
        campos = {
            "titulo",
            "texto_miniatura",
            "gancho_inicial",
            "duracion_objetivo_minutos",
        }

        mapa = {
            "titulo": "titulo",
            "miniatura": "texto_miniatura",
            "gancho": "gancho_inicial",
            "duracion": "duracion_objetivo_minutos",
        }

        for variable, campo_variable in mapa.items():
            with self.subTest(variable=variable):
                resultado = self.gestor.generar(
                    variable=variable,
                    cantidad=3,
                    renderizar_miniaturas=False,
                )

                variantes = resultado[
                    "experimento"
                ]["variantes"]

                control = variantes[0]

                for variante in variantes[1:]:
                    for campo in campos:
                        if campo == campo_variable:
                            self.assertNotEqual(
                                variante[campo],
                                control[campo],
                            )
                        else:
                            self.assertEqual(
                                variante[campo],
                                control[campo],
                            )

    def test_no_declara_ganador_sin_minimo(self) -> None:
        resultado = self.gestor.generar(
            variable="titulo",
            cantidad=3,
            renderizar_miniaturas=False,
        )

        archivo = resultado["archivo"]

        evaluacion = self.gestor.registrar_resultado(
            codigo="A",
            vistas=99,
            ctr=3.0,
            archivo=archivo,
        )["evaluacion"]

        self.assertEqual(
            evaluacion["estado"],
            "recopilando_datos",
        )

        self.assertEqual(
            evaluacion["ganador_provisional"],
            "",
        )

    def test_declara_solo_ganador_provisional(self) -> None:
        resultado = self.gestor.generar(
            variable="titulo",
            cantidad=3,
            renderizar_miniaturas=False,
        )

        archivo = resultado["archivo"]

        self.gestor.registrar_resultado(
            codigo="A",
            vistas=100,
            ctr=3.0,
            archivo=archivo,
        )

        self.gestor.registrar_resultado(
            codigo="B",
            vistas=100,
            ctr=4.0,
            archivo=archivo,
        )

        evaluacion = self.gestor.registrar_resultado(
            codigo="C",
            vistas=100,
            ctr=3.2,
            archivo=archivo,
        )["evaluacion"]

        self.assertEqual(
            evaluacion["estado"],
            "ganador_provisional",
        )

        self.assertEqual(
            evaluacion["ganador_provisional"],
            "B",
        )

    def test_recorta_por_palabra_completa(self) -> None:
        resultado = self.gestor._texto(
            "uno dos tres cuatro",
            "",
            12,
        )

        self.assertEqual(
            resultado,
            "uno dos",
        )


if __name__ == "__main__":
    unittest.main()
