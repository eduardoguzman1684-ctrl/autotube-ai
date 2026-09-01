from __future__ import annotations

import copy
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from autotube.visuals.final_visual_auditor import (
    AuditorVisualFinal,
    _assets_fingerprint,
)


REPAIR_VERSION = "visual_repair_v1"


class VisualRepairError(RuntimeError):
    """Detiene la reparacion cuando no puede conservarse la trazabilidad."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise VisualRepairError(f"No se pudo leer el JSON: {path}") from error
    if not isinstance(value, dict):
        raise VisualRepairError(f"El archivo no contiene un objeto JSON: {path}")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _event_id(element: dict[str, Any]) -> str:
    segment = int(element.get("segmento_indice", 0) or 0)
    clip = int(element.get("clip_orden", 0) or 0)
    return f"s{segment:02d}_c{clip:03d}"


def _available(element: dict[str, Any]) -> bool:
    path = Path(str(element.get("archivo", ""))).expanduser()
    return (
        str(element.get("estado", "")) in {"descargado", "generado_local"}
        and path.is_file()
    )


def _repair_clip(element: dict[str, Any], round_number: int) -> dict[str, Any]:
    """Reconstruye un clip sin reutilizar metadata de la descarga rechazada."""
    clip = copy.deepcopy(element)
    for key in (
        "archivo",
        "estado",
        "fuente",
        "consulta",
        "motivo",
        "error",
        "error_original",
        "reutilizacion",
        "continuidad_visual",
        "generacion_ia",
        "generacion_local",
        "pexels",
        "pixabay",
        "wikimedia",
        "openverse",
    ):
        clip.pop(key, None)

    original_type = str(clip.get("tipo_recurso", ""))
    clip["orden"] = int(clip.get("clip_orden", 0) or 0)
    if round_number >= 2 and original_type == "video_stock":
        # Es preferible una fotografia exacta animada con Ken Burns que un
        # video semanticamente falso.
        clip["tipo_recurso"] = "imagen_stock"

    alternatives = clip.get("consultas_alternativas", [])
    alternatives = (
        [str(item).strip() for item in alternatives if str(item).strip()]
        if isinstance(alternatives, list)
        else []
    )
    if alternatives:
        offset = (round_number - 1) % len(alternatives)
        alternatives = alternatives[offset:] + alternatives[:offset]
    clip["consultas_alternativas"] = alternatives
    clip["_repair_original_type"] = original_type
    return clip


def _repair_plan(
    manifest: dict[str, Any],
    targets: list[dict[str, Any]],
    round_number: int,
) -> dict[str, Any]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for element in targets:
        grouped.setdefault(
            int(element.get("segmento_indice", 0) or 0), []
        ).append(_repair_clip(element, round_number))

    # RecolectorRecursos usa la posicion del segmento como segmento_indice.
    # Se conservan posiciones vacias para que, por ejemplo, el segmento 8 no
    # sea renumerado accidentalmente como segmento 1 durante la reparacion.
    segments: list[dict[str, Any]] = []
    maximum_segment = max(grouped, default=0)
    for segment_number in range(1, maximum_segment + 1):
        clips = grouped.get(segment_number, [])
        clips.sort(key=lambda item: int(item.get("clip_orden", 0) or 0))
        title = (
            str(clips[0].get("segmento_titulo", f"Segmento {segment_number}"))
            if clips
            else f"Segmento {segment_number}"
        )
        segments.append(
            {
                "numero": segment_number,
                "titulo": title,
                "clips": clips,
            }
        )

    return {
        "modelo": "reparacion_visual_selectiva",
        "plan_visual": {
            "titulo": str(manifest.get("titulo", "Sin titulo")),
            "segmentos": segments,
        },
    }


CandidateBuilder = Callable[
    [dict[str, Any], list[dict[str, Any]], int, Path, str], Path
]


class ReparadorVisual:
    """Reemplaza solo recursos rechazados y exige una auditoria posterior."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        auditor: Any | None = None,
        candidate_builder: CandidateBuilder | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.auditor = auditor or AuditorVisualFinal(self.output_dir)
        self.candidate_builder = candidate_builder or self._build_candidates

    def _build_candidates(
        self,
        manifest: dict[str, Any],
        targets: list[dict[str, Any]],
        round_number: int,
        round_dir: Path,
        channel_slug: str,
    ) -> Path:
        # Importaciones diferidas: las pruebas de trazabilidad no necesitan
        # inicializar clientes de stock, Gemini ni Workers AI.
        from autotube.visuals.asset_collector import RecolectorRecursos
        from autotube.visuals.local_asset_generator import GeneradorRecursosLocales

        round_dir.mkdir(parents=True, exist_ok=True)
        plan = _repair_plan(manifest, targets, round_number)
        plan_path = round_dir / "repair_plan.json"
        _write_json_atomic(plan_path, plan)

        collector_output = round_dir / "candidate_output"
        result = RecolectorRecursos(
            data_dir=self.data_dir,
            output_dir=collector_output,
        ).recolectar(
            contenido_plan=plan,
            ruta_plan=plan_path,
            limite=0,
            channel_slug=channel_slug,
        )
        candidate_manifest_path = Path(result["manifiesto"]).resolve()
        candidate_manifest = _read_json(candidate_manifest_path)
        GeneradorRecursosLocales().generar(
            manifiesto=candidate_manifest,
            ruta_manifiesto=candidate_manifest_path,
            forzar=False,
        )
        return candidate_manifest_path

    def repair(
        self,
        assets_path: Path,
        channel_slug: str,
        audit_path: Path | None = None,
        limit: int = 0,
        attempts: int = 3,
    ) -> dict[str, Any]:
        assets_file = Path(assets_path).expanduser().resolve()
        if not assets_file.is_file():
            raise VisualRepairError(f"No existe el manifiesto visual: {assets_file}")
        if attempts < 1 or attempts > 5:
            raise VisualRepairError("Los intentos deben estar entre 1 y 5.")

        manifest = _read_json(assets_file)
        manifest_channel = str(manifest.get("channel_slug", channel_slug))
        if manifest_channel != channel_slug:
            raise VisualRepairError(
                "BLOQUEO MULTICANAL: la coleccion pertenece a "
                f"{manifest_channel}, no a {channel_slug}."
            )

        if audit_path is None:
            initial_audit = self.auditor.audit(
                assets_path=assets_file,
                channel_slug=channel_slug,
                limit=max(0, limit),
            )
        else:
            audit_file = Path(audit_path).expanduser().resolve()
            initial_audit = _read_json(audit_file)
            initial_audit["path"] = str(audit_file)

        if str(initial_audit.get("channel_slug", channel_slug)) != channel_slug:
            raise VisualRepairError("La auditoria pertenece a otro canal.")
        if str(initial_audit.get("assets_fingerprint", "")) != _assets_fingerprint(
            assets_file
        ):
            raise VisualRepairError(
                "La auditoria no corresponde a los bytes actuales del manifiesto. "
                "Ejecuta visual-audit nuevamente."
            )

        audit_elements = initial_audit.get("elements", [])
        if not isinstance(audit_elements, list) or not audit_elements:
            raise VisualRepairError("La auditoria no contiene recursos verificables.")
        if limit > 0:
            audit_elements = audit_elements[:limit]

        elements = manifest.get("elementos", [])
        if not isinstance(elements, list):
            raise VisualRepairError("El manifiesto no contiene una lista de recursos.")
        by_id = {
            _event_id(item): item
            for item in elements
            if isinstance(item, dict)
        }
        rejected_audit = {
            str(item.get("id", "")): item
            for item in audit_elements
            if isinstance(item, dict) and not bool(item.get("approved"))
        }
        remaining = {
            event_id: by_id[event_id]
            for event_id in rejected_audit
            if event_id in by_id
        }

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        repair_dir = self.output_dir / "visual_repairs" / f"repair_{stamp}"
        repair_dir.mkdir(parents=True, exist_ok=True)
        backup_path = repair_dir / "assets_manifest.before_repair.json"
        shutil.copy2(assets_file, backup_path)

        if not remaining:
            final_audit = initial_audit
            report = {
                "version": REPAIR_VERSION,
                "status": str(final_audit.get("status", "approved")),
                "assets_manifest": str(assets_file),
                "initial_audit": str(initial_audit.get("path", "")),
                "final_audit": str(final_audit.get("path", "")),
                "rejected_initially": 0,
                "repaired_assets": 0,
                "pending_assets": 0,
                "backup_manifest": str(backup_path),
                "replacements": [],
            }
            report_path = repair_dir / "visual_repair.json"
            _write_json_atomic(report_path, report)
            report["path"] = str(report_path.resolve())
            return report

        tried_hashes: set[str] = set()
        for item in elements:
            if not isinstance(item, dict):
                continue
            path = Path(str(item.get("archivo", ""))).expanduser()
            if path.is_file():
                tried_hashes.add(_sha256(path))

        replacements: dict[str, dict[str, Any]] = {}
        replacement_log: list[dict[str, Any]] = []

        for round_number in range(1, attempts + 1):
            if not remaining:
                break
            round_dir = repair_dir / f"round_{round_number:02d}"
            candidate_manifest_path = self.candidate_builder(
                manifest,
                list(remaining.values()),
                round_number,
                round_dir,
                channel_slug,
            )
            candidate_manifest = _read_json(candidate_manifest_path)
            candidates = candidate_manifest.get("elementos", [])
            candidates = (
                [item for item in candidates if isinstance(item, dict)]
                if isinstance(candidates, list)
                else []
            )

            auditable: list[dict[str, Any]] = []
            candidate_by_id: dict[str, dict[str, Any]] = {}
            for candidate in candidates:
                event_id = _event_id(candidate)
                if event_id not in remaining or not _available(candidate):
                    continue
                candidate_path = Path(str(candidate["archivo"])).resolve()
                candidate_hash = _sha256(candidate_path)
                if candidate_hash in tried_hashes:
                    replacement_log.append(
                        {
                            "id": event_id,
                            "round": round_number,
                            "approved": False,
                            "reason": "Candidato identico a un recurso ya usado o rechazado.",
                            "candidate_sha256": candidate_hash,
                        }
                    )
                    continue
                tried_hashes.add(candidate_hash)
                auditable.append(candidate)
                candidate_by_id[event_id] = candidate

            if not auditable:
                continue

            audit_manifest_path = round_dir / "auditable_candidates.json"
            _write_json_atomic(
                audit_manifest_path,
                {
                    "channel_slug": channel_slug,
                    "titulo": manifest.get("titulo", ""),
                    "elementos": auditable,
                },
            )
            candidate_audit = self.auditor.audit(
                assets_path=audit_manifest_path,
                channel_slug=channel_slug,
                limit=0,
            )

            for audit_item in candidate_audit.get("elements", []):
                if not isinstance(audit_item, dict):
                    continue
                event_id = str(audit_item.get("id", ""))
                candidate = candidate_by_id.get(event_id)
                approved = bool(audit_item.get("approved"))
                replacement_log.append(
                    {
                        "id": event_id,
                        "round": round_number,
                        "approved": approved,
                        "score": int(audit_item.get("score", 0)),
                        "reason": str(audit_item.get("reason", "")),
                        "description_seen": str(
                            audit_item.get("description_seen", "")
                        ),
                        "candidate_sha256": str(
                            audit_item.get("asset_sha256", "")
                        ),
                    }
                )
                if not approved or candidate is None:
                    continue

                original = remaining[event_id]
                source = Path(str(candidate["archivo"])).resolve()
                source_hash = _sha256(source)
                original_path = Path(str(original.get("archivo", ""))).resolve()
                destination_dir = original_path.parent
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination = destination_dir / (
                    f"clip_{int(original.get('clip_orden', 0) or 0):02d}_"
                    f"reparado_v23_{source_hash[:8]}_r{round_number}"
                    f"{source.suffix.lower()}"
                )
                shutil.copy2(source, destination)

                updated = copy.deepcopy(original)
                old_hash = (
                    _sha256(original_path) if original_path.is_file() else "missing"
                )
                for key in (
                    "pexels",
                    "pixabay",
                    "wikimedia",
                    "openverse",
                    "reutilizacion",
                    "continuidad_visual",
                    "generacion_ia",
                    "generacion_local",
                ):
                    updated.pop(key, None)
                updated["estado"] = str(candidate.get("estado", "descargado"))
                updated["fuente"] = str(candidate.get("fuente", "reparacion_v23"))
                updated["consulta"] = str(candidate.get("consulta", ""))
                updated["archivo"] = str(destination.resolve())
                updated["tipo_recurso"] = str(
                    candidate.get("tipo_recurso", updated.get("tipo_recurso", ""))
                )
                for key in (
                    "pexels",
                    "pixabay",
                    "wikimedia",
                    "openverse",
                    "generacion_ia",
                    "generacion_local",
                ):
                    if key in candidate:
                        updated[key] = copy.deepcopy(candidate[key])
                updated["reparacion_visual"] = {
                    "version": REPAIR_VERSION,
                    "round": round_number,
                    "audit_initial_reason": str(
                        rejected_audit[event_id].get("reason", "")
                    ),
                    "old_asset": str(original_path),
                    "old_sha256": old_hash,
                    "new_sha256": _sha256(destination),
                    "candidate_audit": {
                        "score": int(audit_item.get("score", 0)),
                        "reason": str(audit_item.get("reason", "")),
                        "description_seen": str(
                            audit_item.get("description_seen", "")
                        ),
                    },
                }
                replacements[event_id] = updated
                remaining.pop(event_id, None)

        if replacements:
            new_elements = []
            for item in elements:
                if isinstance(item, dict) and _event_id(item) in replacements:
                    new_elements.append(replacements[_event_id(item)])
                else:
                    new_elements.append(item)
            manifest["elementos"] = new_elements
            summary = manifest.setdefault("resumen", {})
            if isinstance(summary, dict):
                summary["reparados_visual_v23"] = len(replacements)
                summary["pendientes_reparacion_visual"] = len(remaining)
            history = manifest.setdefault("historial_reparaciones_visuales", [])
            if isinstance(history, list):
                history.append(
                    {
                        "version": REPAIR_VERSION,
                        "generated_at": datetime.now().astimezone().isoformat(
                            timespec="seconds"
                        ),
                        "repaired_ids": sorted(replacements),
                        "pending_ids": sorted(remaining),
                        "backup_manifest": str(backup_path.resolve()),
                    }
                )
            _write_json_atomic(assets_file, manifest)

        required_assets = int(initial_audit.get("audited_assets", 0) or 0)
        if limit > 0:
            required_assets = min(required_assets or limit, limit)
        final_audit = self.auditor.audit(
            assets_path=assets_file,
            channel_slug=channel_slug,
            limit=max(0, required_assets),
        )
        final_pending_ids = sorted(
            str(item.get("id", ""))
            for item in final_audit.get("elements", [])
            if isinstance(item, dict) and not bool(item.get("approved"))
        )

        report = {
            "version": REPAIR_VERSION,
            "generated_at": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "status": str(final_audit.get("status", "rejected")),
            "assets_manifest": str(assets_file),
            "initial_audit": str(initial_audit.get("path", "")),
            "final_audit": str(final_audit.get("path", "")),
            "rejected_initially": len(rejected_audit),
            "repaired_assets": len(replacements),
            "pending_assets": len(final_pending_ids),
            "pending_ids": final_pending_ids,
            "backup_manifest": str(backup_path.resolve()),
            "replacements": replacement_log,
        }
        report_path = repair_dir / "visual_repair.json"
        _write_json_atomic(report_path, report)
        report["path"] = str(report_path.resolve())
        return report
