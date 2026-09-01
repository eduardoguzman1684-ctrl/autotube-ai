from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


TIMELINE_VERSION = "semantic_timeline_v1"
READY_ASSET_STATES = {"descargado", "generado_local"}


class TimelineValidationError(RuntimeError):
    """Indica que la narracion y los visuales no cubren el mismo tiempo."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise TimelineValidationError(
            f"No se pudo leer el manifiesto JSON: {path}"
        ) from error

    if not isinstance(data, dict):
        raise TimelineValidationError(
            f"El manifiesto no contiene un objeto JSON: {path}"
        )

    return data


def _latest(output_dir: Path, pattern: str, label: str) -> Path:
    candidates = sorted(
        output_dir.glob(pattern),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        raise FileNotFoundError(f"No se encontro un manifiesto de {label}.")

    return candidates[0].resolve()


def _float(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise TimelineValidationError(
            f"Valor temporal invalido en {field}: {value!r}"
        ) from error


def _int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise TimelineValidationError(
            f"Valor entero invalido en {field}: {value!r}"
        ) from error


def _ms(seconds: float) -> int:
    return round(seconds * 1000)


def _visual_verification(asset: dict[str, Any]) -> dict[str, Any]:
    direct = asset.get("verificacion_visual")
    if isinstance(direct, dict):
        return direct

    for value in asset.values():
        if not isinstance(value, dict):
            continue

        nested = value.get("verificacion_visual")
        if isinstance(nested, dict):
            return nested

    return {}


class GeneradorTimelineSemantica:
    """Crea la fuente temporal unica antes del render final."""

    def __init__(
        self,
        output_dir: Path,
        tolerance_ms: int = 150,
    ) -> None:
        self.output_dir = Path(output_dir).resolve()
        self.tolerance_ms = max(0, int(tolerance_ms))

    def localizar_manifiestos(
        self,
        assets_path: Path | None = None,
        audio_path: Path | None = None,
    ) -> tuple[Path, Path]:
        assets = (
            Path(assets_path).expanduser().resolve()
            if assets_path is not None
            else _latest(
                self.output_dir,
                "assets/coleccion_*/assets_manifest.json",
                "recursos visuales",
            )
        )
        audio = (
            Path(audio_path).expanduser().resolve()
            if audio_path is not None
            else _latest(
                self.output_dir,
                "audio/narracion_*/manifest.json",
                "audio",
            )
        )

        if not assets.is_file():
            raise FileNotFoundError(f"No existe el manifiesto visual: {assets}")
        if not audio.is_file():
            raise FileNotFoundError(f"No existe el manifiesto de audio: {audio}")

        return assets, audio

    def construir(
        self,
        assets_manifest: dict[str, Any],
        audio_manifest: dict[str, Any],
        assets_path: Path,
        audio_path: Path,
        channel_slug: str,
    ) -> dict[str, Any]:
        title_assets = str(assets_manifest.get("titulo", "")).strip()
        title_audio = str(audio_manifest.get("titulo", "")).strip()

        if title_assets and title_audio and title_assets != title_audio:
            raise TimelineValidationError(
                "El audio y los recursos pertenecen a producciones diferentes."
            )

        manifest_channel = str(
            assets_manifest.get("channel_slug", channel_slug)
        ).strip()
        if manifest_channel and manifest_channel != channel_slug:
            raise TimelineValidationError(
                "El manifiesto visual pertenece a otro canal: "
                f"{manifest_channel}."
            )

        audio_segments = audio_manifest.get("segmentos", [])
        if not isinstance(audio_segments, list) or not audio_segments:
            raise TimelineValidationError(
                "El manifiesto de audio no contiene segmentos."
            )

        segment_windows: dict[int, tuple[int, int]] = {}
        accumulated_ms = 0

        for position, segment in enumerate(audio_segments, start=1):
            if not isinstance(segment, dict):
                raise TimelineValidationError(
                    f"Segmento de audio invalido en la posicion {position}."
                )

            duration = _float(
                segment.get("duracion_real_segundos", 0),
                "duracion_real_segundos",
            )
            if duration <= 0:
                raise TimelineValidationError(
                    f"El segmento de audio {position} no tiene duracion valida."
                )

            end_ms = accumulated_ms + _ms(duration)
            segment_windows[position] = (accumulated_ms, end_ms)
            accumulated_ms = end_ms

        declared_total_ms = _ms(
            _float(
                audio_manifest.get(
                    "duracion_total_segundos",
                    accumulated_ms / 1000,
                ),
                "duracion_total_segundos",
            )
        )
        total_ms = accumulated_ms

        if abs(declared_total_ms - total_ms) > self.tolerance_ms:
            raise TimelineValidationError(
                "La suma de segmentos no coincide con la duracion total "
                f"del audio: {total_ms} ms frente a {declared_total_ms} ms."
            )

        raw_assets = assets_manifest.get("elementos", [])
        if not isinstance(raw_assets, list) or not raw_assets:
            raise TimelineValidationError(
                "El manifiesto visual no contiene elementos."
            )

        ordered_assets = sorted(
            (item for item in raw_assets if isinstance(item, dict)),
            key=lambda item: (
                _int(item.get("segmento_indice", 0), "segmento_indice"),
                _int(item.get("clip_orden", 0), "clip_orden"),
            ),
        )

        events: list[dict[str, Any]] = []

        for position, asset in enumerate(ordered_assets, start=1):
            state = str(asset.get("estado", "")).strip()
            if state not in READY_ASSET_STATES:
                raise TimelineValidationError(
                    "La timeline no admite recursos pendientes: "
                    f"elemento {position}, estado={state or 'vacio'}."
                )

            asset_file = Path(str(asset.get("archivo", ""))).expanduser()
            if not asset_file.is_file():
                raise TimelineValidationError(
                    f"No existe el recurso visual del elemento {position}: "
                    f"{asset_file}"
                )

            segment_index = _int(
                asset.get("segmento_indice", 0),
                "segmento_indice",
            )
            clip_order = _int(asset.get("clip_orden", 0), "clip_orden")

            if segment_index not in segment_windows:
                raise TimelineValidationError(
                    f"El elemento {position} apunta a un segmento inexistente."
                )

            start_ms = _ms(
                _float(asset.get("inicio_segundos", 0), "inicio_segundos")
            )
            end_ms = _ms(
                _float(asset.get("final_segundos", 0), "final_segundos")
            )

            if end_ms <= start_ms:
                raise TimelineValidationError(
                    f"Intervalo invalido en el elemento {position}: "
                    f"{start_ms}-{end_ms} ms."
                )

            segment_start_ms, segment_end_ms = segment_windows[segment_index]
            if (
                start_ms < segment_start_ms - self.tolerance_ms
                or end_ms > segment_end_ms + self.tolerance_ms
            ):
                raise TimelineValidationError(
                    f"El elemento {position} sale del segmento de audio "
                    f"{segment_index}."
                )

            speech_text = str(asset.get("texto_narrado", "")).strip()
            if not speech_text:
                raise TimelineValidationError(
                    f"El elemento {position} no conserva el texto narrado."
                )

            verification = _visual_verification(asset)
            events.append(
                {
                    "id": f"s{segment_index:02d}_c{clip_order:03d}",
                    "segment_index": segment_index,
                    "clip_order": clip_order,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "duration_ms": end_ms - start_ms,
                    "speech_text": speech_text,
                    "subtitle_text": speech_text,
                    "visual": {
                        "asset_type": str(asset.get("tipo_recurso", "")),
                        "asset_path": str(asset_file.resolve()),
                        "description": str(asset.get("descripcion", "")),
                        "movement": str(asset.get("movimiento", "")),
                        "concept": str(asset.get("concepto_central", "")),
                        "required": list(
                            asset.get("criterios_obligatorios", [])
                            if isinstance(
                                asset.get("criterios_obligatorios", []), list
                            )
                            else []
                        ),
                        "forbidden": list(
                            asset.get("elementos_prohibidos", [])
                            if isinstance(
                                asset.get("elementos_prohibidos", []), list
                            )
                            else []
                        ),
                        "continuity_id": str(
                            asset.get("continuidad_id", "")
                        ),
                    },
                    "transition": {"type": "cut", "duration_ms": 0},
                    "semantic_verification": verification,
                }
            )

        events.sort(key=lambda event: (event["start_ms"], event["end_ms"]))
        self.validar_eventos(events=events, total_ms=total_ms)

        return {
            "version": TIMELINE_VERSION,
            "generated_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "channel_slug": channel_slug,
            "title": title_audio or title_assets or "Sin titulo",
            "duration_ms": total_ms,
            "sources": {
                "audio_manifest": str(audio_path.resolve()),
                "assets_manifest": str(assets_path.resolve()),
            },
            "validation": {
                "status": "approved",
                "tolerance_ms": self.tolerance_ms,
                "events": len(events),
                "coverage_ms": total_ms,
            },
            "events": events,
        }

    def validar_eventos(
        self,
        events: list[dict[str, Any]],
        total_ms: int,
    ) -> None:
        if not events:
            raise TimelineValidationError("La timeline no contiene eventos.")

        if abs(int(events[0]["start_ms"])) > self.tolerance_ms:
            raise TimelineValidationError(
                "La cobertura visual no comienza junto con la narracion."
            )

        for previous, current in zip(events, events[1:]):
            delta = int(current["start_ms"]) - int(previous["end_ms"])
            if abs(delta) > self.tolerance_ms:
                kind = "hueco" if delta > 0 else "solapamiento"
                raise TimelineValidationError(
                    f"Se detecto un {kind} de {abs(delta)} ms entre "
                    f"{previous['id']} y {current['id']}."
                )

        final_delta = total_ms - int(events[-1]["end_ms"])
        if abs(final_delta) > self.tolerance_ms:
            raise TimelineValidationError(
                "La cobertura visual no termina junto con la narracion: "
                f"diferencia={final_delta} ms."
            )

    def generar(
        self,
        assets_path: Path | None = None,
        audio_path: Path | None = None,
        channel_slug: str = "nexon_ia",
    ) -> dict[str, Any]:
        assets_file, audio_file = self.localizar_manifiestos(
            assets_path=assets_path,
            audio_path=audio_path,
        )
        timeline = self.construir(
            assets_manifest=_read_json(assets_file),
            audio_manifest=_read_json(audio_file),
            assets_path=assets_file,
            audio_path=audio_file,
            channel_slug=channel_slug,
        )

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        directory = self.output_dir / "timelines" / f"timeline_{stamp}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "timeline.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(timeline, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

        return {
            "timeline": timeline,
            "path": path,
            "events": len(timeline["events"]),
            "duration_ms": timeline["duration_ms"],
        }
