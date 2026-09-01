from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from autotube.visuals.final_visual_auditor import _assets_fingerprint
from autotube.visuals.visual_repair import (
    ReparadorVisual,
    VisualRepairError,
    _repair_plan,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _image(path: Path, variant: int) -> None:
    image = Image.new("RGB", (320, 180), color=(10 + variant, 25, 45))
    drawing = ImageDraw.Draw(image)
    drawing.rectangle(
        (15 + variant * 5, 20, 120 + variant * 8, 160),
        fill=(230, 50 + variant * 15, 40),
    )
    drawing.text((145, 75), f"V{variant}", fill="white")
    image.save(path, format="JPEG", quality=95)


def _asset(path: Path, order: int) -> dict[str, object]:
    return {
        "segmento_indice": 1,
        "segmento_numero": 1,
        "segmento_titulo": "Historia",
        "clip_orden": order,
        "tipo_recurso": "imagen_stock",
        "archivo": str(path),
        "estado": "descargado",
        "descripcion": f"Documento historico exacto {order}",
        "concepto_central": f"Concepto {order}",
        "texto_narrado": f"Narracion {order}",
        "criterios_obligatorios": [f"Elemento real {order}"],
        "elementos_prohibidos": ["imagen generica"],
        "consultas_alternativas": [f"historical document {order}"],
    }


class _FakeAuditor:
    def __init__(self, output: Path, approve_candidates: bool = True) -> None:
        self.output = output
        self.approve_candidates = approve_candidates
        self.calls = 0

    def audit(self, assets_path, channel_slug, limit=0):
        self.calls += 1
        path = Path(assets_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        elements = list(data["elementos"])
        if limit > 0:
            elements = elements[:limit]
        candidate_call = path.name == "auditable_candidates.json"
        audited = []
        for element in elements:
            asset_path = Path(element["archivo"])
            approved = (
                self.approve_candidates
                if candidate_call
                else asset_path.name != "rejected.jpg"
            )
            event_id = (
                f"s{int(element['segmento_indice']):02d}_"
                f"c{int(element['clip_orden']):03d}"
            )
            audited.append(
                {
                    "id": event_id,
                    "approved": approved,
                    "score": 98 if approved else 10,
                    "reason": "Candidato exacto" if approved else "Candidato incorrecto",
                    "description_seen": "Contenido comprobado",
                    "asset_sha256": _sha256(asset_path),
                    "duplicate_of": "",
                }
            )
        report_path = self.output / f"fake_audit_{self.calls}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        status = "approved" if audited and all(x["approved"] for x in audited) else "rejected"
        report = {
            "version": "fake",
            "channel_slug": channel_slug,
            "assets_fingerprint": _assets_fingerprint(path),
            "audited_assets": len(audited),
            "approved_assets": sum(int(x["approved"]) for x in audited),
            "rejected_assets": sum(int(not x["approved"]) for x in audited),
            "status": status,
            "elements": audited,
            "path": str(report_path),
        }
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return report


def _builder_factory(candidate_variant: int = 3):
    def builder(manifest, targets, round_number, round_dir, channel_slug):
        round_dir.mkdir(parents=True, exist_ok=True)
        candidates = []
        for target in targets:
            candidate = copy.deepcopy(target)
            candidate_path = round_dir / (
                f"candidate_{target['segmento_indice']}_{target['clip_orden']}.jpg"
            )
            _image(candidate_path, candidate_variant + round_number)
            candidate["archivo"] = str(candidate_path)
            candidate["estado"] = "descargado"
            candidate["fuente"] = "fake_verified_source"
            candidates.append(candidate)
        manifest_path = round_dir / "candidate_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "channel_slug": channel_slug,
                    "titulo": manifest.get("titulo", ""),
                    "elementos": candidates,
                }
            ),
            encoding="utf-8",
        )
        return manifest_path

    return builder


class VisualRepairV23Test(unittest.TestCase):
    def test_target_plan_preserves_original_segment_and_clip_numbers(self) -> None:
        target = _asset(Path("unused.jpg"), 5)
        target["segmento_indice"] = 8
        target["segmento_numero"] = 8
        plan = _repair_plan(
            {"titulo": "Prueba"},
            [target],
            round_number=1,
        )
        segments = plan["plan_visual"]["segmentos"]
        self.assertEqual(len(segments), 8)
        self.assertEqual(segments[7]["numero"], 8)
        self.assertEqual(segments[7]["clips"][0]["orden"], 5)

    def _fixture(self, root: Path):
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
        audit = {
            "version": "final_visual_audit_v1",
            "channel_slug": "nexon_ia",
            "assets_fingerprint": _assets_fingerprint(manifest_path),
            "audited_assets": 2,
            "status": "rejected",
            "elements": [
                {
                    "id": "s01_c001",
                    "approved": True,
                    "asset_sha256": _sha256(first),
                    "reason": "Correcto",
                },
                {
                    "id": "s01_c002",
                    "approved": False,
                    "asset_sha256": _sha256(second),
                    "reason": "Visual generico",
                },
            ],
        }
        audit_path = root / "visual_audit.json"
        audit_path.write_text(json.dumps(audit), encoding="utf-8")
        return manifest_path, audit_path, first, second

    def test_repairs_only_rejected_asset_and_preserves_approved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, audit_path, approved, rejected = self._fixture(root)
            result = ReparadorVisual(
                data_dir=root / "data",
                output_dir=root / "output",
                auditor=_FakeAuditor(root / "audits"),
                candidate_builder=_builder_factory(),
            ).repair(
                assets_path=manifest_path,
                channel_slug="nexon_ia",
                audit_path=audit_path,
                attempts=2,
            )

            updated = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["elementos"][0]["archivo"], str(approved))
            self.assertNotEqual(updated["elementos"][1]["archivo"], str(rejected))
            self.assertTrue(Path(updated["elementos"][1]["archivo"]).is_file())
            self.assertEqual(result["repaired_assets"], 1)
            self.assertEqual(result["pending_assets"], 0)
            self.assertEqual(result["status"], "approved")
            self.assertTrue(Path(result["backup_manifest"]).is_file())

    def test_rejects_stale_audit_without_modifying_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, audit_path, _, _ = self._fixture(root)
            before = manifest_path.read_bytes()
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["elementos"][1]["descripcion"] = "Cambio posterior"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")

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
                )

            self.assertNotEqual(manifest_path.read_bytes(), before)
            self.assertEqual(
                json.loads(manifest_path.read_text(encoding="utf-8"))[
                    "elementos"
                ][1]["descripcion"],
                "Cambio posterior",
            )

    def test_does_not_merge_candidate_rejected_by_pixel_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, audit_path, _, rejected = self._fixture(root)
            result = ReparadorVisual(
                data_dir=root / "data",
                output_dir=root / "output",
                auditor=_FakeAuditor(root / "audits", approve_candidates=False),
                candidate_builder=_builder_factory(),
            ).repair(
                assets_path=manifest_path,
                channel_slug="nexon_ia",
                audit_path=audit_path,
                attempts=1,
            )

            updated = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["elementos"][1]["archivo"], str(rejected))
            self.assertEqual(result["repaired_assets"], 0)
            self.assertEqual(result["pending_assets"], 1)
            self.assertEqual(result["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
