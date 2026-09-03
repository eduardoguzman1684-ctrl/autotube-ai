from __future__ import annotations

import unittest
from pathlib import Path


class EditorialTransportV28Test(unittest.TestCase):
    def test_collector_preserves_all_editorial_fields(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "autotube"
            / "visuals"
            / "asset_collector.py"
        ).read_text(encoding="utf-8-sig")
        for field in (
            "estilo_tarjeta",
            "descripcion_editorial_original",
            "fallback_editorial",
        ):
            with self.subTest(field=field):
                self.assertEqual(source.count(f'"{field}": clip.get('), 1)

    def test_project_version_is_at_least_v2_8(self) -> None:
        pyproject = (
            Path(__file__).resolve().parents[1] / "pyproject.toml"
        ).read_text(encoding="utf-8-sig")
        self.assertRegex(pyproject, r'version = "0\.3\.(?:[89]|[1-9][0-9]+)"')


if __name__ == "__main__":
    unittest.main()
