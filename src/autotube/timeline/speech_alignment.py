from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


ALIGNMENT_VERSION = "speech_alignment_v2"


class SpeechAlignmentError(RuntimeError):
    """Indica que las marcas de voz no pueden formar una timeline segura."""


def _source_fingerprint(
    audio_manifest: dict[str, Any],
) -> str:
    segments = audio_manifest.get("segmentos", [])
    payload = {
        "duration": audio_manifest.get(
            "duracion_total_segundos"
        ),
        "segments": [
            {
                "type": segment.get("tipo"),
                "number": segment.get("numero"),
                "text": segment.get("texto_voz")
                or segment.get("texto"),
                "duration": segment.get(
                    "duracion_real_segundos"
                ),
                "boundaries": segment.get(
                    "marcas_palabras",
                    [],
                ),
            }
            for segment in segments
            if isinstance(segment, dict)
        ],
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _milliseconds(seconds: float) -> int:
    return round(seconds * 1000)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_token(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value).lower())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character) and character.isalnum()
    )


def _punctuation_strength(token: str) -> int:
    stripped = str(token).rstrip('"\'»”)]}')
    if stripped.endswith((".", "!", "?")):
        return 3
    if stripped.endswith((";", ":")):
        return 2
    if stripped.endswith(","):
        return 1
    return 0


def _source_tokens(text: str) -> list[str]:
    return re.findall(r"\S+", str(text).strip())


def _match_display_tokens(
    boundary_words: list[str],
    narration: str,
) -> list[tuple[str, int]]:
    source = _source_tokens(narration)
    if not source:
        return [(word, 0) for word in boundary_words]

    normalized_source = [_normalize_token(token) for token in source]
    cursor = 0
    result: list[tuple[str, int]] = []

    for index, word in enumerate(boundary_words):
        normalized_word = _normalize_token(word)
        match: int | None = None

        for candidate in range(cursor, min(len(source), cursor + 5)):
            if normalized_word and normalized_source[candidate] == normalized_word:
                match = candidate
                break

        if match is None and index < len(source):
            proportional = min(
                len(source) - 1,
                int(index * len(source) / max(1, len(boundary_words))),
            )
            if proportional >= cursor:
                match = proportional

        if match is None:
            display = word
            strength = 0
        else:
            display = source[match]
            strength = _punctuation_strength(display)
            cursor = match + 1

        result.append((display, strength))

    return result


def _prepare_words(
    segment: dict[str, Any],
    duration_ms: int,
    source_duration_ms: int,
) -> tuple[list[dict[str, Any]], str]:
    narration = str(
        segment.get("texto_voz") or segment.get("texto") or ""
    ).strip()
    raw_boundaries = segment.get("marcas_palabras", [])
    parsed: list[dict[str, Any]] = []

    if isinstance(raw_boundaries, list):
        for raw in raw_boundaries:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("texto", "")).strip()
            if not text:
                continue

            source_start_ms = _milliseconds(
                max(0.0, _number(raw.get("inicio_segundos"), 0.0))
            )
            source_end_ms = _milliseconds(
                max(
                    0.0,
                    _number(
                        raw.get("final_segundos"),
                        source_start_ms / 1000,
                    ),
                )
            )
            scale = duration_ms / max(1, source_duration_ms)
            start_ms = round(source_start_ms * scale)
            end_ms = round(source_end_ms * scale)
            start_ms = min(duration_ms, start_ms)
            end_ms = min(duration_ms, max(start_ms + 1, end_ms))

            parsed.append(
                {
                    "raw_text": text,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                }
            )

    parsed.sort(key=lambda word: (word["start_ms"], word["end_ms"]))

    if parsed:
        for current, following in zip(
            parsed,
            parsed[1:],
        ):
            if int(following["start_ms"]) <= int(current["start_ms"]):
                raise SpeechAlignmentError(
                    "Dos marcas WordBoundary comienzan al mismo tiempo."
                )
            current["end_ms"] = min(
                int(current["end_ms"]),
                int(following["start_ms"]),
            )
            current["end_ms"] = max(
                int(current["start_ms"]) + 1,
                int(current["end_ms"]),
            )

        display = _match_display_tokens(
            [str(word["raw_text"]) for word in parsed],
            narration,
        )
        previous_start = -1
        for word, (display_text, strength) in zip(parsed, display):
            if int(word["start_ms"]) < previous_start:
                raise SpeechAlignmentError(
                    "Las marcas WordBoundary no estan ordenadas."
                )
            previous_start = int(word["start_ms"])
            word["text"] = display_text
            word["punctuation_strength"] = strength
        return parsed, "edge_word_boundary"

    tokens = _source_tokens(narration)
    if not tokens:
        raise SpeechAlignmentError(
            "Un segmento de audio no contiene texto ni marcas de palabras."
        )

    step = duration_ms / len(tokens)
    fallback: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        start_ms = round(step * index)
        end_ms = duration_ms if index == len(tokens) - 1 else round(step * (index + 1))
        fallback.append(
            {
                "raw_text": token,
                "text": token,
                "start_ms": start_ms,
                "end_ms": max(start_ms + 1, end_ms),
                "punctuation_strength": _punctuation_strength(token),
            }
        )
    return fallback, "proportional_fallback"


