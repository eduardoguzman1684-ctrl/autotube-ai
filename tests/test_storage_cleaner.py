from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from autotube.operations.storage_cleaner import (
    LimpiadorAlmacenamiento,
)


class LimpiadorAlmacenamientoTest(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temporal.name
        )

        self.videos = (
            self.root
            / "output"
            / "videos"
        )

        self.videos.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.antiguo = (
            self.videos
            / "render_20260101_080000"
        )

        self.protegido = (
            self.videos
            / "render_20260102_080000"
        )

        self.reciente = (
            self.videos
            / "render_20260103_080000"
        )

        for carpeta in (
            self.antiguo,
            self.protegido,
            self.reciente,
        ):
            carpeta.mkdir(
                parents=True,
                exist_ok=True,
            )

            (
                carpeta
                / "video_final.mp4"
            ).write_bytes(
                b"intermedio" * 100
            )

            (
                carpeta
                / "video_final_subtitulado_musica.mp4"
            ).write_bytes(
                b"final" * 100
            )

        preview = (
            self.videos
            / "render_20260101_090000"
        )

        preview.mkdir(
            parents=True,
            exist_ok=True,
        )

        (
            preview
            / "preview.mp4"
        ).write_bytes(
            b"preview"
        )

        pruebas = (
            self.root
            / "output"
            / "hardware_tests"
        )

        pruebas.mkdir(
            parents=True,
            exist_ok=True,
        )

        (
            pruebas
            / "benchmark.mp4"
        ).write_bytes(
            b"benchmark"
        )

        hace_dos_dias = (
            time.time()
            - 48 * 3600
        )

        for carpeta in (
            self.antiguo,
            self.protegido,
            preview,
        ):
            os.utime(
                carpeta,
                (
                    hace_dos_dias,
                    hace_dos_dias,
                ),
            )

        cola = (
            self.root
            / "data"
            / "publish"
            / "upload_queue.json"
        )

        cola.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        cola.write_text(
            json.dumps(
                {
                    "elementos": [
                        {
                            "archivo": str(
                                self.protegido
                                / "video_final.mp4"
                            ),
                            "estado": "publicado",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        self.limpiador = (
            LimpiadorAlmacenamiento(
                project_root=self.root,
            )
        )

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def test_auditoria_protege_actual_y_referenciado(
        self,
    ) -> None:
        informe = (
            self.limpiador.auditar()
        )

        rutas = {
            Path(
                candidato["ruta"]
            )
            for candidato in informe[
                "candidatos"
            ]
        }

        self.assertIn(
            (
                self.antiguo
                / "video_final.mp4"
            ).resolve(),
            rutas,
        )

        self.assertIn(
            (
                self.root
                / "output"
                / "hardware_tests"
            ).resolve(),
            rutas,
        )

        self.assertNotIn(
            (
                self.reciente
                / "video_final.mp4"
            ).resolve(),
            rutas,
        )

        self.assertNotIn(
            (
                self.protegido
                / "video_final.mp4"
            ).resolve(),
            rutas,
        )

    def test_simulacion_no_elimina(
        self,
    ) -> None:
        resultado = (
            self.limpiador.ejecutar(
                confirmar=False,
            )
        )

        self.assertTrue(
            (
                self.antiguo
                / "video_final.mp4"
            ).is_file()
        )

        self.assertEqual(
            resultado["informe"]["estado"],
            "auditado",
        )

        self.assertTrue(
            resultado["rutas"][
                "historico"
            ].is_file()
        )

    def test_confirmacion_elimina_solo_candidatos(
        self,
    ) -> None:
        resultado = (
            self.limpiador.ejecutar(
                confirmar=True,
            )
        )

        self.assertFalse(
            (
                self.antiguo
                / "video_final.mp4"
            ).exists()
        )

        self.assertTrue(
            (
                self.antiguo
                / "video_final_subtitulado_musica.mp4"
            ).is_file()
        )

        self.assertTrue(
            (
                self.reciente
                / "video_final.mp4"
            ).is_file()
        )

        self.assertTrue(
            (
                self.protegido
                / "video_final.mp4"
            ).is_file()
        )

        self.assertEqual(
            resultado["informe"]["errores"],
            [],
        )

        self.assertGreater(
            resultado["informe"][
                "eliminados"
            ],
            0,
        )

    def test_publicado_verificado_se_elimina_y_actualiza_cola(
        self,
    ) -> None:
        carpeta = (
            self.root
            / "output"
            / "shorts"
            / "shorts_prueba"
        )

        carpeta.mkdir(
            parents=True,
            exist_ok=True,
        )

        publicado = (
            carpeta
            / "short_01.mp4"
        )

        publicado.write_bytes(
            b"short-publicado-verificado"
        )

        digest = hashlib.sha256(
            publicado.read_bytes()
        ).hexdigest()

        cola_path = (
            self.root
            / "data"
            / "publish"
            / "upload_queue.json"
        )

        cola = json.loads(
            cola_path.read_text(
                encoding="utf-8"
            )
        )

        cola["elementos"].append(
            {
                "id": "short:prueba",
                "tipo": "short",
                "estado": "publicado",
                "video_id": "video_prueba_123",
                "archivo": str(
                    publicado
                ),
                "sha256": digest,
            }
        )

        cola_path.write_text(
            json.dumps(
                cola
            ),
            encoding="utf-8",
        )

        auditoria = self.limpiador.auditar(
            incluir_publicados=True,
        )

        candidatos = {
            Path(
                candidato["ruta"]
            ): candidato
            for candidato in auditoria[
                "candidatos"
            ]
        }

        self.assertIn(
            publicado.resolve(),
            candidatos,
        )

        self.assertEqual(
            candidatos[
                publicado.resolve()
            ]["tipo"],
            "publicado_verificado",
        )

        resultado = self.limpiador.ejecutar(
            confirmar=True,
            incluir_publicados=True,
        )

        self.assertFalse(
            publicado.exists()
        )

        cola_actualizada = json.loads(
            cola_path.read_text(
                encoding="utf-8"
            )
        )

        registro = next(
            elemento
            for elemento in cola_actualizada[
                "elementos"
            ]
            if elemento.get(
                "video_id"
            ) == "video_prueba_123"
        )

        self.assertFalse(
            registro[
                "archivo_local_disponible"
            ]
        )

        self.assertTrue(
            registro[
                "sha256_verificado_antes_de_eliminar"
            ]
        )

        self.assertEqual(
            resultado["informe"]["errores"],
            [],
        )


    def test_rechaza_rutas_fuera_de_output(
        self,
    ) -> None:
        exterior = (
            self.root
            / "archivo_importante.txt"
        )

        exterior.write_text(
            "protegido",
            encoding="utf-8",
        )

        self.assertFalse(
            self.limpiador._ruta_segura(
                exterior
            )
        )

        self.assertTrue(
            exterior.is_file()
        )


if __name__ == "__main__":
    unittest.main()
