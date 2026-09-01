from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_CHANNEL = "nexon_ia"

CHANNEL_PROFILES: dict[str, dict[str, Any]] = {
    "nexon_ia": {
        "display_name": "Nexon IA",
        "brand_label": "NEXON IA",
        "drive_root_folder": "NEXON IA - AutoTube AI",
        "default_niche": (
            "documentales de divulgacion sobre inteligencia artificial, "
            "su historia, funcionamiento, avances, innovaciones, "
            "aplicaciones, impacto social, riesgos, etica y futuro"
        ),
        "mission": (
            "Explicar la inteligencia artificial al publico general "
            "mediante documentales narrativos, educativos, rigurosos "
            "y visualmente atractivos."
        ),
        "priority_topics": (
            "funcionamiento e historia de la inteligencia artificial",
            "avances, investigacion e innovacion",
            "IA generativa, robots y sistemas autonomos",
            "aplicaciones en medicina, ciencia, educacion e industria",
            "riesgos, privacidad, sesgos, regulacion y etica",
            "impacto laboral, economico, cultural y geopolitico",
            "escenarios futuros de la inteligencia artificial",
        ),
        "forbidden_topics": (
            "tutoriales, instalaciones y configuraciones",
            "recorridos por interfaces o instrucciones paso a paso",
            "noticias, estudios, cifras o avances inventados",
        ),
        "script_development": (
            "contexto e historia; funcionamiento; avances y aplicaciones; "
            "beneficios, riesgos, impacto social y perspectivas futuras"
        ),
        "audience": (
            "publico general interesado en inteligencia artificial, "
            "tecnologia y futuro"
        ),
        "cta": "Suscribete a Nexon IA para descubrir como la inteligencia artificial esta transformando el mundo.",
        "short_cta": "DOCUMENTAL COMPLETO EN NEXON IA",
        "short_description": "Mira el documental completo en Nexon IA.",
        "hashtags": "#InteligenciaArtificial #Tecnologia #Shorts",
        "category_id": "28",
        "colors": {
            "primary": (0, 224, 245),
            "accent": (245, 45, 65),
            "panel": (5, 10, 24),
        },
    },
    "cogniviva": {
        "display_name": "CogniViva",
        "brand_label": "COGNIVIVA",
        "drive_root_folder": "COGNIVIVA - AutoTube AI",
        "default_niche": (
            "psicologia practica: habitos y decisiones, relaciones y "
            "emociones, trabajo y liderazgo"
        ),
        "mission": (
            "Traducir la psicologia basada en evidencia a ideas claras, "
            "humanas y aplicables para comprender mejor lo que pensamos, "
            "sentimos y hacemos."
        ),
        "priority_topics": (
            "habitos, motivacion, autocontrol y toma de decisiones",
            "emociones, autoconocimiento y regulacion emocional",
            "relaciones, comunicacion, limites y resolucion de conflictos",
            "sesgos cognitivos, personalidad y psicologia social",
            "psicologia del trabajo, liderazgo, equipos y bienestar laboral",
            "conductas cotidianas explicadas con evidencia psicologica",
        ),
        "forbidden_topics": (
            "inteligencia artificial o tecnologia como tema central, salvo que el nicho lo solicite expresamente",
            "diagnosticos, autodiagnosticos o tratamientos clinicos",
            "consejos medicos o promesas de curacion",
            "pseudociencia, manipulacion emocional o afirmaciones absolutas",
            "estadisticas, estudios o citas inventadas",
        ),
        "script_development": (
            "situacion cotidiana; mecanismo psicologico; evidencia y "
            "matices; ejemplos; consecuencias; aplicaciones practicas "
            "seguras y una reflexion final"
        ),
        "audience": (
            "adultos hispanohablantes que desean comprender sus habitos, "
            "emociones, relaciones y vida laboral"
        ),
        "cta": "Suscribete a CogniViva para comprender mejor tu mente, tus relaciones y tus decisiones.",
        "short_cta": "VIDEO COMPLETO EN COGNIVIVA",
        "short_description": "Mira el video completo en CogniViva.",
        "hashtags": "#Psicologia #Habitos #Emociones #Relaciones #Shorts",
        "category_id": "27",
        "colors": {
            "primary": (38, 190, 174),
            "accent": (255, 126, 95),
            "panel": (9, 38, 46),
        },
    },
}

CHANNEL_CHOICES = tuple(CHANNEL_PROFILES)


def normalize_channel_slug(value: str | None) -> str:
    slug = str(value or DEFAULT_CHANNEL).strip().lower().replace("-", "_")

    if slug not in CHANNEL_PROFILES:
        valid = ", ".join(CHANNEL_CHOICES)
        raise ValueError(f"Canal editorial no valido: {value!r}. Opciones: {valid}")

    return slug


def channel_profile(value: str | None) -> dict[str, Any]:
    slug = normalize_channel_slug(value)
    return {"slug": slug, **CHANNEL_PROFILES[slug]}


def default_niche(value: str | None) -> str:
    return str(channel_profile(value)["default_niche"])


def resolve_niche(value: str | None, niche: str | None) -> str:
    slug = normalize_channel_slug(value)
    text = " ".join(str(niche or "").split()).strip()
    nexon_default = default_niche(DEFAULT_CHANNEL)

    if not text or (slug != DEFAULT_CHANNEL and text == nexon_default):
        return default_niche(slug)

    return text


def strategy_profile_path(data_dir: Path, value: str | None) -> Path:
    slug = normalize_channel_slug(value)
    base = Path(data_dir) / "analytics"

    if slug == DEFAULT_CHANNEL:
        return base / "strategy_profile.json"

    return base / slug / "strategy_profile.json"


def experiments_directory(project_root: Path, value: str | None) -> Path:
    slug = normalize_channel_slug(value)
    base = Path(project_root) / "data" / "experiments"
    return base if slug == DEFAULT_CHANNEL else base / slug


def editorial_prompt(value: str | None) -> str:
    profile = channel_profile(value)
    priorities = "\n".join(
        f"- {topic};" for topic in profile["priority_topics"]
    )
    forbidden = "\n".join(
        f"- {topic};" for topic in profile["forbidden_topics"]
    )

    return (
        f"CANAL: {profile['display_name']}\n"
        f"MISION EDITORIAL: {profile['mission']}\n"
        f"PUBLICO: {profile['audience']}\n\n"
        f"TEMAS PRIORITARIOS:\n{priorities}\n\n"
        f"LIMITES EDITORIALES:\n{forbidden}"
    )
