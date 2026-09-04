from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from autotube.visuals.final_visual_auditor import (
    AuditorVisualFinal,
    _assets_fingerprint,
)


REPAIR_VERSION = "visual_repair_v3.6"


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


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", text).strip().lower()


def _append_unique(values: list[str], *new_values: str) -> list[str]:
    seen = {_normalized(value) for value in values if str(value).strip()}
    for value in new_values:
        cleaned = str(value).strip()
        identity = _normalized(cleaned)
        if cleaned and identity and identity not in seen:
            values.append(cleaned)
            seen.add(identity)
    return values


def _directed_historical_queries(element: dict[str, Any]) -> list[str]:
    """Produce consultas documentales precisas sin depender de otro LLM."""
    context = _normalized(
        " ".join(
            str(element.get(key, ""))
            for key in (
                "texto_pantalla",
                "descripcion",
                "concepto_central",
                "texto_narrado",
            )
        )
    )
    queries: list[str] = []

    if "john mccarthy" in context:
        _append_unique(
            queries,
            "John McCarthy computer scientist blackboard photograph",
            "John McCarthy Stanford blackboard archive",
            "John McCarthy artificial intelligence historical photograph",
        )

    if "tarjeta" in context and "perforad" in context:
        _append_unique(
            queries,
            "1950s punch card reader operator historical photograph",
            "IBM 711 punched card reader 1950s archive",
            "IBM punched card machine computer room operator",
        )

    if (
        ("computadora central" in context or "maquina" in context)
        and ("1950" in context or "anos cincuenta" in context)
    ):
        _append_unique(
            queries,
            "1950s mainframe computer operators historical photograph",
            "IBM 704 computer operators 1950s archive",
            "UNIVAC computer room operators 1950s photograph",
        )

    if "diagrama" in context and "flujo" in context:
        _append_unique(
            queries,
            "1950s computer scientists flowchart office historical photograph",
            "early computer programmers flowchart paper 1950s archive",
            "computer researchers continuous paper diagram 1950s",
        )

    if "dartmouth" in context and (
        "propuesta" in context or "manifiesto" in context or "documento" in context
    ):
        _append_unique(
            queries,
            "Dartmouth proposal artificial intelligence 1955 original document",
            "Dartmouth Summer Research Project on Artificial Intelligence proposal scan",
            "John McCarthy Dartmouth proposal 1955 document",
        )
    elif "dartmouth" in context and (
        "investigador" in context or "1956" in context or "fundador" in context
    ):
        _append_unique(
            queries,
            "1956 Dartmouth artificial intelligence workshop participants archive",
            "Dartmouth Summer Research Project Artificial Intelligence 1956 researchers",
            "John McCarthy Marvin Minsky Claude Shannon Nathaniel Rochester 1956",
        )

    screen_text = str(element.get("texto_pantalla", "")).strip()
    if screen_text:
        _append_unique(queries, f"{screen_text} historical archive")
    return queries


