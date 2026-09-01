from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autotube.timeline.semantic_timeline import (
    GeneradorTimelineSemantica,
)
from autotube.timeline.speech_alignment import (
    ALIGNMENT_VERSION,
    build_speech_alignment,
    create_subtitle_cues,
    get_speech_alignment,
)
from autotube.video.composer import (
    sincronizar_duraciones_con_timeline,
)
from autotube.video.subtitle_generator import (
    GeneradorSubtitulos,
)


def _real_audio_manifest() -> dict[str, object]:
    tokens = [
        "Uno",
        "dos",
        "tres",
        "cuatro",
        "cinco",
        "seis",
        "Siete",
        "ocho",
        "nueve",
        "diez",
        "once",
        "doce",
    ]
    return {
        "titulo": "Alineacion real",
        "duracion_total_segundos": 12.0,
        "segmentos": [
            {
                "tipo": "escena",
                "numero": 1,
                "titulo": "Escena de prueba",
                "texto_voz": (
                    "Uno dos tres cuatro cinco seis. "
                    "Siete ocho nueve diez once doce."
                ),
                "duracion_real_segundos": 12.0,
                "marcas_palabras": [
                    {
                        "texto": token,
                        "inicio_segundos": index + 0.1,
                        "final_segundos": index + 0.8,
                    }
                    for index, token in enumerate(tokens)
                ],
            }
        ],
    }


