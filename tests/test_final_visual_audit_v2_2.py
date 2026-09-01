from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from autotube.video.composer import CompositorVideo
from autotube.visuals.final_visual_auditor import (
    AuditorVisualFinal,
    FinalVisualAuditError,
    find_compatible_audit,
)


class _VerifierApproved:
    def seleccionar_lote(self, groups, sheet):
        return {
            str(group["id"]): {
                "seleccion": 1,
                "puntaje": 98,
                "aprobada": True,
                "cumple_concepto": True,
                "cumple_obligatorios": True,
                "viola_prohibidos": False,
                "descripcion": "Coincidencia directa comprobada.",
                "motivo": "Pixeles aprobados.",
            }
            for group in groups
        }


def _image(path: Path, variant: int) -> None:
    image = Image.new("RGB", (320, 180), color=(20, 30, 40))
    drawing = ImageDraw.Draw(image)
    if variant == 1:
        drawing.rectangle((20, 20, 130, 160), fill=(240, 210, 30))
    else:
        drawing.ellipse((160, 25, 300, 165), fill=(20, 220, 180))
    image.save(path, format="JPEG", quality=95)


def _asset(path: Path, order: int) -> dict[str, object]:
    return {
        "segmento_indice": 1,
        "clip_orden": order,
        "archivo": str(path),
        "estado": "descargado",
        "descripcion": f"Visual documental exacto {order}",
        "concepto_central": f"Concepto {order}",
        "texto_narrado": f"Narracion {order}",
        "criterios_obligatorios": [f"Elemento {order}"],
        "elementos_prohibidos": ["relleno generico"],
    }


class FinalVisualAuditV22Test(unittest.TestCase):
    def test_rejects_adjacent_duplicate_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "visual.jpg"
            _image(image, 1)
            manifest_path = root / "assets.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "titulo": "Prueba",
                        "elementos": [_asset(image, 1), _asset(image, 2)],
                    }
                ),
                encoding="utf-8",
            )

            report = AuditorVisualFinal(
                root / "output",
                verifier=_VerifierApproved(),
            ).audit(manifest_path, "nexon_ia")

            self.assertEqual(report["approved_assets"], 1)
            self.assertEqual(report["rejected_assets"], 1)
            self.assertEqual(report["status"], "rejected")
            self.assertEqual(report["elements"][1]["duplicate_of"], "s01_c001")

    def test_audit_is_bound_to_exact_asset_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "visual.jpg"
            _image(image, 1)
            manifest_path = root / "assets.json"
            manifest_path.write_text(
                json.dumps({"elementos": [_asset(image, 1)]}),
                encoding="utf-8",
            )
            output = root / "output"
            report = AuditorVisualFinal(
                output,
                verifier=_VerifierApproved(),
            ).audit(manifest_path, "nexon_ia")

            found, found_path = find_compatible_audit(
                output,
                manifest_path,
                required_assets=1,
                audit_path=Path(report["path"]),
            )
            self.assertEqual(found["status"], "approved")
            self.assertTrue(found_path.is_file())

            _image(image, 2)
            with self.assertRaises(FinalVisualAuditError):
                find_compatible_audit(
                    output,
                    manifest_path,
                    required_assets=1,
                    audit_path=Path(report["path"]),
                )

    def test_ken_burns_progress_spans_complete_clip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            compositor = CompositorVideo(Path(temporary))
            filter_value = compositor.filtro_imagen(
                ancho=1280,
                alto=720,
                fps=24,
                duracion=15.0,
                movimiento="zoom lento",
                identificador="clip-1",
            )

            self.assertIn("on/359", filter_value)
            self.assertIn("1+0.070", filter_value)
            self.assertNotIn("zoom+", filter_value)


if __name__ == "__main__":
    unittest.main()