def _enrich_contract(element: dict[str, Any]) -> dict[str, Any]:
    """Completa contratos vacios y conserva cualquier criterio editorial previo."""
    enriched = copy.deepcopy(element)
    description = str(enriched.get("descripcion", "")).strip()
    context = _normalized(
        " ".join(
            (
                description,
                str(enriched.get("texto_pantalla", "")),
                str(enriched.get("texto_narrado", "")),
            )
        )
    )

    if not str(enriched.get("concepto_central", "")).strip():
        enriched["concepto_central"] = description

    criteria = enriched.get("criterios_obligatorios", [])
    criteria = (
        [str(value).strip() for value in criteria if str(value).strip()]
        if isinstance(criteria, list)
        else []
    )
    if description:
        _append_unique(criteria, description)
    screen_text = str(enriched.get("texto_pantalla", "")).strip()
    if "texto animado" in context and screen_text:
        _append_unique(
            criteria,
            f'El texto visible debe decir exactamente: "{screen_text}".',
            "La tipografia debe ser legible, central y ocupar el foco de la composicion.",
        )
        enriched["tipo_recurso"] = "texto_animado"
    enriched["criterios_obligatorios"] = criteria

    forbidden = enriched.get("elementos_prohibidos", [])
    forbidden = (
        [str(value).strip() for value in forbidden if str(value).strip()]
        if isinstance(forbidden, list)
        else []
    )
    _append_unique(
        forbidden,
        "Contenido generico sin relacion directa con la narracion.",
    )
    historical = any(
        token in context
        for token in (
            "archivo",
            "1950",
            "1955",
            "1956",
            "anos cincuenta",
            "historica",
        )
    )
    if historical:
        _append_unique(
            forbidden,
            "Tecnologia, ropa, oficinas o infraestructura modernas.",
            "Fotografia de stock contemporanea presentada como archivo historico.",
        )
    if "fotografia real" in context or "archivo real" in context:
        _append_unique(
            forbidden,
            "Ilustracion ficticia presentada como una fotografia real.",
        )
    enriched["elementos_prohibidos"] = forbidden

    alternatives = enriched.get("consultas_alternativas", [])
    alternatives = (
        [str(value).strip() for value in alternatives if str(value).strip()]
        if isinstance(alternatives, list)
        else []
    )
    alternatives = _append_unique(
        alternatives,
        *_directed_historical_queries(enriched),
    )
    enriched["consultas_alternativas"] = alternatives
    return enriched


