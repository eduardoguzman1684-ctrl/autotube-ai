from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from autotube.visuals.final_visual_auditor import _assets_fingerprint
from autotube.visuals.visual_repair import (
    ReparadorVisual,
    VisualRepairError,
    _repair_clip,
)


def _image(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (320, 180), color=color).save(path, format="PNG")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _AlwaysApprovedAuditor:
    def __init__(self, output: Path) -> None:
        self.output = output
        self.calls = 0

    def audit(self, assets_path, channel_slug, limit=0):
        self.calls += 1
        path = Path(assets_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        elements = list(data["elementos"])
        if limit > 0:
            elements = elements[:limit]
        results = []
        for item in elements:
            asset_path = Path(item["archivo"])
            results.append(
                {
                    "id": (
                        f"s{int(item['segmento_indice']):02d}_"
                        f"c{int(item['clip_orden']):03d}"
                    ),
                    "approved": True,
                    "score": 100,
                    "reason": "Tarjeta factual aprobada.",
                    "description_seen": str(item.get("descripcion", "")),
                    "asset_sha256": _sha256(asset_path),
                }
            )
        report_path = self.output / f"audit_{self.calls}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "channel_slug": channel_slug,
            "assets_fingerprint": _assets_fingerprint(path),
            "audited_assets": len(results),
            "status": "approved",
            "elements": results,
            "path": str(report_path),
        }
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return report


class EditorialFallbackV25Test(unittest.TestCase):
    def test_round_two_rotates_to_second_historical_query(self) -> None:
        clip = {
            "segmento_indice": 2,
            "clip_orden": 4,
            "tipo_recurso": "imagen_stock",
            "descripcion": "Fotografia real de John McCarthy en una pizarra.",
            "texto_narrado": "John McCarthy organizo el taller.",
            "criterios_obligatorios": [],
            "elementos_prohibidos": [],
            "consultas_alternativas": [],
        }

        repaired = _repair_clip(clip, round_number=2)

        self.assertEqual(
            repaired["busqueda_en"],
            "John McCarthy Stanford blackboard archive",
        )
        self.assertEqual(repaired["tipo_recurso"], "imagen_stock")

    def test_round_three_uses_factual_local_cards_for_four_hard_cases(self) -> None:
        cases = [
            (
                "Fotografia de investigadores fundadores en Dartmouth College en 1956.",
                "Dartmouth 1956",
            ),
            (
                "Fotografia real de John McCarthy trabajando en una pizarra.",
                "John McCarthy",
            ),
            (
                "Video de cientificos analizando diagramas de flujo en los anos 50.",
                "Describir la inteligencia",
            ),
            (
                "Documento original de la propuesta de Dartmouth de 1955.",
                "Propuesta fundacional",
            ),
        ]

        for description, expected_text in cases:
            with self.subTest(expected_text=expected_text):
                repaired = _repair_clip(
                    {
                        "segmento_indice": 1,
                        "clip_orden": 1,
                        "tipo_recurso": "imagen_stock",
                        "descripcion": description,
                        "texto_narrado": description,
                        "criterios_obligatorios": [],
                        "elementos_prohibidos": [],
                        "consultas_alternativas": [],
                    },
                    round_number=3,
                )
                self.assertEqual(repaired["tipo_recurso"], "texto_animado")
                self.assertIn(expected_text, repaired["texto_pantalla"])
                self.assertIn("fallback_editorial", repaired)
                self.assertTrue(repaired["descripcion_editorial_original"])

    def test_repair_validates_continuation_range(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "assets.json"
            manifest.write_text("{}", encoding="utf-8")
            repairer = ReparadorVisual(
                data_dir=Path(temporary) / "data",
                output_dir=Path(temporary) / "output",
                auditor=_AlwaysApprovedAuditor(Path(temporary) / "audits"),
            )
            with self.assertRaises(VisualRepairError):
                repairer.repair(
                    assets_path=manifest,
                    channel_slug="nexon_ia",
                    attempts=3,
                    start_round=4,
                )

    def test_approved_fallback_contract_is_persisted_in_main_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "wrong.png"
            _image(original, (30, 30, 30))
            element = {
                "segmento_indice": 2,
                "segmento_numero": 2,
                "segmento_titulo": "Fundadores",
                "clip_orden": 4,
                "tipo_recurso": "imagen_stock",
                "archivo": str(original),
                "estado": "descargado",
                "descripcion": "Fotografia real de John McCarthy en una pizarra.",
                "texto_narrado": "John McCarthy organizo el taller.",
                "criterios_obligatorios": [],
                "elementos_prohibidos": [],
                "consultas_alternativas": [],
            }
            manifest_path = root / "assets_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "channel_slug": "nexon_ia",
                        "titulo": "Historia de la IA",
                        "elementos": [element],
                    }
                ),
                encoding="utf-8",
            )
            audit_path = root / "rejected_audit.json"
            audit_path.write_text(
                json.dumps(
                    {
                        "channel_slug": "nexon_ia",
                        "assets_fingerprint": _assets_fingerprint(manifest_path),
                        "audited_assets": 1,
                        "status": "rejected",
                        "elements": [
                            {
                                "id": "s02_c004",
                                "approved": False,
                                "reason": "No aparece John McCarthy.",
                                "asset_sha256": _sha256(original),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            def builder(manifest, targets, round_number, round_dir, channel_slug):
                candidate = _repair_clip(targets[0], round_number)
                candidate_path = round_dir / "john_card.png"
                round_dir.mkdir(parents=True, exist_ok=True)
                _image(candidate_path, (20, 80, 140))
                candidate["archivo"] = str(candidate_path)
                candidate["estado"] = "generado_local"
                candidate["fuente"] = "generador_local"
                path = round_dir / "candidates.json"
                path.write_text(
                    json.dumps(
                        {
                            "channel_slug": channel_slug,
                            "elementos": [candidate],
                        }
                    ),
                    encoding="utf-8",
                )
                return path

            result = ReparadorVisual(
                data_dir=root / "data",
                output_dir=root / "output",
                auditor=_AlwaysApprovedAuditor(root / "audits"),
                candidate_builder=builder,
            ).repair(
                assets_path=manifest_path,
                channel_slug="nexon_ia",
                audit_path=audit_path,
                attempts=1,
                start_round=3,
            )

            updated = json.loads(manifest_path.read_text(encoding="utf-8"))
            repaired = updated["elementos"][0]
            self.assertEqual(result["status"], "approved")
            self.assertEqual(repaired["tipo_recurso"], "texto_animado")
            self.assertIn("Tarjeta documental", repaired["descripcion"])
            self.assertIn("fallback_editorial", repaired)


if __name__ == "__main__":
    unittest.main()