def _create_phrases(
    words: list[dict[str, Any]],
    segment_index: int,
    segment_start_ms: int,
    duration_ms: int,
    target_ms: int,
    minimum_ms: int,
    maximum_ms: int,
) -> list[dict[str, Any]]:
    phrases: list[dict[str, Any]] = []
    first_index = 0
    phrase_start = 0
    last_index = len(words) - 1

    while first_index <= last_index:
        remaining = duration_ms - phrase_start
        if remaining <= maximum_ms:
            cut_index = last_index
        else:
            candidates = [
                index
                for index in range(first_index, last_index + 1)
                if minimum_ms
                <= int(words[index]["end_ms"]) - phrase_start
                <= maximum_ms
            ]
            semantic = [
                index
                for index in candidates
                if int(words[index].get("punctuation_strength", 0)) > 0
            ]
            if semantic:
                cut_index = max(
                    semantic,
                    key=lambda index: (
                        int(words[index].get("punctuation_strength", 0)),
                        -abs(
                            (int(words[index]["end_ms"]) - phrase_start)
                            - target_ms
                        ),
                    ),
                )
            elif candidates:
                cut_index = min(
                    candidates,
                    key=lambda index: abs(
                        (int(words[index]["end_ms"]) - phrase_start) - target_ms
                    ),
                )
            else:
                cut_index = min(
                    range(first_index, last_index + 1),
                    key=lambda index: abs(
                        (int(words[index]["end_ms"]) - phrase_start) - target_ms
                    ),
                )

        phrase_end = (
            duration_ms
            if cut_index == last_index
            else int(words[cut_index]["end_ms"])
        )
        phrase_end = min(duration_ms, max(phrase_start + 1, phrase_end))
        phrase_text = " ".join(
            str(word["text"])
            for word in words[first_index : cut_index + 1]
        ).strip()

        phrases.append(
            {
                "id": f"s{segment_index:02d}_p{len(phrases) + 1:03d}",
                "segment_index": segment_index,
                "phrase_index": len(phrases) + 1,
                "start_ms": segment_start_ms + phrase_start,
                "end_ms": segment_start_ms + phrase_end,
                "duration_ms": phrase_end - phrase_start,
                "text": phrase_text,
                "segment_word_start": first_index,
                "segment_word_end": cut_index,
            }
        )
        first_index = cut_index + 1
        phrase_start = phrase_end

    if len(phrases) > 1 and int(phrases[-1]["duration_ms"]) < minimum_ms:
        previous = phrases[-2]
        last = phrases[-1]
        if int(previous["duration_ms"]) + int(last["duration_ms"]) <= maximum_ms + 1500:
            previous["end_ms"] = last["end_ms"]
            previous["duration_ms"] = int(previous["end_ms"]) - int(previous["start_ms"])
            previous["text"] = f"{previous['text']} {last['text']}".strip()
            previous["segment_word_end"] = last["segment_word_end"]
            phrases.pop()

    for index, phrase in enumerate(phrases, start=1):
        phrase["phrase_index"] = index
        phrase["id"] = f"s{segment_index:02d}_p{index:03d}"

    return phrases