def _apply_editorial_fallback(
    clip: dict[str, Any],
    round_number: int,
) -> dict[str, Any]:
    """Usa una tarjeta factual solo tras agotar dos rondas de archivo real."""
    if round_number < 3:
        return clip

    # Si una reparacion previa contamino el texto visible o la descripcion,
    # la descripcion editorial original es la fuente autoritativa. No se
    # mezclan nombres mencionados secundariamente en la narracion.
    contract_source = str(
        clip.get("descripcion_editorial_original", "")
        or clip.get("descripcion", "")
        or clip.get("texto_narrado", "")
        or clip.get("texto_pantalla", "")
    ).strip()
    context = _normalized(contract_source)
    screen = ""
    description = ""
    card_style = ""

    if (
        "modelo anatomico" in context
        and "cerebro humano" in context
    ):
        screen = "Cerebro y mente\nLa complejidad subestimada"
        description = (
            "Tarjeta documental animada sobre la complejidad del cerebro "
            "humano que los primeros investigadores de IA subestimaron."
        )
        card_style = "cerebro_anatomico_historico"
    elif (
        "tarjetas perforadas apiladas" in context
        or "cajas de almacenamiento de carton" in context
    ):
        screen = "Tarjetas perforadas\nDatos almacenados en papel"
        description = (
            "Tarjeta documental animada sobre el almacenamiento físico de "
            "datos mediante tarjetas perforadas organizadas en cajas."
        )
        card_style = "tarjetas_perforadas_archivadas"
    elif "logic theorist" in context or (
        "allen newell" in context
        and "impresiones de software logico" in context
    ):
        screen = "Logic Theorist\nNewell + Simon · 1956"
        description = (
            "Tarjeta documental animada que identifica Logic Theorist, de "
            "Allen Newell y Herbert Simon, como programa pionero de 1956."
        )
        card_style = "logic_theorist_1956"
    elif (
        "listados de codigo fuente impresos" in context
        or ("papel continuo" in context and "1956" in context)
    ):
        screen = "Código impreso · 1956\nEl primer programa de IA"
        description = (
            "Tarjeta documental animada sobre los listados impresos del "
            "software lógico pionero presentado en 1956."
        )
        card_style = "codigo_impreso_1956"
    elif "principia mathematica" in context:
        screen = "Principia Mathematica\nTeoremas demostrados por máquina"
        description = (
            "Tarjeta documental animada sobre los teoremas de Principia "
            "Mathematica demostrados por Logic Theorist."
        )
        card_style = "principia_mathematica"
    elif (
        "auditorio universitario" in context
        and "conferencia cientifica" in context
    ):
        screen = "Conferencia científica\nLa IA gana respaldo"
        description = (
            "Tarjeta documental animada sobre el respaldo académico e "
            "institucional obtenido por la inteligencia artificial."
        )
        card_style = "auditorio_cientifico_1950"
    elif (
        "documentos de financiacion" in context
        or "oficina de la administracion universitaria" in context
    ):
        screen = "Financiamiento científico\nComienza una nueva etapa"
        description = (
            "Tarjeta documental animada sobre el inicio de una etapa de "
            "financiamiento y entusiasmo institucional por la IA."
        )
        card_style = "financiamiento_ia_inicial"
    elif "lectora de tarjetas perforadas" in context:
        screen = "Tarjetas perforadas\nLectura de datos · años 50"
        description = (
            "Tarjeta documental animada que explica la lectura de datos "
            "mediante tarjetas perforadas en las computadoras de los años cincuenta."
        )
        card_style = "lectora_tarjetas_perforadas"
    elif (
        "investigador operando los interruptores" in context
        and "computadora central" in context
    ):
        screen = "Computadora central · años 50\nOperación mediante interruptores"
        description = (
            "Tarjeta documental animada sobre la operación manual de una "
            "computadora central histórica mediante interruptores."
        )
        card_style = "operador_mainframe_interruptores"
    elif "reglas logicas simbolicas" in context:
        screen = "Reglas simbólicas\nFormalizar la cognición"
        description = (
            "Tarjeta documental animada que representa reglas lógicas "
            "simbólicas como modelo formal de la cognición."
        )
        card_style = "diagrama_reglas_simbolicas"
    elif "luces parpadeantes" in context and "consola central" in context:
        screen = "Consola central\nProcesamiento en marcha"
        description = (
            "Tarjeta documental animada que representa la actividad de una "
            "consola central histórica durante el procesamiento."
        )
        card_style = "consola_mainframe_luces"
    elif "norbert wiener" in context:
        screen = "Norbert Wiener\nCibernética: control y comunicación"
        description = (
            "Tarjeta documental animada que identifica a Norbert Wiener y "
            "su relación con la cibernética, el control y la comunicación."
        )
        card_style = "perfil_wiener"
    elif (
        "componentes electronicos antiguos" in context
        or "procesando senales electricas" in context
    ):
        screen = "Señales eléctricas\nComponentes y circuitos de época"
        description = (
            "Tarjeta documental animada sobre componentes electrónicos "
            "históricos procesando señales eléctricas en laboratorio."
        )
        card_style = "componentes_electronicos_historicos"
    elif "revista cientifica" in context and "maquinas pensantes" in context:
        screen = "Máquinas pensantes\nDebate científico · años 50"
        description = (
            "Tarjeta documental animada sobre el debate científico de los "
            "años cincuenta acerca de las máquinas pensantes."
        )
        card_style = "revista_maquinas_pensantes"
    elif "libro clasico" in context and (
        "filosofia" in context or "tecnologia" in context
    ):
        screen = "Impacto filosófico\nMáquinas, mente y sociedad"
        description = (
            "Tarjeta documental animada sobre el impacto filosófico y social "
            "de atribuir inteligencia a una máquina."
        )
        card_style = "libro_filosofia_tecnologia"
    elif (
        "investigadores" in context
        and "mesa" in context
        and ("aire libre" in context or "campus de dartmouth" in context)
    ):
        screen = "Dartmouth · verano de 1956\nIdeas alrededor de una mesa"
        description = (
            "Tarjeta documental animada sobre los debates colaborativos del "
            "taller de Dartmouth durante el verano de 1956."
        )
        card_style = "mesa_dartmouth_exterior"
    elif "tablero de ajedrez" in context and (
        "computadora central" in context or "anos 50" in context
    ):
        screen = "El optimismo inicial\nAjedrez + computadora"
        description = (
            "Tarjeta documental animada sobre el ajedrez como desafío "
            "temprano para la inteligencia artificial."
        )
        card_style = "ajedrez_computadora_historica"
    elif "john mccarthy" in context:
        screen = "John McCarthy\nPadre de la Inteligencia Artificial"
        description = (
            "Tarjeta documental animada que identifica claramente a John "
            "McCarthy y su papel fundador en la inteligencia artificial."
        )
        card_style = "perfil_mccarthy"
    elif "marvin minsky" in context:
        screen = "Marvin Minsky\nPionero de la IA · MIT"
        description = (
            "Tarjeta documental animada que identifica a Marvin Minsky como "
            "pionero de la inteligencia artificial vinculado al MIT."
        )
        card_style = "perfil_minsky"
    elif "allen newell" in context or "herbert simon" in context:
        screen = "Newell + Simon\nRazonamiento simbólico"
        description = (
            "Tarjeta documental animada que identifica a Allen Newell y "
            "Herbert Simon y su trabajo en razonamiento simbólico."
        )
        card_style = "dupla_newell_simon"
    elif "claude shannon" in context:
        screen = "Claude Shannon\nInformación, lógica y máquinas"
        description = (
            "Tarjeta documental animada que identifica a Claude Shannon y "
            "su vínculo con la teoría de la información y la lógica."
        )
        card_style = "perfil_shannon"
    elif (
        "electromecan" in context
        or ("rele" in context and "cable" in context)
        or "sistema automatizado" in context
    ):
        screen = "Relés + cables\nAutomatización electromecánica"
        description = (
            "Tarjeta documental animada que explica la automatización "
            "electromecánica mediante relés y cableado de época."
        )
        card_style = "circuito_electromecanico"
    elif (
        "academico" in context
        and ("mesa" in context or "conferencia" in context)
    ):
        screen = "Dartmouth 1956\nIdeas alrededor de una mesa"
        description = (
            "Tarjeta documental animada que representa el carácter académico "
            "y colaborativo del taller de Dartmouth de 1956."
        )
        card_style = "mesa_dartmouth"
    elif "dartmouth" in context and (
        "investigador" in context or "fundador" in context or "1956" in context
    ) and not any(
        token in context for token in ("propuesta", "manifiesto", "documento")
    ):
        screen = "Dartmouth 1956\nMcCarthy · Minsky · Rochester · Shannon"
        description = (
            "Tarjeta documental animada de Dartmouth 1956 con los nombres de "
            "los cuatro investigadores vinculados a la propuesta fundacional."
        )
        card_style = "fundadores_dartmouth"
    elif "diagrama" in context and "flujo" in context:
        screen = "1956\nDescribir la inteligencia para poder simularla"
        description = (
            "Tarjeta documental animada que representa la idea central de "
            "describir formalmente la inteligencia para simularla en una maquina."
        )
        card_style = "flujo_inteligencia"
    elif "dartmouth" in context and any(
        token in context for token in ("propuesta", "manifiesto", "documento")
    ):
        screen = "Dartmouth, 1955\nPropuesta fundacional de la IA"
        description = (
            "Tarjeta documental animada que identifica la propuesta de Dartmouth "
            "de 1955 como documento fundacional de la inteligencia artificial."
        )
        card_style = "documento_dartmouth"

    if not screen:
        return clip

    original_description = str(
        clip.get("descripcion_editorial_original", "")
        or clip.get("descripcion", "")
    )
    clip["descripcion_editorial_original"] = original_description
    clip["tipo_recurso"] = "texto_animado"
    clip["estilo_tarjeta"] = card_style or _event_id(clip)
    clip["texto_pantalla"] = screen
    clip["descripcion"] = description
    clip["concepto_central"] = description
    visible_phrases = [
        phrase.strip()
        for phrase in screen.splitlines()
        if phrase.strip()
    ]
    clip["criterios_obligatorios"] = [
        description,
        (
            "El texto visible debe incluir todas estas frases: "
            + "; ".join(f'"{phrase}"' for phrase in visible_phrases)
            + ". Pueden aparecer en lineas distintas y no requieren barras "
            "ni otros caracteres separadores."
        ),
        "La tarjeta debe ser legible, especifica y directamente vinculada a la narracion.",
    ]
    clip["elementos_prohibidos"] = [
        "Fotografia de stock generica o contemporanea.",
        "Personas, documentos u objetos presentados falsamente como archivo real.",
        "Contenido sin los nombres, fecha o concepto historico solicitado.",
    ]
    clip["consultas_alternativas"] = []
    clip["busqueda_en"] = ""
    clip["busqueda_es"] = ""
    clip["fallback_editorial"] = {
        "version": REPAIR_VERSION,
        "round": round_number,
        "reason": (
            "Dos rondas de busqueda de archivo real no produjeron un recurso "
            "aprobado; se usa una tarjeta factual, nunca stock falso."
        ),
        "descripcion_original": original_description,
    }
    return clip


