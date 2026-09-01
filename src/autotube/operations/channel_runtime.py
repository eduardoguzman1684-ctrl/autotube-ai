from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autotube.content.channel_profiles import (
    DEFAULT_CHANNEL,
    normalize_channel_slug,
)


def pipeline_state_directory(project_root: Path) -> Path:
    """Devuelve la carpeta de estados independientes por canal."""
    return Path(project_root).resolve() / "data" / "pipeline_states"


def pipeline_state_path(
    project_root: Path,
    channel_slug: str | None,
) -> Path:
    """Resuelve el estado que pertenece exclusivamente a un canal."""
    slug = normalize_channel_slug(channel_slug)
    return pipeline_state_directory(project_root) / f"{slug}.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def migrate_legacy_pipeline_state(
    project_root: Path,
) -> dict[str, Any]:
    """Copia el estado global antiguo al canal indicado sin eliminarlo.

    La migracion nunca sobrescribe un estado multicanal ya existente. Los
    estados antiguos sin ``parametros.canal`` pertenecen al canal historico
    predeterminado, NEXON IA.
    """
    root = Path(project_root).resolve()
    legacy_path = root / "data" / "pipeline_state.json"
    legacy = _read_json(legacy_path)

    result: dict[str, Any] = {
        "legacy": str(legacy_path),
        "found": bool(legacy),
        "migrated": False,
        "channel": "",
        "destination": "",
        "reason": "",
    }

    if not legacy:
        result["reason"] = "No existe un estado global valido."
        return result

    parameters = legacy.get("parametros", {})
    raw_channel = (
        parameters.get("canal", DEFAULT_CHANNEL)
        if isinstance(parameters, dict)
        else DEFAULT_CHANNEL
    )

    try:
        channel = normalize_channel_slug(str(raw_channel))
    except ValueError:
        result["reason"] = (
            "El estado global indica un canal desconocido; se conserva sin "
            "modificar."
        )
        return result

    destination = pipeline_state_path(root, channel)
    result["channel"] = channel
    result["destination"] = str(destination)

    if destination.exists():
        result["reason"] = "El canal ya tiene un estado independiente."
        return result

    _write_json_atomic(destination, legacy)
    result["migrated"] = True
    result["reason"] = "Estado global copiado de forma no destructiva."
    return result


def newest_pipeline_state(project_root: Path) -> Path:
    """Elige el estado de canal mas reciente para vistas agregadas."""
    root = Path(project_root).resolve()
    candidates = [
        path
        for path in pipeline_state_directory(root).glob("*.json")
        if path.is_file()
    ]

    legacy = root / "data" / "pipeline_state.json"
    if legacy.is_file():
        candidates.append(legacy)

    if not candidates:
        return pipeline_state_path(root, DEFAULT_CHANNEL)

    return max(candidates, key=lambda path: path.stat().st_mtime)


def incomplete_other_channel_states(
    project_root: Path,
    channel_slug: str | None,
) -> list[dict[str, str]]:
    """Detecta otra produccion pausada que aun usa archivos compartidos."""
    root = Path(project_root).resolve()
    target = normalize_channel_slug(channel_slug)
    migrate_legacy_pipeline_state(root)
    pending: list[dict[str, str]] = []

    for path in sorted(pipeline_state_directory(root).glob("*.json")):
        if not path.is_file() or path.stem == target:
            continue

        data = _read_json(path)
        if not data or bool(data.get("completado", False)):
            continue

        completed_steps = data.get("pasos_completados", [])
        has_progress = bool(
            data.get("ultimo_error", "")
            or data.get("paso_actual", "")
            or (
                isinstance(completed_steps, list)
                and completed_steps
            )
        )

        if has_progress:
            pending.append(
                {
                    "canal": path.stem,
                    "archivo": str(path),
                    "ultimo_error": str(data.get("ultimo_error", "")),
                }
            )

    return pending
