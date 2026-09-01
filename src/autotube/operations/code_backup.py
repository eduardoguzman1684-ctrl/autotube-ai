from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


class CodeBackupError(RuntimeError):
    """Impide crear respaldos ambiguos o que puedan contener secretos."""


PRIVATE_SUFFIXES = {
    ".key",
    ".pem",
    ".p12",
    ".pfx",
}


def _git(
    project_root: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _safe_version(value: str) -> str:
    version = value.strip()
    if not version:
        raise CodeBackupError("La version del respaldo no puede estar vacia.")

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", version):
        raise CodeBackupError(
            "La version solo puede contener letras, numeros, punto, guion "
            "y guion bajo (maximo 80 caracteres)."
        )

    return version


def _is_sensitive_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]

    if name == ".env.example":
        return False

    if name == ".env" or name.startswith(".env."):
        return True

    if Path(name).suffix in PRIVATE_SUFFIXES:
        return True

    sensitive_names = {
        "token.json",
        "analytics_token.json",
        "client_secret.json",
        "credentials.json",
        "service_account.json",
    }
    if name in sensitive_names:
        return True

    if normalized.startswith("secrets/"):
        return True

    if normalized.startswith("config/") and any(
        marker in name
        for marker in ("token", "secret", "credential", "service_account")
    ):
        return True

    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_repository(
    project_root: Path,
    version: str | None = None,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()

    try:
        repository_root = Path(
            _git(root, "rev-parse", "--show-toplevel").stdout.strip()
        ).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        raise CodeBackupError(
            f"No se encontro un repositorio Git valido en {root}."
        ) from error

    if repository_root != root:
        raise CodeBackupError(
            "El respaldo debe ejecutarse desde la raiz del repositorio: "
            f"{repository_root}"
        )

    dirty = _git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
    ).stdout.strip()
    if dirty:
        raise CodeBackupError(
            "Hay cambios controlados sin guardar. Ejecuta pruebas y crea el "
            "commit antes del respaldo de codigo."
        )

    commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    short_commit = _git(root, "rev-parse", "--short=7", "HEAD").stdout.strip()
    branch_result = _git(
        root,
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
        check=False,
    )
    branch = branch_result.stdout.strip() or "detached"
    tags = sorted(
        tag
        for tag in _git(root, "tag", "--points-at", "HEAD").stdout.splitlines()
        if tag.strip()
    )

    selected_version = version
    if selected_version is None:
        selected_version = tags[0] if tags else f"commit-{short_commit}"
    selected_version = _safe_version(selected_version)

    tracked_output = _git(
        root,
        "ls-tree",
        "-r",
        "--name-only",
        "-z",
        "HEAD",
    ).stdout
    tracked_files = sorted(path for path in tracked_output.split("\0") if path)
    sensitive_files = [path for path in tracked_files if _is_sensitive_path(path)]

    if sensitive_files:
        formatted = "\n".join(f"- {path}" for path in sensitive_files)
        raise CodeBackupError(
            "BLOQUEO DE SEGURIDAD: el commit contiene archivos sensibles:\n"
            f"{formatted}\n"
            "Eliminalos del control de Git antes de crear el respaldo."
        )

    upstream_result = _git(
        root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
        check=False,
    )

    return {
        "project_root": root,
        "commit": commit,
        "short_commit": short_commit,
        "branch": branch,
        "upstream": upstream_result.stdout.strip(),
        "tags": tags,
        "version": selected_version,
        "tracked_files": tracked_files,
        "tracked_file_count": len(tracked_files),
    }


def create_code_backup(
    plan: dict[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(plan["project_root"]).resolve()
    destination = (
        output_dir.expanduser().resolve()
        if output_dir is not None
        else root / "output" / "code_backups"
    )
    destination.mkdir(parents=True, exist_ok=True)

    base_name = (
        f"autotube-ai_{plan['version']}_{plan['short_commit']}"
    )
    archive_path = destination / f"{base_name}.zip"
    manifest_path = destination / f"{base_name}.manifest.json"

    temporary_archive = archive_path.with_suffix(".zip.part")
    temporary_archive.unlink(missing_ok=True)

    try:
        _git(
            root,
            "archive",
            "--format=zip",
            "--prefix=autotube-ai/",
            f"--output={temporary_archive}",
            str(plan["commit"]),
        )
        temporary_archive.replace(archive_path)
    finally:
        temporary_archive.unlink(missing_ok=True)

    archive_sha256 = _sha256(archive_path)
    manifest = {
        "schema_version": 1,
        "product": "AutoTube AI",
        "backup_type": "git_commit_source",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "version": plan["version"],
        "commit": plan["commit"],
        "short_commit": plan["short_commit"],
        "branch": plan["branch"],
        "upstream": plan["upstream"],
        "tags": plan["tags"],
        "archive": archive_path.name,
        "archive_size_bytes": archive_path.stat().st_size,
        "archive_sha256": archive_sha256,
        "tracked_file_count": plan["tracked_file_count"],
        "tracked_files": plan["tracked_files"],
        "security": {
            "source": "git archive del commit exacto",
            "untracked_files_included": False,
            "tracked_sensitive_paths_detected": False,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        **plan,
        "archive_path": archive_path,
        "manifest_path": manifest_path,
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_path.stat().st_size,
    }
