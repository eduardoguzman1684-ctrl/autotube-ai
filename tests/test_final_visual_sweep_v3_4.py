from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autotube.visuals.final_visual_auditor import (
    _assets_fingerprint,
    _difference_hash,
    _hamming,
)
from autotube.visuals.local_asset_generator import generar_texto_animado
from autotube.visuals.visual_repair import (
    FINAL_FACTUAL_CONTRACTS,
    ReparadorVisual,
    VisualRepairError,
    _repair_clip,
)
from tests.test_visual_repair_v2_3 import (
    _FakeAuditor,
    _asset,
    _builder_factory,
    _image,
)


FINAL_CASES = [
    (9, 1, "Fotografía real de archivo de Frank Rosenblatt junto al Perceptrón Mark I."),
    (9, 2, "Diagrama técnico de una red neuronal artificial con capas interconectadas."),
    (9, 4, "Fotografía de un tablero tradicional del juego de Go con piedras negras y blancas."),
    (9, 5, "Video real de un centro de datos moderno con servidores operativos."),
    (10, 1, "Video real de una oficina corporativa tecnológica con profesionales trabajando."),
    (11, 1, "Video real de un panel de debate sobre regulaciones tecnológicas."),
    (11, 4, "Video real de analistas de ciberseguridad monitoreando protección de datos."),
    (11, 5, "Fotografía real de un laboratorio de ciencia cognitiva y cognición artificial."),
    (12, 5, "Video de una comunidad diversa trabajando por un futuro tecnológico sostenible."),
]


def _element(segment: int, clip: int, description: str) -> dict:
    return {
        "segmento_indice": segment,
        "clip_orden": clip,
        "segmento_titulo": "Historia de la inteligencia artificial",
        "tipo_recurso": "imagen_stock",
        "descripcion": description,
        "descripcion_editorial_original": "",
        "texto_narrado": description,
        "estado": "descargado",
        "archivo": "recurso_rechazado.jpg",
    }


class FinalVisualSweepV34Test(unittest.TestCase):
    def test_round_three_has_exact_contract_for_all_nine_ids(self) -> None:
        styles = set()
        for segment, clip, description in FINAL_CASES:
            event_id = f"s{segment:02d}_c{clip:03d}"
            expected = FINAL_FACTUAL_CONTRACTS[event_id]
            repaired = _repair_clip(
                _element(segment, clip, description),
                round_number=3,
            )
            self.assertEqual(repaired["tipo_recurso"], "texto_animado")
            self.assertEqual(repaired["texto_pantalla"], expected["screen"])
            self.assertEqual(repaired["estilo_tarjeta"], expected["style"])
            styles.add(repaired["estilo_tarjeta"])
        self.assertEqual(len(styles), len(FINAL_CASES))

    def test_round_two_does_not_activate_final_cards(self) -> None:
        for segment, clip, description in FINAL_CASES:
            repaired = _repair_clip(
                _element(segment, clip, description),
                round_number=2,
            )
            self.assertNotEqual(repaired["tipo_recurso"], "texto_animado")

    def test_final_cards_are_not_adjacent_perceptual_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hashes = []
            for index, (segment, clip, description) in enumerate(FINAL_CASES):
                repaired = _repair_clip(
                    _element(segment, clip, description),
                    round_number=3,
                )
                path = Path(temporary) / f"card_{index}.png"
                generar_texto_animado(repaired).save(path, format="PNG")
                hashes.append(_difference_hash(path))
            distances = [
                _hamming(first, second)
                for first, second in zip(hashes, hashes[1:])
            ]
            self.assertTrue(
                all(distance > 2 for distance in distances),
                msg=f"Distancias perceptuales: {distances}",
            )

    def test_explicit_target_repairs_item_missing_from_partial_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "approved.jpg"
            second = root / "rejected.jpg"
            _image(first, 1)
            _image(second, 2)
            manifest_path = root / "assets_manifest.json"
            manifest = {
                "channel_slug": "nexon_ia",
                "titulo": "Historia de la IA",
                "resumen": {},
                "elementos": [_asset(first, 1), _asset(second, 2)],
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            audit_path = root / "partial_audit.json"
            audit_path.write_text(
                json.dumps(
                    {
                        "channel_slug": "nexon_ia",
                        "assets_fingerprint": _assets_fingerprint(manifest_path),
                        "audited_assets": 1,
                        "status": "approved",
                        "elements": [
                            {
                                "id": "s01_c001",
                                "approved": True,
                                "reason": "Correcto",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = ReparadorVisual(
                data_dir=root / "data",
                output_dir=root / "output",
                auditor=_FakeAuditor(root / "audits"),
                candidate_builder=_builder_factory(),
            ).repair(
                assets_path=manifest_path,
                channel_slug="nexon_ia",
                audit_path=audit_path,
                attempts=1,
                target_ids=["s01_c002"],
            )
            self.assertEqual(result["rejected_initially"], 1)
            self.assertEqual(result["repaired_assets"], 1)
            self.assertEqual(result["pending_assets"], 0)
            self.assertEqual(result["status"], "approved")

    def test_explicit_target_rejects_unknown_manifest_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "approved.jpg"
            _image(first, 1)
            manifest_path = root / "assets_manifest.json"
            manifest = {
                "channel_slug": "nexon_ia",
                "titulo": "Historia de la IA",
                "elementos": [_asset(first, 1)],
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            audit_path = root / "partial_audit.json"
            audit_path.write_text(
                json.dumps(
                    {
                        "channel_slug": "nexon_ia",
                        "assets_fingerprint": _assets_fingerprint(manifest_path),
                        "audited_assets": 1,
                        "status": "approved",
                        "elements": [
                            {"id": "s01_c001", "approved": True}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(VisualRepairError):
                ReparadorVisual(
                    data_dir=root / "data",
                    output_dir=root / "output",
                    auditor=_FakeAuditor(root / "audits"),
                    candidate_builder=_builder_factory(),
                ).repair(
                    assets_path=manifest_path,
                    channel_slug="nexon_ia",
                    audit_path=audit_path,
                    attempts=1,
                    target_ids=["s99_c999"],
                )


if __name__ == "__main__":
    unittest.main()