def build_speech_alignment(
    audio_manifest: dict[str, Any],
    target_seconds: float = 6.5,
    minimum_seconds: float = 3.0,
    maximum_seconds: float = 10.0,
    total_tolerance_ms: int = 180,
) -> dict[str, Any]:
    segments_raw = audio_manifest.get("segmentos", [])
    if not isinstance(segments_raw, list) or not segments_raw:
        raise SpeechAlignmentError(
            "El manifiesto de audio no contiene segmentos validos."
        )

    source_durations = [
        _milliseconds(
            _number(segment.get("duracion_real_segundos"), 0.0)
        )
        if isinstance(segment, dict)
        else 0
        for segment in segments_raw
    ]
    if any(duration <= 0 for duration in source_durations):
        raise SpeechAlignmentError(
            "Uno o mas segmentos no tienen duracion real valida."
        )

    source_total_ms = sum(source_durations)
    declared_total_ms = _milliseconds(
        _number(
            audio_manifest.get("duracion_total_segundos"),
            source_total_ms / 1000,
        )
    )
    allowed_difference_ms = max(
        max(0, int(total_tolerance_ms)),
        len(segments_raw) * 120,
    )
    if abs(declared_total_ms - source_total_ms) > allowed_difference_ms:
        raise SpeechAlignmentError(
            "La duracion completa y la suma de segmentos difieren "
            f"por {abs(declared_total_ms - source_total_ms)} ms."
        )

    scale = declared_total_ms / max(1, source_total_ms)
    reconciled_durations = [
        max(1, round(duration * scale))
        for duration in source_durations
    ]
    reconciled_durations[-1] += (
        declared_total_ms - sum(reconciled_durations)
    )

    segments: list[dict[str, Any]] = []
    global_words: list[dict[str, Any]] = []
    global_phrases: list[dict[str, Any]] = []
    accumulated_ms = 0
    real_segments = 0

    for segment_index, (
        raw_segment,
        duration_ms,
        source_duration_ms,
    ) in enumerate(
        zip(
            segments_raw,
            reconciled_durations,
            source_durations,
        ),
        start=1,
    ):
        if not isinstance(raw_segment, dict):
            raise SpeechAlignmentError(
                f"El segmento {segment_index} no es un objeto valido."
            )

        local_words, timing_source = _prepare_words(
            raw_segment,
            duration_ms,
            source_duration_ms,
        )
        if timing_source == "edge_word_boundary":
            real_segments += 1

        segment_words: list[dict[str, Any]] = []
        for local_index, word in enumerate(local_words, start=1):
            global_word = {
                "id": f"s{segment_index:02d}_w{local_index:04d}",
                "segment_index": segment_index,
                "word_index": local_index,
                "global_word_index": len(global_words) + 1,
                "text": str(word["text"]),
                "raw_text": str(word["raw_text"]),
                "start_ms": accumulated_ms + int(word["start_ms"]),
                "end_ms": accumulated_ms + int(word["end_ms"]),
                "duration_ms": int(word["end_ms"]) - int(word["start_ms"]),
                "punctuation_strength": int(word["punctuation_strength"]),
                "timing_source": timing_source,
            }
            segment_words.append(global_word)
            global_words.append(global_word)

        phrases = _create_phrases(
            words=local_words,
            segment_index=segment_index,
            segment_start_ms=accumulated_ms,
            duration_ms=duration_ms,
            target_ms=_milliseconds(target_seconds),
            minimum_ms=_milliseconds(minimum_seconds),
            maximum_ms=_milliseconds(maximum_seconds),
        )
        for phrase in phrases:
            phrase["timing_source"] = timing_source
            phrase["global_word_start"] = segment_words[
                int(phrase["segment_word_start"])
            ]["global_word_index"]
            phrase["global_word_end"] = segment_words[
                int(phrase["segment_word_end"])
            ]["global_word_index"]
            global_phrases.append(phrase)

        segment_end = accumulated_ms + duration_ms
        segments.append(
            {
                "segment_index": segment_index,
                "type": str(raw_segment.get("tipo", "escena")),
                "number": raw_segment.get("numero", segment_index),
                "title": str(raw_segment.get("titulo", f"Segmento {segment_index}")),
                "start_ms": accumulated_ms,
                "end_ms": segment_end,
                "duration_ms": duration_ms,
                "timing_source": timing_source,
                "word_count": len(segment_words),
                "phrase_count": len(phrases),
                "words": segment_words,
                "phrases": phrases,
            }
        )
        accumulated_ms = segment_end

    difference = declared_total_ms - accumulated_ms
    total_ms = declared_total_ms
    if difference and segments:
        segments[-1]["end_ms"] = total_ms
        segments[-1]["duration_ms"] = (
            int(segments[-1]["end_ms"]) - int(segments[-1]["start_ms"])
        )
        if global_phrases:
            global_phrases[-1]["end_ms"] = total_ms
            global_phrases[-1]["duration_ms"] = (
                total_ms - int(global_phrases[-1]["start_ms"])
            )
            segments[-1]["phrases"][-1]["end_ms"] = total_ms
            segments[-1]["phrases"][-1]["duration_ms"] = (
                total_ms - int(segments[-1]["phrases"][-1]["start_ms"])
            )

    return {
        "version": ALIGNMENT_VERSION,
        "source_fingerprint": _source_fingerprint(
            audio_manifest
        ),
        "duration_ms": total_ms,
        "word_count": len(global_words),
        "phrase_count": len(global_phrases),
        "quality": {
            "timing_source": (
                "edge_word_boundary"
                if real_segments == len(segments)
                else "mixed_with_proportional_fallback"
            ),
            "real_boundary_segments": real_segments,
            "fallback_segments": len(segments) - real_segments,
            "coverage_start_ms": 0,
            "coverage_end_ms": total_ms,
            "source_segment_total_ms": source_total_ms,
            "reconciled_difference_ms": (
                declared_total_ms
                - source_total_ms
            ),
            "segment_time_scale": round(
                scale,
                8,
            ),
        },
        "segments": segments,
        "words": global_words,
        "phrases": global_phrases,
    }


