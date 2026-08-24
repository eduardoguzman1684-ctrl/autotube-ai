from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from autotube.operations.dashboard import CentroControlAutoTube


class CentroControlAutoTubeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.root = Path(self.temporal.name)
        self.dashboard = CentroControlAutoTube(
            project_root=self.root,
        )

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def test_json_inexistente_o_invalido_devuelve_objeto_vacio(
        self,
    ) -> None:
        inexistente = self.root / "no_existe.json"

        self.assertEqual(
            self.dashboard._leer_json(inexistente),
            {},
        )

        invalido = self.root / "invalido.json"
        invalido.write_text(
            "{contenido roto",
            encoding="utf-8",
        )

        self.assertEqual(
            self.dashboard._leer_json(invalido),
            {},
        )

    def test_recopilar_entrega_estructura_completa(
        self,
    ) -> None:
        datos = self.dashboard.recopilar()

        claves = {
            "version",
            "generado_en",
            "estado_general",
            "pipeline",
            "produccion",
            "calidad",
            "publicacion",
            "analytics",
            "experimento",
            "almacenamiento",
            "logs",
            "alertas",
        }

        self.assertEqual(
            set(datos),
            claves,
        )
        self.assertIn(
            datos["estado_general"],
            {
                "operativo",
                "atencion",
                "critico",
            },
        )
        self.assertIsInstance(
            datos["alertas"],
            list,
        )
        self.assertTrue(
            datos["alertas"],
        )

    def test_guardar_crea_json_actual_historico_y_html(
        self,
    ) -> None:
        datos = self.dashboard.recopilar()
        rutas = self.dashboard.guardar(datos)

        self.assertTrue(
            rutas["historico"].is_file(),
        )
        self.assertTrue(
            rutas["actual"].is_file(),
        )
        self.assertTrue(
            rutas["html"].is_file(),
        )

        guardado = json.loads(
            rutas["actual"].read_text(
                encoding="utf-8",
            )
        )

        self.assertEqual(
            guardado["estado_general"],
            datos["estado_general"],
        )

        html = rutas["html"].read_text(
            encoding="utf-8",
        )

        self.assertIn(
            "Centro de Control AutoTube AI",
            html,
        )
        self.assertIn(
            "<!doctype html>",
            html,
        )

    def test_html_escapa_contenido_no_confiable(
        self,
    ) -> None:
        datos = self.dashboard.recopilar()
        datos["produccion"]["titulo"] = (
            "<script>alert('prueba')</script>"
        )

        html = self.dashboard._crear_html(
            datos
        )

        self.assertNotIn(
            "<script>alert('prueba')</script>",
            html,
        )
        self.assertIn(
            "&lt;script&gt;",
            html,
        )

    def test_generar_devuelve_datos_y_rutas(
        self,
    ) -> None:
        salida = io.StringIO()

        with contextlib.redirect_stdout(salida):
            resultado = self.dashboard.generar(
                abrir=False,
            )

        self.assertIn(
            "datos",
            resultado,
        )
        self.assertIn(
            "rutas",
            resultado,
        )
        self.assertTrue(
            resultado["rutas"]["html"].is_file(),
        )
        self.assertIn(
            "CENTRO DE CONTROL AUTOTUBE AI",
            salida.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
