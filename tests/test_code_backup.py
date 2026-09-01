from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from autotube.operations.code_backup import (
    CodeBackupError,
    create_code_backup,
    inspect_repository,
)


class CodeBackupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self._git("init", "-b", "main")
        self._git("config", "user.email", "test@autotube.local")
        self._git("config", "user.name", "AutoTube Test")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )

    def _commit_base(self) -> None:
        (self.root / "src").mkdir(exist_ok=True)
        (self.root / "src" / "app.py").write_text(
            "print('autotube')\n",
            encoding="utf-8",
        )
        (self.root / ".env.example").write_text(
            "API_KEY=coloca_tu_clave\n",
            encoding="utf-8",
        )
        self._git("add", "src/app.py", ".env.example")
        self._git("commit", "-m", "base")

    def test_archive_contains_only_tracked_commit_files(self) -> None:
        self._commit_base()
        (self.root / ".env").write_text("API_KEY=secreto\n", encoding="utf-8")
        (self.root / "token.json").write_text("{}", encoding="utf-8")

        plan = inspect_repository(self.root, version="prueba-v1")
        result = create_code_backup(plan)

        with zipfile.ZipFile(result["archive_path"]) as archive:
            names = set(archive.namelist())

        self.assertIn("autotube-ai/src/app.py", names)
        self.assertIn("autotube-ai/.env.example", names)
        self.assertNotIn("autotube-ai/.env", names)
        self.assertNotIn("autotube-ai/token.json", names)

        manifest = json.loads(
            Path(result["manifest_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "prueba-v1")
        self.assertEqual(manifest["tracked_file_count"], 2)
        self.assertEqual(len(manifest["archive_sha256"]), 64)
        self.assertFalse(manifest["security"]["untracked_files_included"])

    def test_blocks_tracked_credentials(self) -> None:
        self._commit_base()
        token = self.root / "config" / "google_drive" / "token.json"
        token.parent.mkdir(parents=True)
        token.write_text("{}", encoding="utf-8")
        self._git("add", "config/google_drive/token.json")
        self._git("commit", "-m", "token inseguro")

        with self.assertRaises(CodeBackupError) as context:
            inspect_repository(self.root, version="prueba-v2")

        self.assertIn("BLOQUEO DE SEGURIDAD", str(context.exception))

    def test_blocks_uncommitted_tracked_changes(self) -> None:
        self._commit_base()
        (self.root / "src" / "app.py").write_text(
            "print('cambio pendiente')\n",
            encoding="utf-8",
        )

        with self.assertRaises(CodeBackupError) as context:
            inspect_repository(self.root, version="prueba-v3")

        self.assertIn("cambios controlados sin guardar", str(context.exception))

    def test_uses_exact_tag_as_default_version(self) -> None:
        self._commit_base()
        self._git("tag", "codigo-v1")

        plan = inspect_repository(self.root)

        self.assertEqual(plan["version"], "codigo-v1")


if __name__ == "__main__":
    unittest.main()