def get_speech_alignment(audio_manifest: dict[str, Any]) -> dict[str, Any]:
    existing = audio_manifest.get("alineacion_global")
    if (
        isinstance(existing, dict)
        and existing.get("version") == ALIGNMENT_VERSION
        and existing.get("source_fingerprint")
        == _source_fingerprint(audio_manifest)
        and isinstance(existing.get("words"), list)
        and isinstance(existing.get("phrases"), list)
    ):
        return existing
    return build_speech_alignment(audio_manifest)


def create_subtitle_cues(
    alignment: dict[str, Any],
    max_words: int = 12,
    max_characters: int = 74,
) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []

    for segment in alignment.get("segments", []):
        if not isinstance(segment, dict):
            continue
        words = segment.get("words", [])
        if not isinstance(words, list) or not words:
            continue

        group: list[dict[str, Any]] = []

        def flush() -> None:
            if not group:
                return
            cues.append(
                {
                    "start_ms": int(group[0]["start_ms"]),
                    "end_ms": int(group[-1]["end_ms"]),
                    "text": " ".join(str(word["text"]) for word in group).strip(),
                    "segment_index": int(segment["segment_index"]),
                    "word_start": int(group[0]["global_word_index"]),
                    "word_end": int(group[-1]["global_word_index"]),
                    "timing_source": str(segment["timing_source"]),
                }
            )
            group.clear()

        for word in words:
            candidate = " ".join(
                [*(str(item["text"]) for item in group), str(word["text"])]
            )
            if group and (
                len(group) >= max_words or len(candidate) > max_characters
            ):
                flush()

            group.append(word)
            if (
                int(word.get("punctuation_strength", 0)) >= 2
                and len(group) >= 4
            ):
                flush()

        flush()

    for index, cue in enumerate(cues, start=1):
        cue["id"] = f"sub_{index:04d}"
        if int(cue["end_ms"]) <= int(cue["start_ms"]):
            cue["end_ms"] = int(cue["start_ms"]) + 1

    return cues