class SpeechAlignmentV2Test(unittest.TestCase):
    def test_creates_global_words_and_semantic_phrases(self) -> None:
        alignment = build_speech_alignment(
            _real_audio_manifest()
        )

        self.assertEqual(alignment["version"], ALIGNMENT_VERSION)
        self.assertEqual(alignment["word_count"], 12)
        self.assertEqual(alignment["phrase_count"], 2)
        self.assertEqual(alignment["phrases"][0]["start_ms"], 0)
        self.assertEqual(alignment["phrases"][0]["end_ms"], 5800)
        self.assertEqual(alignment["phrases"][1]["end_ms"], 12000)
        self.assertEqual(
            alignment["quality"]["timing_source"],
            "edge_word_boundary",
        )
        self.assertTrue(
            str(alignment["phrases"][0]["text"]).endswith("seis.")
        )

    def test_subtitles_use_real_word_boundaries(self) -> None:
        alignment = build_speech_alignment(
            _real_audio_manifest()
        )
        cues = create_subtitle_cues(
            alignment,
            max_words=6,
            max_characters=60,
        )

        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["start_ms"], 100)
        self.assertEqual(cues[0]["end_ms"], 5800)
        self.assertEqual(cues[1]["start_ms"], 6100)
        self.assertEqual(cues[1]["end_ms"], 11800)
        self.assertEqual(cues[0]["word_start"], 1)
        self.assertEqual(cues[1]["word_end"], 12)

        events = GeneradorSubtitulos().crear_eventos(
            _real_audio_manifest(),
            max_palabras=6,
            max_caracteres=60,
        )
        self.assertEqual(events[0]["inicio_segundos"], 0.1)
        self.assertEqual(events[0]["final_segundos"], 5.8)
        self.assertEqual(
            events[0]["sincronizacion"],
            "edge_word_boundary",
        )

    def test_legacy_audio_uses_explicit_fallback(self) -> None:
        alignment = build_speech_alignment(
            {
                "duracion_total_segundos": 4.0,
                "segmentos": [
                    {
                        "texto": "Audio antiguo sin marcas reales.",
                        "duracion_real_segundos": 4.0,
                    }
                ],
            }
        )

        self.assertEqual(
            alignment["quality"]["timing_source"],
            "mixed_with_proportional_fallback",
        )
        self.assertEqual(alignment["quality"]["fallback_segments"], 1)
        self.assertEqual(alignment["phrases"][-1]["end_ms"], 4000)

    def test_rebuilds_stale_cached_alignment(self) -> None:
        manifest = _real_audio_manifest()
        cached = build_speech_alignment(manifest)
        manifest["alineacion_global"] = cached
        manifest["segmentos"][0]["texto_voz"] = (
            "Uno dos tres cuatro cinco seis. "
            "Siete ocho nueve diez once CAMBIO."
        )

        rebuilt = get_speech_alignment(manifest)

        self.assertNotEqual(
            rebuilt["source_fingerprint"],
            cached["source_fingerprint"],
        )
        self.assertIn("CAMBIO.", rebuilt["phrases"][-1]["text"])

    def test_reconciles_mp3_concat_duration_without_gaps(self) -> None:
        manifest = {
            "duracion_total_segundos": 9.2,
            "segmentos": [
                {
                    "texto": f"Palabra {index}.",
                    "duracion_real_segundos": 1.0,
                    "marcas_palabras": [
                        {
                            "texto": "Palabra",
                            "inicio_segundos": 0.1,
                            "final_segundos": 0.5,
                        },
                        {
                            "texto": str(index),
                            "inicio_segundos": 0.55,
                            "final_segundos": 0.9,
                        },
                    ],
                }
                for index in range(10)
            ],
        }

        alignment = build_speech_alignment(manifest)

        self.assertEqual(alignment["duration_ms"], 9200)
        self.assertEqual(alignment["phrases"][0]["start_ms"], 0)
        self.assertEqual(alignment["phrases"][-1]["end_ms"], 9200)
        self.assertEqual(
            alignment["quality"]["reconciled_difference_ms"],
            -800,
        )
        for previous, current in zip(
            alignment["segments"],
            alignment["segments"][1:],
        ):
            self.assertEqual(previous["end_ms"], current["start_ms"])

    def test_timeline_overrides_legacy_asset_times(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = [root / "visual_1.jpg", root / "visual_2.jpg"]
            for path in files:
                path.write_bytes(b"visual")

            assets = {
                "titulo": "Alineacion real",
                "channel_slug": "nexon_ia",
                "elementos": [
                    self._asset(1, files[0], 0.0, 5.0),
                    self._asset(2, files[1], 5.0, 12.0),
                ],
            }
            timeline = GeneradorTimelineSemantica(
                root / "output"
            ).construir(
                assets_manifest=assets,
                audio_manifest=_real_audio_manifest(),
                assets_path=root / "assets.json",
                audio_path=root / "audio.json",
                channel_slug="nexon_ia",
            )

            self.assertEqual(timeline["version"], "semantic_timeline_v2")
            self.assertEqual(timeline["events"][0]["end_ms"], 5800)
            self.assertEqual(timeline["events"][1]["start_ms"], 5800)
            self.assertEqual(
                timeline["events"][0]["alignment"]["source"],
                "edge_word_boundary",
            )
            self.assertEqual(len(timeline["tracks"]["words"]), 12)

    def test_render_uses_timeline_durations_without_rescaling(self) -> None:
        timeline = {
            "duration_ms": 12000,
            "events": [
                {
                    "id": "s01_c001",
                    "segment_index": 1,
                    "clip_order": 1,
                    "start_ms": 0,
                    "end_ms": 5800,
                    "speech_text": "Primera frase.",
                },
                {
                    "id": "s01_c002",
                    "segment_index": 1,
                    "clip_order": 2,
                    "start_ms": 5800,
                    "end_ms": 12000,
                    "speech_text": "Segunda frase.",
                },
            ],
        }
        elements = [
            {
                "segmento_indice": 1,
                "clip_orden": 1,
                "duracion_objetivo_segundos": 4.0,
            },
            {
                "segmento_indice": 1,
                "clip_orden": 2,
                "duracion_objetivo_segundos": 8.0,
            },
        ]

        synchronized = sincronizar_duraciones_con_timeline(
            elements,
            timeline,
        )

        self.assertEqual(
            [item["duracion_objetivo_segundos"] for item in synchronized],
            [5.8, 6.2],
        )
        self.assertEqual(
            synchronized[0]["sincronizacion_render"],
            "semantic_timeline_v2",
        )

    @staticmethod
    def _asset(
        order: int,
        path: Path,
        start: float,
        end: float,
    ) -> dict[str, object]:
        return {
            "segmento_indice": 1,
            "clip_orden": order,
            "estado": "descargado",
            "archivo": str(path),
            "inicio_segundos": start,
            "final_segundos": end,
            "texto_narrado": f"Texto visual {order}",
            "tipo_recurso": "imagen_stock",
            "descripcion": "Visual relacionado",
            "movimiento": "zoom lento",
            "concepto_central": "concepto",
            "criterios_obligatorios": ["sujeto"],
            "elementos_prohibidos": ["relleno"],
        }


if __name__ == "__main__":
    unittest.main()
