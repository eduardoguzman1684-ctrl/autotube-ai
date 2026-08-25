from __future__ import annotations

import unittest

from autotube.audio.voice_generator import (
    FILTRO_MASTER_VOZ,
    PERFIL_VOZ_VERSION,
    TONO_PREDETERMINADO,
    VELOCIDAD_PREDETERMINADA,
    crear_huella_audio,
    normalizar_texto_voz,
)


class CalidadVozTest(unittest.TestCase):
    def test_perfil_documental_mas_natural(
        self,
    ) -> None:
        self.assertEqual(
            VELOCIDAD_PREDETERMINADA,
            "-2%",
        )
        self.assertEqual(
            TONO_PREDETERMINADO,
            "-1Hz",
        )
        self.assertEqual(
            PERFIL_VOZ_VERSION,
            "documental_profesional_v1",
        )

    def test_pronuncia_terminos_tecnicos(
        self,
    ) -> None:
        texto = normalizar_texto_voz(
            "La IA, la AGI, una GPU, una CPU "
            "y una API impulsan ChatGPT."
        )

        self.assertIn(
            "inteligencia artificial",
            texto,
        )
        self.assertIn(
            "inteligencia artificial general",
            texto,
        )
        self.assertIn(
            "ge pe u",
            texto,
        )
        self.assertIn(
            "ce pe u",
            texto,
        )
        self.assertIn(
            "a pe i",
            texto,
        )
        self.assertIn(
            "Chat ge pe te",
            texto,
        )

    def test_no_duplica_modelo_llm(
        self,
    ) -> None:
        texto = normalizar_texto_voz(
            "Los modelos LLM analizan datos."
        )

        self.assertIn(
            "modelos ele ele eme",
            texto,
        )
        self.assertNotIn(
            "modelos modelo",
            texto,
        )

    def test_huella_cambia_con_configuracion(
        self,
    ) -> None:
        base = crear_huella_audio(
            texto="Narracion de prueba.",
            voz="es-MX-JorgeNeural",
            velocidad="-2%",
            tono="-1Hz",
            volumen="+0%",
        )

        igual = crear_huella_audio(
            texto="Narracion de prueba.",
            voz="es-MX-JorgeNeural",
            velocidad="-2%",
            tono="-1Hz",
            volumen="+0%",
        )

        diferente = crear_huella_audio(
            texto="Narracion de prueba.",
            voz="es-MX-JorgeNeural",
            velocidad="-3%",
            tono="-1Hz",
            volumen="+0%",
        )

        self.assertEqual(
            base,
            igual,
        )
        self.assertNotEqual(
            base,
            diferente,
        )

    def test_masterizacion_define_objetivos(
        self,
    ) -> None:
        self.assertIn(
            "highpass=f=70",
            FILTRO_MASTER_VOZ,
        )
        self.assertIn(
            "acompressor=",
            FILTRO_MASTER_VOZ,
        )
        self.assertIn(
            "loudnorm=I=-16",
            FILTRO_MASTER_VOZ,
        )
        self.assertIn(
            "TP=-1.5",
            FILTRO_MASTER_VOZ,
        )


if __name__ == "__main__":
    unittest.main()