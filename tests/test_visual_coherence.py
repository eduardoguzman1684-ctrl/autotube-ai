from __future__ import annotations

import re
import unittest

from autotube.visuals.asset_collector import (
    RecolectorRecursos,
)
from autotube.visuals.visual_planner import (
    PLAN_VISUAL_SCHEMA,
    crear_bloques_narracion,
)


def crear_segmento(
    texto: str,
    duracion: float,
    con_marcas: bool = True,
) -> dict[str, object]:
    palabras = re.findall(r"\S+", texto)
    paso = duracion / max(1, len(palabras))

    marcas = [
        {
            "texto": re.sub(
                r"[.!?,;:]+$",
                "",
                palabra,
            ),
            "inicio_segundos": indice * paso,
            "final_segundos": (indice + 1) * paso,
        }
        for indice, palabra in enumerate(palabras)
    ]

    return {
        "duracion_real_segundos": duracion,
        "texto_voz": texto,
        "marcas_palabras": marcas if con_marcas else [],
    }


class CoherenciaPlanVisualTest(unittest.TestCase):
    def test_grafico_es_un_recurso_visual_valido(
        self,
    ) -> None:
        tipos = (
            PLAN_VISUAL_SCHEMA["properties"]
            ["segmentos"]["items"]["properties"]
            ["clips"]["items"]["properties"]
            ["tipo_recurso"]["enum"]
        )

        self.assertIn(
            "grafico",
            tipos,
        )

    def test_corta_en_limites_semanticos(
        self,
    ) -> None:
        texto = (
            "Una red aprende patrones. "
            "Luego compara senales y resultados; "
            "finalmente ajusta decisiones."
        )

        bloques = crear_bloques_narracion(
            segmento=crear_segmento(
                texto=texto,
                duracion=18.0,
            ),
            inicio_global=30.0,
        )

        self.assertEqual(
            len(bloques),
            3,
        )

        self.assertEqual(
            [
                bloque["texto_narrado"][-1]
                for bloque in bloques
            ],
            [
                ".",
                ";",
                ".",
            ],
        )

    def test_mantiene_cobertura_temporal_exacta(
        self,
    ) -> None:
        texto = (
            "Una red aprende patrones. "
            "Luego compara senales y resultados; "
            "finalmente ajusta decisiones."
        )

        bloques = crear_bloques_narracion(
            segmento=crear_segmento(
                texto=texto,
                duracion=18.0,
            ),
            inicio_global=30.0,
        )

        self.assertEqual(
            bloques[0]["inicio_segundos"],
            30.0,
        )
        self.assertEqual(
            bloques[-1]["final_segundos"],
            48.0,
        )

        for anterior, siguiente in zip(
            bloques,
            bloques[1:],
        ):
            self.assertEqual(
                anterior["final_segundos"],
                siguiente["inicio_segundos"],
            )

        self.assertAlmostEqual(
            sum(
                float(
                    bloque["duracion_segundos"]
                )
                for bloque in bloques
            ),
            18.0,
            places=3,
        )

    def test_respaldo_sin_marcas_respeta_frases(
        self,
    ) -> None:
        texto = (
            "Primero observa los datos. "
            "Despues contrasta la evidencia. "
            "Finalmente presenta la conclusion."
        )

        bloques = crear_bloques_narracion(
            segmento=crear_segmento(
                texto=texto,
                duracion=18.0,
                con_marcas=False,
            ),
            inicio_global=0.0,
        )

        self.assertTrue(
            bloques,
        )
        self.assertEqual(
            bloques[-1]["final_segundos"],
            18.0,
        )

        for bloque in bloques:
            self.assertIn(
                bloque["texto_narrado"][-1],
                ".!?,;:",
            )

    def test_frase_larga_tiene_cortes_controlados(
        self,
    ) -> None:
        texto = " ".join(
            f"palabra{indice}"
            for indice in range(24)
        )

        bloques = crear_bloques_narracion(
            segmento=crear_segmento(
                texto=texto,
                duracion=24.0,
            ),
            inicio_global=0.0,
        )

        self.assertGreater(
            len(bloques),
            1,
        )
        self.assertLessEqual(
            max(
                float(
                    bloque["duracion_segundos"]
                )
                for bloque in bloques
            ),
            10.5,
        )
        self.assertEqual(
            bloques[-1]["final_segundos"],
            24.0,
        )


    def test_esquema_exige_metadatos_de_coherencia(
        self,
    ) -> None:
        esquema_clip = (
            PLAN_VISUAL_SCHEMA["properties"]
            ["segmentos"]["items"]["properties"]
            ["clips"]["items"]
        )

        campos = {
            "concepto_central",
            "criterios_obligatorios",
            "elementos_prohibidos",
            "continuidad_id",
            "consultas_alternativas",
        }

        propiedades = set(
            esquema_clip["properties"]
        )
        requeridos = set(
            esquema_clip["required"]
        )

        self.assertTrue(
            campos.issubset(propiedades)
        )
        self.assertTrue(
            campos.issubset(requeridos)
        )


    def test_rechaza_video_pexels_con_tags_copiados(
        self,
    ) -> None:
        recolector = RecolectorRecursos.__new__(
            RecolectorRecursos
        )

        consulta = (
            "ai researchers analyzing "
            "neural network graphs monitors"
        )

        evaluacion = (
            recolector._evaluar_metadata_video(
                resultado={
                    "_fuente": "pexels",
                    "pageURL": (
                        "https://www.pexels.com/video/"
                        "man-monitoring-the-stocks-7579951/"
                    ),
                    "tags": consulta,
                },
                consulta=consulta,
            )
        )

        self.assertFalse(
            evaluacion["aprobada"]
        )
        self.assertEqual(
            evaluacion["coincidencias"],
            [],
        )

    def test_acepta_video_con_titulo_autentico_coherente(
        self,
    ) -> None:
        recolector = RecolectorRecursos.__new__(
            RecolectorRecursos
        )

        evaluacion = (
            recolector._evaluar_metadata_video(
                resultado={
                    "_fuente": "pexels",
                    "pageURL": (
                        "https://www.pexels.com/video/"
                        "scientists-analyzing-neural-network-"
                        "in-laboratory-123456/"
                    ),
                    "tags": "consulta copiada",
                },
                consulta=(
                    "ai researchers analyzing "
                    "neural network graphs monitors"
                ),
            )
        )

        self.assertTrue(
            evaluacion["aprobada"]
        )
        self.assertIn(
            "neural",
            evaluacion["coincidencias"],
        )
        self.assertIn(
            "research",
            evaluacion["coincidencias"],
        )

    def test_requisito_visual_incluye_contrato_estricto(
        self,
    ) -> None:
        recolector = RecolectorRecursos.__new__(
            RecolectorRecursos
        )

        requisito = recolector._requisito_visual(
            {
                "concepto_central": (
                    "Comite cientifico sobre etica de IA"
                ),
                "descripcion": (
                    "Investigadores debaten en laboratorio"
                ),
                "criterios_obligatorios": [
                    "cientificos identificables",
                    "entorno de investigacion",
                ],
                "elementos_prohibidos": [
                    "reunion empresarial generica",
                ],
                "consultas_alternativas": [
                    "AI ethics scientific committee",
                ],
                "texto_narrado": (
                    "Los expertos estudian sus riesgos."
                ),
            }
        )

        self.assertIn(
            "CONCEPTO CENTRAL:",
            requisito,
        )
        self.assertIn(
            "CRITERIOS OBLIGATORIOS:",
            requisito,
        )
        self.assertIn(
            "ELEMENTOS PROHIBIDOS:",
            requisito,
        )
        self.assertIn(
            "reunion empresarial generica",
            requisito,
        )

    def test_consultas_alternativas_se_utilizan(
        self,
    ) -> None:
        recolector = RecolectorRecursos.__new__(
            RecolectorRecursos
        )

        consultas = recolector._consultas_clip(
            {
                "busqueda_en": (
                    "scientists AI ethics committee"
                ),
                "consultas_alternativas": [
                    "research laboratory ethics meeting",
                    "scientific panel artificial intelligence",
                ],
                "busqueda_es": (
                    "cientificos comite etica IA"
                ),
                "concepto_central": (
                    "comite cientifico"
                ),
                "descripcion": (
                    "investigadores debatiendo"
                ),
            }
        )

        self.assertIn(
            "research laboratory ethics meeting",
            consultas,
        )
        self.assertIn(
            "scientific panel artificial intelligence",
            consultas,
        )


if __name__ == "__main__":
    unittest.main()