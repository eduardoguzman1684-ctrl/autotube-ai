from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image, ImageDraw, ImageOps

if TYPE_CHECKING:
    from autotube.visuals.visual_verifier import VerificadorVisualGemini


AUDIT_VERSION = "final_visual_audit_v1"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


class FinalVisualAuditError(RuntimeError):
    """Impide renderizar recursos que no fueron comprobados visualmente."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise FinalVisualAuditError(f"No se pudo leer el JSON: {path}") from error
    if not isinstance(data, dict):
        raise FinalVisualAuditError(f"El archivo no contiene un objeto JSON: {path}")
    return data


def _assets_fingerprint(path: Path) -> str:
    manifest = _read_json(path)
    elements = manifest.get("elementos", [])
    stable: list[dict[str, Any]] = []
    for element in elements if isinstance(elements, list) else []:
        if not isinstance(element, dict):
            continue
        asset_path = Path(str(element.get("archivo", ""))).expanduser().resolve()
        stable.append(
            {
                "segment": int(element.get("segmento_indice", 0)),
                "clip": int(element.get("clip_orden", 0)),
                "description": str(element.get("descripcion", "")),
                "concept": str(element.get("concepto_central", "")),
                "asset_sha256": _sha256(asset_path) if asset_path.is_file() else "missing",
            }
        )
    payload = json.dumps(
        stable,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _contract(asset: dict[str, Any]) -> str:
    description = str(asset.get("descripcion", "")).strip()
    concept = str(asset.get("concepto_central", "") or description).strip()
    narration = str(asset.get("texto_narrado", "")).strip()
    criteria = asset.get("criterios_obligatorios", [])
    forbidden = asset.get("elementos_prohibidos", [])
    alternatives = asset.get("consultas_alternativas", [])

    def lines(values: Any) -> list[str]:
        return (
            [f"- {str(value).strip()}" for value in values if str(value).strip()]
            if isinstance(values, list)
            else []
        )

    return "\n".join(
        [
            f"CONCEPTO CENTRAL: {concept}",
            f"DESCRIPCION OBJETIVO: {description}",
            "CRITERIOS OBLIGATORIOS:",
            *lines(criteria or [description]),
            "ELEMENTOS PROHIBIDOS:",
            *lines(forbidden),
            f"CONTEXTO NARRADO: {narration[:700]}",
            "BUSQUEDAS ALTERNATIVAS:",
            *lines(alternatives),
        ]
    )


def _video_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return max(0.1, float(result.stdout.strip()))


def _video_contact_sheet(path: Path, destination: Path) -> Path:
    duration = _video_duration(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []

    for index, fraction in enumerate((0.15, 0.50, 0.85), start=1):
        frame = destination.parent / f"{destination.stem}_f{index}.jpg"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{duration * fraction:.3f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                str(frame),
            ],
            check=True,
            timeout=90,
        )
        frames.append(frame)

    sheet = Image.new("RGB", (1440, 270), color=(12, 15, 22))
    drawing = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        with Image.open(frame) as original:
            image = ImageOps.fit(
                original.convert("RGB"),
                (480, 270),
                method=Image.Resampling.LANCZOS,
            )
        sheet.paste(image, (index * 480, 0))
        drawing.rectangle(
            (index * 480 + 8, 8, index * 480 + 64, 44),
            fill=(0, 0, 0),
            outline=(0, 220, 255),
            width=2,
        )
        drawing.text((index * 480 + 24, 17), str(index + 1), fill="white")

    sheet.save(destination, format="JPEG", quality=90)
    return destination


def _representative(asset_path: Path, destination: Path) -> Path:
    extension = asset_path.suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return asset_path
    if extension in VIDEO_EXTENSIONS:
        return _video_contact_sheet(asset_path, destination)
    raise FinalVisualAuditError(f"Formato visual no auditable: {asset_path}")


def _difference_hash(path: Path) -> int:
    with Image.open(path) as original:
        image = original.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        flattened = getattr(image, "get_flattened_data", None)
        pixels = list(flattened() if flattened is not None else image.getdata())
    value = 0
    for row in range(8):
        for column in range(8):
            left = pixels[row * 9 + column]
            right = pixels[row * 9 + column + 1]
            value = (value << 1) | int(left > right)
    return value


def _hamming(first: int, second: int) -> int:
    return (first ^ second).bit_count()


class AuditorVisualFinal:
    """Audita los pixeles o fotogramas reales, nunca solo la metadata."""

    def __init__(
        self,
        output_dir: Path,
        verifier: VerificadorVisualGemini | None = None,
    ) -> None:
        self.output_dir = Path(output_dir).resolve()
        if verifier is None:
            from autotube.visuals.visual_verifier import VerificadorVisualGemini

            verifier = VerificadorVisualGemini(umbral=92)
        self.verifier = verifier

    def audit(
        self,
        assets_path: Path,
        channel_slug: str,
        limit: int = 0,
    ) -> dict[str, Any]:
        assets_file = Path(assets_path).expanduser().resolve()
        manifest = _read_json(assets_file)
        elements_raw = manifest.get("elementos", [])
        if not isinstance(elements_raw, list) or not elements_raw:
            raise FinalVisualAuditError("El manifiesto no contiene recursos visuales.")

        elements = [item for item in elements_raw if isinstance(item, dict)]
        if limit > 0:
            elements = elements[:limit]

        # Los procesos de reparacion pueden ejecutar varias auditorias dentro
        # del mismo segundo. Los microsegundos impiden que un informe pise a
        # otro y preservan la trazabilidad de cada candidato.
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        audit_dir = self.output_dir / "visual_audits" / f"audit_{stamp}"
        representatives_dir = audit_dir / "representatives"
        representatives_dir.mkdir(parents=True, exist_ok=True)

        prepared: list[dict[str, Any]] = []
        previous_hash: int | None = None
        previous_id = ""

        for position, asset in enumerate(elements, start=1):
            path = Path(str(asset.get("archivo", ""))).expanduser().resolve()
            if not path.is_file():
                raise FinalVisualAuditError(f"No existe el recurso {position}: {path}")

            identifier = (
                f"s{int(asset.get('segmento_indice', 0)):02d}_"
                f"c{int(asset.get('clip_orden', 0)):03d}"
            )
            representative = _representative(
                path,
                representatives_dir / f"{identifier}_video.jpg",
            )
            visual_hash = _difference_hash(representative)
            duplicate_of = (
                previous_id
                if previous_hash is not None and _hamming(previous_hash, visual_hash) <= 2
                else ""
            )
            prepared.append(
                {
                    "id": identifier,
                    "asset": asset,
                    "asset_path": path,
                    "representative": representative,
                    "sha256": _sha256(path),
                    "duplicate_of": duplicate_of,
                }
            )
            previous_hash = visual_hash
            previous_id = identifier

        results_by_id: dict[str, dict[str, Any]] = {}
        candidates = [item for item in prepared if not item["duplicate_of"]]

        for offset in range(0, len(candidates), 5):
            batch = candidates[offset : offset + 5]
            groups = [
                {
                    "id": item["id"],
                    "imagenes": [item["representative"]],
                    "requisito_visual": _contract(item["asset"]),
                }
                for item in batch
            ]
            sheet = audit_dir / f"verification_batch_{offset // 5 + 1:03d}.jpg"
            try:
                verified = self.verifier.seleccionar_lote(groups, sheet)
            except Exception as error:
                raise FinalVisualAuditError(
                    "No se pudo completar la auditoria visual estricta con Gemini."
                ) from error
            results_by_id.update(verified)

        audit_elements: list[dict[str, Any]] = []
        for item in prepared:
            if item["duplicate_of"]:
                result = {
                    "aprobada": False,
                    "puntaje": 0,
                    "motivo": (
                        "Recurso visual duplicado o casi identico al evento anterior."
                    ),
                }
            else:
                result = dict(results_by_id.get(item["id"], {}))

            approved = bool(result.get("aprobada", False)) and int(
                result.get("seleccion", 0)
            ) == 1
            audit_elements.append(
                {
                    "id": item["id"],
                    "approved": approved,
                    "score": int(result.get("puntaje", 0)),
                    "reason": str(result.get("motivo", "Sin resultado verificable.")),
                    "description_seen": str(result.get("descripcion", "")),
                    "asset_path": str(item["asset_path"]),
                    "asset_sha256": item["sha256"],
                    "representative": str(item["representative"]),
                    "duplicate_of": item["duplicate_of"],
                }
            )

        approved_count = sum(int(item["approved"]) for item in audit_elements)
        report = {
            "version": AUDIT_VERSION,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "channel_slug": channel_slug,
            "assets_manifest": str(assets_file),
            "assets_manifest_sha256": _sha256(assets_file),
            "assets_fingerprint": _assets_fingerprint(assets_file),
            "total_manifest_assets": len(elements_raw),
            "audited_assets": len(audit_elements),
            "approved_assets": approved_count,
            "rejected_assets": len(audit_elements) - approved_count,
            "complete": len(audit_elements) == len(elements_raw),
            "status": (
                "approved"
                if approved_count == len(audit_elements) and audit_elements
                else "rejected"
            ),
            "elements": audit_elements,
        }
        report_path = audit_dir / "visual_audit.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report["path"] = str(report_path.resolve())
        return report


def find_compatible_audit(
    output_dir: Path,
    assets_path: Path,
    required_assets: int,
    audit_path: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    assets_file = Path(assets_path).resolve()
    candidates = (
        [Path(audit_path).expanduser().resolve()]
        if audit_path is not None
        else sorted(
            Path(output_dir).glob("visual_audits/audit_*/visual_audit.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    )
    assets_fingerprint = _assets_fingerprint(assets_file)

    for candidate in candidates:
        if not candidate.is_file():
            continue
        report = _read_json(candidate)
        if str(report.get("assets_fingerprint", "")) != assets_fingerprint:
            continue
        elements = report.get("elements", [])
        if not isinstance(elements, list) or len(elements) < required_assets:
            continue
        selected = elements[:required_assets]
        if not all(isinstance(item, dict) and bool(item.get("approved")) for item in selected):
            continue
        current_assets = _read_json(assets_file).get("elementos", [])[:required_assets]
        hashes_match = all(
            _sha256(Path(str(asset.get("archivo", ""))).resolve())
            == str(audit.get("asset_sha256", ""))
            for asset, audit in zip(current_assets, selected)
            if isinstance(asset, dict)
        )
        if hashes_match and len(current_assets) == len(selected):
            return report, candidate

    raise FinalVisualAuditError(
        "No existe una auditoria visual final aprobada y compatible. "
        "Ejecuta autotube visual-audit antes del render."
    )
