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

    def test_html_incluye_actualizacion_automatica(
        self,
    ) -> None:
        datos = self.dashboard.recopilar()
        datos[
            "actualizacion_automatica_segundos"
        ] = 30

        html = self.dashboard._crear_html(
            datos
        )

        self.assertIn(
            'http-equiv="refresh" content="30"',
            html,
        )

    def test_publicado_limpiado_no_es_error_critico(
        self,
    ) -> None:
        video = (
            self.root
            / "output"
            / "videos"
            / "render_prueba"
            / "video_final_subtitulado_musica.mp4"
        )

        calidad = {
            "estado": "aprobado",
            "video": {
                "archivo": str(video),
                "duracion_segundos": 900,
            },
            "metadata": {
                "titulo": "Documental de prueba",
            },
        }

        publicacion = {
            "elementos": [
                {
                    "estado": "publicado",
                    "tipo": "documental",
                    "archivo": str(video),
                    "titulo": "Documental de prueba",
                    "video_id": "abc123",
                    "sha256": "hash-verificado",
                    "url": "https://youtu.be/abc123",
                }
            ],
            "estados": {
                "publicado": 1,
            },
        }

        pipeline = {
            "completado": True,
            "cantidad_completados": 11,
            "progreso_porcentaje": 100,
            "ultimo_error": "",
        }

        produccion = self.dashboard._produccion(
            calidad,
            publicacion=publicacion,
            pipeline=pipeline,
        )

        self.assertFalse(
            produccion["video_existe"]
        )
        self.assertTrue(
            produccion["publicado"]
        )
        self.assertEqual(
            produccion["estado"],
            "publicado_sin_copia_local",
        )

        alertas = self.dashboard._alertas(
            pipeline=pipeline,
            calidad=calidad,
            publicacion=publicacion,
            almacenamiento={
                "libre_porcentaje": 20,
                "libre_bytes": 20 * 1024**3,
            },
            produccion=produccion,
        )

        self.assertFalse(
            any(
                alerta["nivel"] == "critica"
                and "video final"
                in alerta["mensaje"].lower()
                for alerta in alertas
            )
        )

    def test_logs_separa_error_activo_del_historico(
        self,
    ) -> None:
        logs_dir = self.root / "logs"
        logs_dir.mkdir(
            parents=True,
        )

        (
            logs_dir
            / "autotube.log"
        ).write_text(
            (
                "2026-01-01 | ERROR | "
                "autotube | fallo anterior\n"
            ),
            encoding="utf-8",
        )

        logs = self.dashboard._logs(
            pipeline={
                "ultimo_error": "",
            }
        )

        self.assertEqual(
            logs["errores_historicos"],
            1,
        )
        self.assertEqual(
            logs["errores_activos"],
            0,
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
