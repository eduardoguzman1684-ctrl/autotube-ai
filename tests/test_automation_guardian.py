from __future__ import annotations

import json
import os
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

from autotube.operations.guardian import (
    EjecucionEnCursoError,
    GuardianPipeline,
)
from autotube.operations.windows_scheduler import (
    ProgramadorWindows,
)


DiskUsage = namedtuple(
    "DiskUsage",
    [
        "total",
        "used",
        "free",
    ],
)


class GuardianPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temporal.name
        )

        ejecutables = [
            (
                self.root
                / ".venv"
                / "Scripts"
                / "autotube.exe"
            ),
            (
                self.root
                / ".venv"
                / "bin"
                / "autotube"
            ),
        ]

        for ejecutable in ejecutables:
            ejecutable.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            ejecutable.write_bytes(
                b"prueba"
            )

        self.guardian = GuardianPipeline(
            project_root=self.root,
        )

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def _guardar_estado(
        self,
        completado: bool,
        pasos: list[str],
        error: str = "",
    ) -> None:
        ruta = (
            self.root
            / "data"
            / "pipeline_state.json"
        )

        ruta.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        ruta.write_text(
            json.dumps(
                {
                    "completado": completado,
                    "pasos_completados": pasos,
                    "ultimo_error": error,
                }
            ),
            encoding="utf-8",
        )

    def test_reanuda_pipeline_incompleto(
        self,
    ) -> None:
        self._guardar_estado(
            completado=False,
            pasos=[
                "Generacion de ideas",
            ],
        )

        self.assertTrue(
            self.guardian.debe_reanudar()
        )

        comandos = (
            self.guardian.construir_comandos()
        )

        pipeline = next(
            item["comando"]
            for item in comandos
            if item["nombre"]
            == "Pipeline de produccion"
        )

        self.assertIn(
            "--reanudar",
            pipeline,
        )

    def test_pipeline_completado_inicia_uno_nuevo(
        self,
    ) -> None:
        self._guardar_estado(
            completado=True,
            pasos=[
                "Generacion de ideas",
            ],
        )

        self.assertFalse(
            self.guardian.debe_reanudar()
        )

        comandos = (
            self.guardian.construir_comandos()
        )

        pipeline = next(
            item["comando"]
            for item in comandos
            if item["nombre"]
            == "Pipeline de produccion"
        )

        self.assertNotIn(
            "--reanudar",
            pipeline,
        )

    def test_limpieza_verificada_ocurre_despues_del_pipeline(
        self,
    ) -> None:
        comandos = (
            self.guardian.construir_comandos(
                publicar=True,
                limpiar_publicados=True,
            )
        )

        self.assertEqual(
            comandos[-1]["nombre"],
            "Limpieza de publicaciones verificadas",
        )

        self.assertEqual(
            comandos[-1]["comando"][-3:],
            [
                "storage-clean",
                "--publicados",
                "--confirmar",
            ],
        )

        sin_publicar = (
            self.guardian.construir_comandos(
                publicar=False,
                limpiar_publicados=True,
            )
        )

        self.assertNotIn(
            "Limpieza de publicaciones verificadas",
            [
                item["nombre"]
                for item in sin_publicar
            ],
        )


    def test_bloqueo_impide_segunda_ejecucion(
        self,
    ) -> None:
        token = (
            self.guardian.adquirir_bloqueo()
        )

        try:
            estado = (
                self.guardian.estado_bloqueo()
            )

            self.assertTrue(
                estado["activo"]
            )
            self.assertEqual(
                estado["pid"],
                os.getpid(),
            )

            with self.assertRaises(
                EjecucionEnCursoError
            ):
                self.guardian.adquirir_bloqueo()

            self.assertFalse(
                self.guardian.liberar_bloqueo(
                    "token-incorrecto"
                )
            )
        finally:
            self.guardian.liberar_bloqueo(
                token
            )

        self.assertFalse(
            self.guardian.lock_path.exists()
        )

    def test_preflight_aprobado_con_recursos(
        self,
    ) -> None:
        veinte_gb = 20 * 1024 ** 3
        cien_gb = 100 * 1024 ** 3

        with (
            patch(
                "autotube.operations.guardian."
                "shutil.disk_usage",
                return_value=DiskUsage(
                    cien_gb,
                    cien_gb - veinte_gb,
                    veinte_gb,
                ),
            ),
            patch(
                "autotube.operations.guardian."
                "shutil.which",
                side_effect=lambda nombre: (
                    f"C:\\herramientas\\{nombre}.exe"
                ),
            ),
            patch(
                "autotube.operations.guardian."
                "socket.getaddrinfo",
                return_value=[
                    (
                        None,
                        None,
                        None,
                        None,
                        None,
                    )
                ],
            ),
        ):
            resultado = (
                self.guardian.preflight()
            )

        self.assertTrue(
            resultado["aprobado"]
        )
        self.assertEqual(
            resultado["errores"],
            [],
        )

    def test_simulacion_no_ejecuta_subprocesos(
        self,
    ) -> None:
        with patch(
            "autotube.operations.guardian."
            "subprocess.run"
        ) as ejecutar:
            resultado = self.guardian.ejecutar(
                dry_run=True,
            )

        ejecutar.assert_not_called()

        self.assertEqual(
            resultado["informe"]["estado"],
            "simulacion",
        )
        self.assertTrue(
            resultado["rutas"][
                "historico"
            ].is_file()
        )


class ProgramadorWindowsTest(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temporal.name
        )

        for ejecutable in (
            (
                self.root
                / ".venv"
                / "Scripts"
                / "autotube.exe"
            ),
            (
                self.root
                / ".venv"
                / "bin"
                / "autotube"
            ),
        ):
            ejecutable.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            ejecutable.write_bytes(
                b"prueba"
            )

        self.programador = ProgramadorWindows(
            project_root=self.root,
        )

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def test_valida_hora_y_dias(
        self,
    ) -> None:
        self.assertEqual(
            self.programador.validar_hora(
                "08:30"
            ),
            "08:30",
        )

        self.assertEqual(
            self.programador.normalizar_dias(
                "lunes, miércoles, viernes"
            ),
            [
                "MON",
                "WED",
                "FRI",
            ],
        )

        with self.assertRaises(
            ValueError
        ):
            self.programador.validar_hora(
                "25:90"
            )

        with self.assertRaises(
            ValueError
        ):
            self.programador.normalizar_dias(
                "dia-inventado"
            )

    def test_instalacion_sin_confirmar_es_simulacion(
        self,
    ) -> None:
        with patch(
            "autotube.operations."
            "windows_scheduler.subprocess.run"
        ) as ejecutar:
            resultado = (
                self.programador.instalar(
                    hora="09:15",
                    dias="martes,jueves",
                    confirmar=False,
                )
            )

        ejecutar.assert_not_called()

        self.assertFalse(
            resultado["instalado"]
        )
        self.assertFalse(
            resultado["confirmado"]
        )
        self.assertEqual(
            resultado["dias"],
            [
                "TUE",
                "THU",
            ],
        )
        self.assertIn(
            "WEEKLY",
            resultado["comando"],
        )

    def test_lanzador_usa_entorno_virtual(
        self,
    ) -> None:
        contenido = (
            self.programador.contenido_lanzador()
        )

        self.assertIn(
            "autotube",
            contenido.lower(),
        )
        self.assertIn(
            "guardian-run",
            contenido,
        )
        self.assertIn(
            "guardian_task.log",
            contenido,
        )


if __name__ == "__main__":
    unittest.main()