def _repair_clip(element: dict[str, Any], round_number: int) -> dict[str, Any]:
    """Reconstruye un clip sin reutilizar metadata de la descarga rechazada."""
    clip = _enrich_contract(element)
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
    historical = any(
        token in _normalized(clip.get("descripcion", ""))
        for token in ("archivo", "1950", "1955", "1956", "anos 50")
    )
    if original_type == "video_stock" and (round_number >= 2 or historical):
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
    clip["busqueda_en"] = alternatives[0] if alternatives else ""
    clip["busqueda_es"] = ""
    clip["_repair_original_type"] = original_type
    return _apply_editorial_fallback(clip, round_number)


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
        start_round: int = 1,
    ) -> dict[str, Any]:
        assets_file = Path(assets_path).expanduser().resolve()
        if not assets_file.is_file():
            raise VisualRepairError(f"No existe el manifiesto visual: {assets_file}")
        if attempts < 1 or attempts > 5:
            raise VisualRepairError("Los intentos deben estar entre 1 y 5.")
        if start_round < 1 or start_round > 5:
            raise VisualRepairError("La ronda inicial debe estar entre 1 y 5.")
        if start_round + attempts - 1 > 5:
            raise VisualRepairError(
                "La ronda inicial mas los intentos no puede superar la ronda 5."
            )

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
        intermediate_audits: list[str] = []
        required_assets = int(initial_audit.get("audited_assets", 0) or 0)
        if limit > 0:
            required_assets = min(required_assets or limit, limit)
        last_round = start_round + attempts - 1

        for round_number in range(start_round, start_round + attempts):
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

            approved_this_round: set[str] = set()
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
                    "descripcion",
                    "descripcion_editorial_original",
                    "concepto_central",
                    "criterios_obligatorios",
                    "elementos_prohibidos",
                    "consultas_alternativas",
                    "texto_pantalla",
                    "estilo_tarjeta",
                    "fallback_editorial",
                ):
                    if key in candidate:
                        updated[key] = copy.deepcopy(candidate[key])
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
                approved_this_round.add(event_id)

            # Un candidato puede aprobarse de forma aislada y aun asi fallar
            # cuando se vuelve a auditar dentro de la coleccion real. Antes de
            # avanzar a la siguiente estrategia, reconstruimos el manifiesto
            # completo y reincorporamos esos falsos positivos a ``remaining``.
            if approved_this_round and round_number < last_round:
                validation_manifest = copy.deepcopy(manifest)
                validation_manifest["elementos"] = [
                    replacements.get(_event_id(item), item)
                    if isinstance(item, dict)
                    else item
                    for item in elements
                ]
                validation_path = round_dir / "round_validation_manifest.json"
                _write_json_atomic(validation_path, validation_manifest)
                validation_audit = self.auditor.audit(
                    assets_path=validation_path,
                    channel_slug=channel_slug,
                    limit=max(0, required_assets),
                )
                intermediate_audits.append(str(validation_audit.get("path", "")))
                validation_status = {
                    str(item.get("id", "")): bool(item.get("approved"))
                    for item in validation_audit.get("elements", [])
                    if isinstance(item, dict)
                }
                for event_id in rejected_audit:
                    if validation_status.get(event_id) is True:
                        remaining.pop(event_id, None)
                        continue
                    # No conservar como reemplazo definitivo un candidato que
                    # la auditoria integral rechazo o no pudo comprobar.
                    replacements.pop(event_id, None)
                    if event_id in by_id:
                        remaining[event_id] = by_id[event_id]

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
            "intermediate_audits": intermediate_audits,
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
