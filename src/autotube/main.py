from __future__ import annotations

import argparse
from pathlib import Path

from autotube.ai.gemini_client import GeminiClient
from autotube.audio.voice_generator import (
    GeneradorVoz,
    cargar_guion_audio,
)
from autotube.visuals.visual_planner import (
    PlanificadorVisual,
    cargar_contexto_visual,
)
from autotube.visuals.asset_collector import (
    RecolectorRecursos,
    cargar_plan_visual,
)
from autotube.visuals.local_asset_generator import (
    GeneradorRecursosLocales,
    cargar_manifiesto_assets,
)
from autotube.visuals.final_visual_auditor import (
    AuditorVisualFinal,
    find_compatible_audit,
)
from autotube.video.composer import (
    CompositorVideo,
    cargar_contexto_render,
    cargar_timeline_render,
)
from autotube.video.subtitle_generator import (
    GeneradorSubtitulos,
    cargar_audio_para_subtitulos,
)
from autotube.timeline.semantic_timeline import (
    GeneradorTimelineSemantica,
)
from autotube.video.finalizer import FinalizadorVideo
from autotube.video.shorts_generator import GeneradorShorts
# SHORTS_AUTOMATICOS_INTEGRADOS_V1
from autotube.content.youtube_metadata import GeneradorMetadataYouTube
from autotube.content.thumbnail_generator import GeneradorMiniaturaYouTube
from autotube.visuals.tutorial_capture import (
    CapturadorTutorial,
    cargar_manifiesto_tutorial,
)
from autotube.content.ideas_generator import (
    NICHO_PREDETERMINADO,
    GeneradorIdeas,
)
from autotube.content.channel_profiles import (
    CHANNEL_CHOICES,
    DEFAULT_CHANNEL,
    channel_profile,
    resolve_niche,
)
from autotube.content.script_generator import (
    GeneradorGuiones,
    cargar_idea,
)
from autotube.content.script_validator import (
    imprimir_reporte,
    validar_archivo_guion,
)
from autotube.content.script_fixer import (
    ReparadorGuiones,
    cargar_guion_para_correccion,
)
from autotube.core.config import load_settings
from autotube.core.health import ejecutar_diagnostico
from autotube.core.logging_config import configure_logging
from autotube.core.security import ejecutar_revision_seguridad
from autotube.operations.channel_runtime import (
    incomplete_other_channel_states,
    migrate_legacy_pipeline_state,
    pipeline_state_path,
)


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autotube",
        description="Sistema automatizado de producción para YouTube.",
    )

    subcomandos = parser.add_subparsers(dest="comando")

    subcomandos.add_parser(
        "doctor",
        help="Comprueba los requisitos y la estructura del proyecto.",
    )

    subcomandos.add_parser(
        "info",
        help="Muestra la configuración sin revelar claves privadas.",
    )

    subcomandos.add_parser(
        "security",
        help="Comprueba la protección de claves y credenciales.",
    )

    subcomandos.add_parser(
        "gemini-test",
        help="Comprueba la conexión real con Gemini.",
    )

    ideas_parser = subcomandos.add_parser(
        "ideas",
        help="Genera ideas estructuradas para videos.",
    )

    ideas_parser.add_argument(
        "--nicho",
        default=NICHO_PREDETERMINADO,
        help="Nicho para el cual se generarán las ideas.",
    )

    ideas_parser.add_argument(
        "--cantidad",
        type=int,
        default=5,
        help="Cantidad de ideas, entre 1 y 20.",
    )

    ideas_parser.add_argument(
        "--idioma",
        default="español",
        help="Idioma de las ideas generadas.",
    )

    ideas_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Perfil editorial para las ideas.",
    )

    script_parser = subcomandos.add_parser(
        "script",
        help="Genera un guion desde una idea guardada.",
    )

    script_parser.add_argument(
        "--indice",
        type=int,
        default=1,
        help="Número de la idea que se utilizará.",
    )

    script_parser.add_argument(
        "--archivo",
        default=None,
        help="Archivo JSON de ideas. Por defecto usa el más reciente.",
    )

    script_parser.add_argument(
        "--idioma",
        default="español",
        help="Idioma del guion generado.",
    )

    script_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Perfil editorial para el guion.",
    )

    check_parser = subcomandos.add_parser(
        "script-check",
        help="Comprueba la duración y calidad de un guion.",
    )

    check_parser.add_argument(
        "--archivo",
        default=None,
        help="Archivo de guion. Por defecto usa el más reciente.",
    )

    check_parser.add_argument(
        "--ppm",
        type=int,
        default=145,
        help="Velocidad estimada de narración en palabras por minuto.",
    )

    fix_parser = subcomandos.add_parser(
        "script-fix",
        help="Expande y corrige un guion demasiado corto.",
    )

    fix_parser.add_argument(
        "--archivo",
        default=None,
        help="Archivo de guion. Por defecto usa el más reciente.",
    )

    fix_parser.add_argument(
        "--ppm",
        type=int,
        default=145,
        help="Velocidad objetivo en palabras por minuto.",
    )

    fix_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Perfil editorial que se conservara.",
    )

    voice_parser = subcomandos.add_parser(
        "voice",
        help="Genera la narración completa del guion.",
    )

    voice_parser.add_argument(
        "--archivo",
        default=None,
        help="Archivo de guion. Por defecto usa el más reciente.",
    )

    voice_parser.add_argument(
        "--voz",
        default="es-MX-JorgeNeural",
        help="Voz utilizada por Edge TTS.",
    )

    voice_parser.add_argument(
        "--velocidad",
        default="-2%",
        help="Velocidad de la narración.",
    )

    voice_parser.add_argument(
        "--tono",
        default="-1Hz",
        help="Ajuste del tono de voz.",
    )

    visual_parser = subcomandos.add_parser(
        "visual-plan",
        help="Crea un plan visual sincronizado con la narración.",
    )

    visual_parser.add_argument(
        "--guion",
        default=None,
        help="Archivo de guion. Por defecto usa el del audio.",
    )

    visual_parser.add_argument(
        "--manifiesto",
        default=None,
        help="Manifiesto de audio. Por defecto usa el más reciente.",
    )

    visual_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal propietario del plan visual.",
    )

    assets_parser = subcomandos.add_parser(
        "assets",
        help="Descarga recursos de Pixabay para el plan visual.",
    )

    assets_parser.add_argument(
        "--plan",
        default=None,
        help="Plan visual. Por defecto usa el más reciente.",
    )

    assets_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal propietario de los recursos visuales.",
    )

    assets_parser.add_argument(
        "--limite",
        type=int,
        default=6,
        help=(
            "Cantidad máxima de archivos a descargar. "
            "Usa 0 para procesar el plan completo."
        ),
    )

    local_parser = subcomandos.add_parser(
        "local-assets",
        help="Genera gráficos, interfaces y textos localmente.",
    )

    local_parser.add_argument(
        "--manifiesto",
        default=None,
        help="Manifiesto de recursos. Usa el más reciente por defecto.",
    )

    local_parser.add_argument(
        "--forzar",
        action="store_true",
        help="Vuelve a generar recursos locales existentes.",
    )

    local_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal propietario de la coleccion visual.",
    )

    timeline_parser = subcomandos.add_parser(
        "timeline",
        help=(
            "Crea y valida la timeline semantica antes del render."
        ),
    )

    timeline_parser.add_argument(
        "--assets",
        default=None,
        help="Manifiesto visual. Usa el mas reciente por defecto.",
    )

    timeline_parser.add_argument(
        "--audio",
        default=None,
        help="Manifiesto de audio. Usa el mas reciente por defecto.",
    )

    timeline_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal propietario de la produccion.",
    )

    visual_audit_parser = subcomandos.add_parser(
        "visual-audit",
        help="Audita los pixeles y fotogramas reales antes del render.",
    )
    visual_audit_parser.add_argument(
        "--assets",
        default=None,
        help="Manifiesto visual. Usa el mas reciente por defecto.",
    )
    visual_audit_parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Cantidad de recursos a auditar; 0 audita la coleccion completa.",
    )
    visual_audit_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal propietario de la produccion.",
    )

    render_parser = subcomandos.add_parser(
        "render",
        help="Combina los recursos visuales con la narración.",
    )

    render_parser.add_argument(
        "--assets",
        default=None,
        help="Manifiesto de recursos. Usa el más reciente por defecto.",
    )

    render_parser.add_argument(
        "--audio",
        default=None,
        help="Manifiesto de audio. Usa el más reciente por defecto.",
    )

    render_parser.add_argument(
        "--timeline",
        default=None,
        help="Timeline aprobada. Busca la compatible si se omite.",
    )

    render_parser.add_argument(
        "--visual-audit",
        default=None,
        help="Auditoria visual aprobada. Busca la compatible si se omite.",
    )

    render_parser.add_argument(
        "--preview",
        action="store_true",
        help="Genera una vista previa rápida en 1280x720.",
    )

    render_parser.add_argument(
        "--limite-clips",
        type=int,
        default=None,
        help=(
            "Número de clips a procesar. "
            "La vista previa usa 8 por defecto."
        ),
    )

    render_parser.add_argument(
        "--conservar-temporales",
        action="store_true",
        help="Conserva los clips intermedios del render.",
    )

    render_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal propietario de los recursos del render.",
    )

    visual_cache_parser = subcomandos.add_parser(
        "visual-cache",
        help="Guarda, restaura o libera visuales mediante Google Drive.",
    )
    visual_cache_parser.add_argument(
        "accion",
        choices=["store", "restore", "cleanup", "status"],
    )
    visual_cache_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
    )
    visual_cache_parser.add_argument("--manifiesto", default=None)
    visual_cache_parser.add_argument("--dry-run", action="store_true")
    visual_cache_parser.add_argument("--confirmar", action="store_true")

    code_backup_parser = subcomandos.add_parser(
        "code-backup",
        help="Respalda en Google Drive el commit actual sin credenciales.",
    )
    code_backup_parser.add_argument(
        "--version",
        default=None,
        help="Version del respaldo; usa la etiqueta Git si se omite.",
    )
    code_backup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida el respaldo sin crear archivos ni usar Google Drive.",
    )
    code_backup_parser.add_argument(
        "--carpeta-raiz",
        default="NEXON IA - AutoTube AI",
        help="Carpeta raiz de AutoTube AI en Google Drive.",
    )

    subtitles_parser = subcomandos.add_parser(
        "subtitles",
        help="Genera subtítulos SRT sincronizados con la voz.",
    )

    subtitles_parser.add_argument(
        "--audio",
        default=None,
        help="Manifiesto de audio. Usa el más reciente por defecto.",
    )

    subtitles_parser.add_argument(
        "--max-palabras",
        type=int,
        default=12,
        help="Máximo de palabras por subtítulo.",
    )

    subtitles_parser.add_argument(
        "--max-caracteres",
        type=int,
        default=74,
        help="Máximo de caracteres por subtítulo.",
    )


    dashboard_parser = subcomandos.add_parser(
        "dashboard",
        help=(
            "Genera el centro de control operativo "
            "de AutoTube AI."
        ),
    )

    dashboard_parser.add_argument(
        "--abrir",
        action="store_true",
        help="Abre el panel HTML en el navegador.",
    )

    dashboard_parser.add_argument(
        "--en-vivo",
        action="store_true",
        help=(
            "Actualiza automaticamente el panel "
            "mientras el comando permanece activo."
        ),
    )

    dashboard_parser.add_argument(
        "--intervalo",
        type=int,
        default=30,
        help=(
            "Segundos entre actualizaciones "
            "del panel en vivo."
        ),
    )



    storage_parser = subcomandos.add_parser(
        "storage-clean",
        help=(
            "Audita y elimina salidas regenerables "
            "sin tocar producciones protegidas."
        ),
    )

    storage_parser.add_argument(
        "--confirmar",
        action="store_true",
        help=(
            "Elimina realmente los candidatos seguros. "
            "Sin esta opcion solo se simula."
        ),
    )


    storage_parser.add_argument(
        "--publicados",
        action="store_true",
        help=(
            "Incluye MP4 publicados cuyo video_id "
            "y SHA256 hayan sido verificados."
        ),
    )

    guardian_parser = subcomandos.add_parser(
        "guardian-run",
        help=(
            "Ejecuta el pipeline autonomo con preflight, "
            "bloqueo y reanudacion segura."
        ),
    )

    guardian_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el plan sin ejecutar el pipeline.",
    )

    guardian_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal que producira o reanudara el Guardian.",
    )

    guardian_parser.add_argument(
        "--sin-publicar",
        action="store_true",
        help="Produce contenido sin publicar en YouTube.",
    )

    guardian_parser.add_argument(
        "--sin-control-profundo",
        action="store_true",
        help="Omite el analisis multimedia profundo.",
    )


    guardian_parser.add_argument(
        "--sin-limpiar-publicados",
        action="store_true",
        help=(
            "Conserva los MP4 locales despues "
            "de publicarlos."
        ),
    )

    scheduler_parser = subcomandos.add_parser(
        "scheduler",
        help=(
            "Administra la tarea automatica del "
            "Programador de Windows."
        ),
    )

    scheduler_parser.add_argument(
        "--accion",
        choices=(
            "estado",
            "instalar",
            "eliminar",
        ),
        default="estado",
        help="Operacion que se realizara sobre la tarea.",
    )

    scheduler_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal cuya tarea programada se administrara.",
    )

    scheduler_parser.add_argument(
        "--hora",
        default="08:00",
        help="Hora de inicio en formato HH:MM.",
    )

    scheduler_parser.add_argument(
        "--dias",
        default="lunes,miercoles,viernes",
        help="Dias semanales separados por comas.",
    )

    scheduler_parser.add_argument(
        "--confirmar",
        action="store_true",
        help=(
            "Confirma la instalacion o eliminacion real. "
            "Sin esta opcion solo se simula."
        ),
    )

    encoder_check_parser = subcomandos.add_parser(
        "encoder-check",
        help=(
            "Comprueba Quick Sync y muestra "
            "el codificador elegido por etapa."
        ),
    )

    encoder_check_parser.add_argument(
        "--reprobar",
        action="store_true",
        help="Repite la prueba real de Quick Sync.",
    )

    media_check_parser = subcomandos.add_parser(
        "media-check",
        help=(
            "Valida video, audio, subtitulos, "
            "miniatura y metadata."
        ),
    )

    media_check_parser.add_argument(
        "--validar-shorts",
        action="store_true",
        help="Valida tambien el lote de Shorts reciente.",
    )

    media_check_parser.add_argument(
        "--manifiesto-shorts",
        default=None,
        help="Ruta opcional del shorts_manifest.json.",
    )

    media_check_parser.add_argument(
        "--profundo",
        action="store_true",
        help=(
            "Busca tramos negros, silencios "
            "y niveles anormales de audio."
        ),
    )

    analytics_parser = subcomandos.add_parser(
        "analytics",
        help="Genera un informe de rendimiento de YouTube Analytics.",
    )

    analytics_parser.add_argument(
        "--dias",
        type=int,
        default=28,
        help="Cantidad de dias que se analizaran.",
    )

    analytics_parser.add_argument(
        "--max-videos",
        type=int,
        default=50,
        help="Cantidad maxima de videos incluidos.",
    )

    analytics_parser.add_argument(
        "--canal",
        choices=["nexon_ia", "cogniviva"],
        default="nexon_ia",
        help="Perfil de YouTube que se analizara.",
    )

    publish_status_parser = subcomandos.add_parser(
        "publish-status",
        help="Muestra el estado actual de la cola de YouTube.",
    )

    publish_status_parser.add_argument(
        "--canal",
        choices=["nexon_ia", "cogniviva"],
        default="nexon_ia",
        help="Perfil de YouTube que se consultara.",
    )

    publish_queue_parser = subcomandos.add_parser(
        "publish-queue",
        help="Sincroniza archivos y publicaciones con la cola.",
    )

    publish_queue_parser.add_argument(
        "--canal",
        choices=["nexon_ia", "cogniviva"],
        default="nexon_ia",
        help="Perfil de YouTube que se sincronizara.",
    )

    publish_resume_parser = subcomandos.add_parser(
        "publish-resume",
        help="Reanuda las publicaciones pendientes de YouTube.",
    )

    publish_resume_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la reanudacion sin subir videos.",
    )

    publish_resume_parser.add_argument(
        "--canal",
        choices=["nexon_ia", "cogniviva"],
        default="nexon_ia",
        help="Perfil de YouTube que se reanudara.",
    )

    analytics_insights_parser = subcomandos.add_parser(
        "analytics-insights",
        help=(
            "Convierte Analytics en recomendaciones "
            "para proximos contenidos."
        ),
    )

    analytics_insights_parser.add_argument(
        "--reporte",
        default=None,
        help="Informe JSON; usa el mas reciente por defecto.",
    )

    analytics_insights_parser.add_argument(
        "--canal",
        choices=["nexon_ia", "cogniviva"],
        default="nexon_ia",
        help="Perfil editorial que recibira los insights.",
    )

    experiment_parser = subcomandos.add_parser(
        "experiment",
        help=(
            "Genera variantes A/B editoriales "
            "sin modificar publicaciones."
        ),
    )

    experiment_parser.add_argument(
        "--variable",
        choices=[
            "titulo",
            "miniatura",
            "gancho",
            "duracion",
        ],
        default="titulo",
        help="Unica variable que cambiara el experimento.",
    )

    experiment_parser.add_argument(
        "--cantidad",
        type=int,
        default=3,
        help="Cantidad de variantes, incluyendo el control A.",
    )

    experiment_parser.add_argument(
        "--sin-miniaturas",
        action="store_true",
        help="No renderiza imagenes en experimentos de miniatura.",
    )

    experiment_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal del experimento editorial.",
    )

    experiment_result_parser = subcomandos.add_parser(
        "experiment-result",
        help="Registra metricas de una variante experimental.",
    )

    experiment_result_parser.add_argument(
        "--codigo",
        required=True,
        choices=["A", "B", "C", "D", "E"],
        help="Codigo de la variante evaluada.",
    )

    experiment_result_parser.add_argument(
        "--vistas",
        required=True,
        type=int,
        help="Visualizaciones acumuladas de la variante.",
    )

    experiment_result_parser.add_argument(
        "--ctr",
        type=float,
        default=None,
        help="CTR de impresiones expresado como porcentaje.",
    )

    experiment_result_parser.add_argument(
        "--retencion",
        type=float,
        default=None,
        help="Porcentaje medio de visualizacion.",
    )

    experiment_result_parser.add_argument(
        "--duracion-media",
        type=float,
        default=None,
        help="Duracion media de visualizacion en segundos.",
    )

    experiment_result_parser.add_argument(
        "--minutos-vistos",
        type=float,
        default=None,
        help="Minutos de reproduccion acumulados.",
    )

    experiment_result_parser.add_argument(
        "--experimento",
        default=None,
        help="Archivo JSON; usa el experimento actual por defecto.",
    )

    experiment_result_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal del experimento evaluado.",
    )

    shorts_parser = subcomandos.add_parser(
        "shorts",
        help="Genera Shorts verticales desde el documental mas reciente.",
    )

    shorts_parser.add_argument(
        "--cantidad",
        type=int,
        default=4,
        help="Cantidad de Shorts que se generaran.",
    )

    shorts_parser.add_argument(
        "--duracion",
        type=float,
        default=42.0,
        help="Duracion aproximada de cada Short.",
    )

    shorts_parser.add_argument(
        "--solo-plan",
        action="store_true",
        help="Selecciona los fragmentos sin renderizar videos.",
    )

    shorts_parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Marca y perfil editorial de los Shorts.",
    )

    run_parser = subcomandos.add_parser(
        "run",
        help="Ejecuta autom?ticamente el pipeline completo de producci?n.",
    )

    run_parser.add_argument(
        "--nicho",
        default=NICHO_PREDETERMINADO,
        help="Nicho o tema general para generar las ideas.",
    )

    run_parser.add_argument(
        "--cantidad-ideas",
        type=int,
        default=5,
        help="Cantidad de ideas iniciales que generar? Gemini.",
    )

    run_parser.add_argument(
        "--indice",
        type=int,
        default=1,
        help="Idea que se utilizar? para producir el video.",
    )

    run_parser.add_argument(
        "--voz",
        default="es-MX-JorgeNeural",
        help="Voz utilizada por Edge TTS.",
    )

    run_parser.add_argument(
        "--velocidad",
        default="-2%",
        help="Velocidad de narraci?n.",
    )

    run_parser.add_argument(
        "--tono",
        default="-1Hz",
        help="Tono de narraci?n.",
    )

    run_parser.add_argument(
        "--canal",
        choices=["nexon_ia", "cogniviva"],
        default="nexon_ia",
        help="Canal de YouTube de destino.",
    )

    run_parser.add_argument(
        "--omitir-doctor",
        action="store_true",
        help="No ejecuta la comprobaci?n inicial del proyecto.",
    )


    run_parser.add_argument(
        "--control-profundo",
        action="store_true",
        help=(
            "Ejecuta el control multimedia profundo "
            "antes de publicar."
        ),
    )


    run_parser.add_argument(
        "--sin-publicar",
        action="store_true",
        help="Completa el video pero no lo sube a YouTube.",
    )

    run_parser.add_argument(
        "--reanudar",
        action="store_true",
        help="Contin?a desde el ?ltimo paso completado.",
    )

    run_parser.add_argument(
        "--regenerar-visuales",
        action="store_true",
        help=(
            "Con --reanudar conserva guion y voz, pero repite "
            "plan visual, recursos, render y subtitulos."
        ),
    )

    run_parser.add_argument(
        "--conservar-visuales-locales",
        action="store_true",
        help=(
            "Conserva los recursos visuales locales despues del respaldo. "
            "Por defecto se liberan tras verificar Google Drive."
        ),
    )


    run_parser.add_argument(
        "--sin-shorts",
        action="store_true",
        help="Omite la generacion automatica de Shorts.",
    )

    run_parser.add_argument(
        "--cantidad-shorts",
        type=int,
        default=4,
        help="Cantidad de Shorts generados por documental.",
    )

    run_parser.add_argument(
        "--duracion-short",
        type=float,
        default=42.0,
        help="Duracion aproximada de cada Short.",
    )

    tutorial_parser = subcomandos.add_parser(
        "tutorial-capture",
        help="Captura interfaces web reales para tutoriales.",
    )

    tutorial_parser.add_argument(
        "--manifiesto",
        default=None,
    )

    tutorial_parser.add_argument(
        "--login",
        default=None,
        choices=[
            "make",
            "chatgpt",
            "openai",
            "gmail",
            "n8n",
            "supabase",
            "notion",
            "claude",
            "cursor",
            "v0",
            "heygen",
            "elevenlabs",
        ],
    )

    tutorial_parser.add_argument(
        "--forzar",
        action="store_true",
    )

    tutorial_parser.add_argument(
        "--limite",
        type=int,
        default=0,
    )

    tutorial_parser.add_argument(
        "--mostrar-navegador",
        action="store_true",
    )

    return parser


def mostrar_informacion() -> None:
    """Muestra un resumen seguro de la configuración."""
    settings = load_settings()

    print("\nINFORMACIÓN DE AUTOTUBE AI")
    print("=" * 60)
    print(f"Proyecto: {settings.project_root}")
    print(f"Entorno: {settings.environment}")
    print(f"Nivel de logs: {settings.log_level}")
    print(f"Datos: {settings.data_dir}")
    print(f"Salidas: {settings.output_dir}")
    print(f"Registros: {settings.logs_dir}")

    print(
        "Gemini API: "
        + ("Configurada" if settings.gemini_api_key else "Pendiente")
    )

    print(
        "Pixabay API: "
        + ("Configurada" if settings.pixabay_api_key else "Pendiente")
    )

    if settings.youtube_is_configured:
        print("YouTube: Configurado")
    else:
        print(
            "YouTube: Pendiente; falta el archivo "
            f"{settings.youtube_client_secret_path}"
        )

    print("=" * 60)


def probar_gemini() -> None:
    """Comprueba la conexión utilizando el cliente interno."""
    print("\nPRUEBA DE GEMINI")
    print("=" * 60)

    cliente = GeminiClient()
    respuesta = cliente.probar_conexion()

    print(f"Modelo configurado: {cliente.model}")
    print(f"Modelo utilizado: {cliente.last_model_used}")
    print(f"Respuesta: {respuesta}")
    print("=" * 60)
    print("Gemini está conectado correctamente.")


def generar_ideas(argumentos: argparse.Namespace) -> None:
    """Genera, muestra y guarda ideas para videos."""
    settings = load_settings()
    generador = GeneradorIdeas()
    canal_slug = getattr(argumentos, "canal", DEFAULT_CHANNEL)
    profile = channel_profile(canal_slug)
    nicho = resolve_niche(canal_slug, argumentos.nicho)

    print("\nGENERADOR DE IDEAS")
    print("=" * 70)
    print(f"Canal: {profile['display_name']} ({canal_slug})")
    print(f"Nicho: {nicho}")
    print(f"Cantidad solicitada: {argumentos.cantidad}")
    print("Generando ideas...")

    resultado = generador.generar(
        nicho=nicho,
        cantidad=argumentos.cantidad,
        idioma=argumentos.idioma,
        data_dir=settings.data_dir,
        youtube_api_key=settings.youtube_api_key,
        region_tendencias="MX",
        channel_slug=canal_slug,
    )

    ruta = generador.guardar(
        resultado=resultado,
        data_dir=settings.data_dir,
    )

    print("=" * 70)

    investigacion = resultado.get(
        "investigacion_tendencias",
        {},
    )

    if investigacion.get("disponible"):
        print(
            "Tendencias YouTube: "
            f"{investigacion.get('videos_analizados', 0)} "
            "videos recientes analizados"
        )
        print(
            "Regi?n:",
            investigacion.get("region", "MX"),
        )
    else:
        print(
            "AVISO: tendencias externas no disponibles:",
            investigacion.get(
                "motivo",
                "motivo desconocido",
            ),
        )

    seleccion = resultado.get(
        "seleccion_automatica",
        {},
    )

    if seleccion:
        print(
            "SELECCI?N AUTOM?TICA:",
            seleccion.get("titulo", ""),
        )
        print(
            "Puntuaci?n de tendencia:",
            seleccion.get(
                "puntuacion_tendencia",
                0,
            ),
        )

    for numero, idea in enumerate(resultado["ideas"], start=1):
        print(f"\n{numero}. {idea['titulo']}")
        print(f"   Formato: {idea['formato']}")
        print(f"   Duración: {idea['duracion_minutos']} minutos")
        print(f"   Palabra clave: {idea['palabra_clave']}")
        print(f"   Potencial: {idea['potencial']}")
        print(
            "   Tendencia:",
            idea.get("puntuacion_tendencia", 0),
        )
        print(f"   Gancho: {idea['gancho']}")
        print(f"   Ángulo: {idea['angulo']}")

    rechazadas = resultado.get(
        "ideas_rechazadas",
        [],
    )

    if rechazadas:
        print("\nIDEAS RECHAZADAS POR SIMILITUD")

        for rechazada in rechazadas:
            print(
                f"- {rechazada['titulo']} "
                f"({rechazada['similitud']}%)"
            )

            print(
                "  Similar a: "
                f"{rechazada['comparado_con']}"
            )

            for motivo in rechazada.get(
                "motivos",
                [],
            ):
                print(
                    f"  - {motivo}"
                )

    print("\n" + "=" * 70)
    print(f"Modelo utilizado: {resultado['modelo']}")
    print(f"Archivo guardado: {ruta}")
    print("=" * 70)


def generar_guion(argumentos: argparse.Namespace) -> None:
    """Genera un guion a partir de una idea guardada."""
    settings = load_settings()
    canal_slug = getattr(argumentos, "canal", DEFAULT_CHANNEL)
    profile = channel_profile(canal_slug)

    archivo = (
        Path(argumentos.archivo)
        if argumentos.archivo
        else None
    )

    idea, archivo_ideas = cargar_idea(
        data_dir=settings.data_dir,
        indice=argumentos.indice,
        archivo=archivo,
        channel_slug=canal_slug,
    )

    print("\nGENERADOR DE GUIONES")
    print("=" * 70)
    print(f"Archivo de ideas: {archivo_ideas}")
    print(f"Canal: {profile['display_name']} ({canal_slug})")
    print(f"Idea seleccionada: {argumentos.indice}")
    print(f"Título: {idea.get('titulo', 'Sin título')}")
    print("Generando guion...")

    generador = GeneradorGuiones()

    resultado = generador.generar(
        idea=idea,
        idioma=argumentos.idioma,
        channel_slug=canal_slug,
    )

    ruta = generador.guardar(
        resultado=resultado,
        data_dir=settings.data_dir,
    )

    guion = resultado["guion"]

    print("=" * 70)
    print(f"Título final: {guion['titulo']}")
    print(f"Formato: {guion['formato']}")
    print(
        "Duración estimada: "
        f"{guion['duracion_estimada_minutos']} minutos"
    )
    print(f"Escenas generadas: {len(guion['escenas'])}")
    print(f"Gancho: {guion['gancho_inicial']}")

    print("\nESCENAS")

    for escena in guion["escenas"]:
        print(
            f"{escena['numero']}. {escena['titulo']} "
            f"({escena['duracion_segundos']} segundos)"
        )

    print("\n" + "=" * 70)
    print(f"Modelo utilizado: {resultado['modelo']}")
    print(f"Archivo guardado: {ruta}")
    print("=" * 70)


def revisar_guion(argumentos: argparse.Namespace) -> None:
    """Ejecuta el control de calidad del guion."""
    settings = load_settings()

    archivo = (
        Path(argumentos.archivo)
        if argumentos.archivo
        else None
    )

    reporte, ruta = validar_archivo_guion(
        data_dir=settings.data_dir,
        archivo=archivo,
        palabras_por_minuto=argumentos.ppm,
    )

    imprimir_reporte(
        reporte=reporte,
        ruta=ruta,
    )

    if not reporte["aprobado"]:
        raise SystemExit(2)


def corregir_guion(argumentos: argparse.Namespace) -> None:
    """Expande la narración de un guion demasiado corto."""
    settings = load_settings()
    canal_slug = getattr(argumentos, "canal", DEFAULT_CHANNEL)

    archivo = (
        Path(argumentos.archivo)
        if argumentos.archivo
        else None
    )

    contenido, ruta_original = cargar_guion_para_correccion(
        data_dir=settings.data_dir,
        archivo=archivo,
    )

    print("\nCORRECCIÓN AUTOMÁTICA DEL GUION")
    print("=" * 72)
    print(f"Archivo original: {ruta_original}")
    print(f"Velocidad objetivo: {argumentos.ppm} palabras por minuto")
    print("Expandiendo narraciones...")

    reparador = ReparadorGuiones()

    resultado = reparador.corregir(
        contenido=contenido,
        palabras_por_minuto=argumentos.ppm,
        channel_slug=canal_slug,
    )

    ruta_corregida = reparador.guardar(
        resultado=resultado,
        data_dir=settings.data_dir,
    )

    correccion = resultado["correccion"]

    print("=" * 72)
    print(f"Palabras antes: {correccion['palabras_antes']}")
    print(f"Palabras objetivo: {correccion['palabras_objetivo']}")
    print(f"Palabras después: {correccion['palabras_despues']}")
    print(f"Modelo utilizado: {resultado['modelo']}")
    print(f"Guion corregido: {ruta_corregida}")
    print("=" * 72)
    print("Ejecuta 'autotube script-check' para validar el resultado.")


def generar_voz(argumentos: argparse.Namespace) -> None:
    """Genera la narración del guion más reciente."""
    settings = load_settings()

    archivo = (
        Path(argumentos.archivo)
        if argumentos.archivo
        else None
    )

    contenido, ruta_guion = cargar_guion_audio(
        data_dir=settings.data_dir,
        archivo=archivo,
    )

    print("\nGENERADOR DE VOZ")
    print("=" * 72)
    print(f"Guion: {ruta_guion}")
    print(f"Voz: {argumentos.voz}")
    print(f"Velocidad: {argumentos.velocidad}")
    print(f"Tono: {argumentos.tono}")
    print("=" * 72)

    generador = GeneradorVoz(
        voz=argumentos.voz,
        velocidad=argumentos.velocidad,
        tono=argumentos.tono,
    )

    resultado = generador.generar(
        contenido=contenido,
        ruta_guion=ruta_guion,
        output_dir=settings.output_dir,
    )

    minutos = int(
        resultado["duracion_total_segundos"]
        // 60
    )

    segundos = round(
        resultado["duracion_total_segundos"]
        % 60,
        1,
    )

    print("\n" + "=" * 72)
    print(
        f"Segmentos generados: "
        f"{len(resultado['segmentos'])}"
    )
    print(
        f"Duración total: "
        f"{minutos} minutos y {segundos} segundos"
    )
    print(
        f"Audio completo: "
        f"{resultado['audio_completo']}"
    )
    print(
        f"Manifiesto: "
        f"{resultado['manifiesto']}"
    )
    print(
        f"Alineacion por palabra: "
        f"{resultado['alineacion']}"
    )
    print("=" * 72)


def generar_plan_visual(argumentos: argparse.Namespace) -> None:
    """Crea un plan visual sincronizado con el audio."""
    settings = load_settings()
    canal_slug = getattr(
        argumentos,
        "canal",
        DEFAULT_CHANNEL,
    )

    archivo_guion = (
        Path(argumentos.guion)
        if argumentos.guion
        else None
    )

    archivo_manifiesto = (
        Path(argumentos.manifiesto)
        if argumentos.manifiesto
        else None
    )

    (
        contenido_guion,
        manifiesto,
        ruta_guion,
        ruta_manifiesto,
    ) = cargar_contexto_visual(
        data_dir=settings.data_dir,
        output_dir=settings.output_dir,
        archivo_guion=archivo_guion,
        archivo_manifiesto=archivo_manifiesto,
    )

    print("\nPLANIFICADOR VISUAL")
    print("=" * 72)
    print(f"Guion: {ruta_guion}")
    print(f"Audio: {ruta_manifiesto}")
    print(
        f"Duración total: "
        f"{manifiesto.get('duracion_total_segundos', 0)} segundos"
    )
    print("Creando plan visual sincronizado...")
    print("=" * 72)

    planificador = PlanificadorVisual()

    resultado = planificador.generar(
        contenido_guion=contenido_guion,
        manifiesto=manifiesto,
    )

    resultado["channel_slug"] = canal_slug
    resultado["plan_visual"]["channel_slug"] = canal_slug

    ruta_resultado = planificador.guardar(
        resultado=resultado,
        data_dir=settings.data_dir,
    )

    segmentos = resultado["plan_visual"]["segmentos"]

    cantidad_clips = sum(
        len(segmento.get("clips", []))
        for segmento in segmentos
    )

    print("\n" + "=" * 72)
    print(f"Segmentos visuales: {len(segmentos)}")
    print(f"Clips planificados: {cantidad_clips}")
    print(f"Modelo utilizado: {resultado['modelo']}")
    print(f"Plan guardado: {ruta_resultado}")
    print("=" * 72)


def descargar_recursos(argumentos: argparse.Namespace) -> None:
    """Descarga recursos visuales desde Pixabay."""
    settings = load_settings()

    if argumentos.limite < 0:
        raise ValueError(
            "El límite no puede ser negativo."
        )

    archivo_plan = (
        Path(argumentos.plan)
        if argumentos.plan
        else None
    )

    contenido_plan, ruta_plan = cargar_plan_visual(
        data_dir=settings.data_dir,
        archivo=archivo_plan,
    )

    print("\nRECOLECTOR DE RECURSOS VISUALES")
    print("=" * 72)
    print(f"Plan visual: {ruta_plan}")

    if argumentos.limite == 0:
        print("Límite: plan completo")
    else:
        print(
            f"Límite de descargas: "
            f"{argumentos.limite}"
        )

    print("=" * 72)

    recolector = RecolectorRecursos(
        data_dir=settings.data_dir,
        output_dir=settings.output_dir,
    )

    resultado = recolector.recolectar(
        contenido_plan=contenido_plan,
        ruta_plan=ruta_plan,
        limite=argumentos.limite,
        channel_slug=getattr(
            argumentos,
            "canal",
            DEFAULT_CHANNEL,
        ),
    )

    resumen = resultado["resumen"]

    print("\n" + "=" * 72)
    print(
        f"Recursos descargados: "
        f"{resumen['descargados']}"
    )
    print(
        f"Recursos de stock aprobados: "
        f"{resumen.get('descargados_stock', resumen['descargados'])}"
    )
    print(
        f"Imagenes documentales generadas con Workers AI: "
        f"{resumen.get('generados_ia', 0)}"
    )
    print(
        f"Pendientes de generación local: "
        f"{resumen['pendientes_generacion']}"
    )
    print(
        f"Pendientes sin recurso coincidente: "
        f"{resumen.get('pendientes_sin_recurso', 0)}"
    )
    print(
        f"Omitidos por el límite: "
        f"{resumen['omitidos_por_limite']}"
    )
    print(
        f"Errores: "
        f"{resumen['errores']}"
    )
    print(
        f"Manifiesto: "
        f"{resultado['manifiesto']}"
    )
    print("=" * 72)

    pendientes_sin_recurso = int(
        resumen.get(
            "pendientes_sin_recurso",
            0,
        )
    )

    pendientes_cuota_ia = int(
        resumen.get(
            "pendientes_cuota_imagen_ia",
            0,
        )
    )

    if pendientes_cuota_ia:
        raise RuntimeError(
            "COBERTURA VISUAL INCOMPLETA: "
            f"{pendientes_cuota_ia} clips no pudieron cubrirse con "
            "stock, cache, Drive, reutilizacion contextual ni el "
            "generador opcional. Cloudflare no es un requisito para "
            "producir; el bloqueo indica ausencia real de cobertura."
        )

    if bool(resumen.get("recoleccion_detenida", False)):
        raise RuntimeError(
            "PAUSA SEGURA DEL CONTROL VISUAL: la recoleccion se "
            "detuvo antes de completar todos los clips. Motivo: "
            + str(
                resumen.get(
                    "motivo_detencion",
                    "verificacion visual no disponible",
                )
            )
        )

    if pendientes_sin_recurso:
        raise RuntimeError(
            "CONTROL EDITORIAL VISUAL: "
            f"{pendientes_sin_recurso} clips no tienen una imagen "
            "o video que coincida con la narracion. El pipeline se "
            "detuvo antes del render y no genero graficos de relleno."
        )


def generar_recursos_locales(argumentos: argparse.Namespace) -> None:
    """Genera recursos gráficos locales para el video."""
    settings = load_settings()

    archivo = (
        Path(argumentos.manifiesto)
        if argumentos.manifiesto
        else None
    )

    manifiesto, ruta_manifiesto = cargar_manifiesto_assets(
        output_dir=settings.output_dir,
        archivo=archivo,
    )

    canal_slug = getattr(
        argumentos,
        "canal",
        DEFAULT_CHANNEL,
    )
    canal_manifiesto = str(
        manifiesto.get(
            "channel_slug",
            canal_slug,
        )
    )

    if canal_manifiesto != canal_slug:
        raise RuntimeError(
            "BLOQUEO MULTICANAL: la coleccion visual pertenece a "
            f"{canal_manifiesto}, no a {canal_slug}."
        )

    print("\nGENERADOR DE RECURSOS LOCALES")
    print("=" * 72)
    print(f"Manifiesto: {ruta_manifiesto}")
    print(f"Resolución: 1920x1080")
    print(f"Regenerar existentes: {argumentos.forzar}")
    print("=" * 72)

    generador = GeneradorRecursosLocales()

    resultado = generador.generar(
        manifiesto=manifiesto,
        ruta_manifiesto=ruta_manifiesto,
        forzar=argumentos.forzar,
    )

    print("\n" + "=" * 72)
    print(
        f"Generados en esta ejecución: "
        f"{resultado['generados_esta_ejecucion']}"
    )
    print(
        f"Recursos de Pixabay: "
        f"{resultado['descargados']}"
    )
    print(
        f"Recursos locales totales: "
        f"{resultado['generados_localmente']}"
    )
    print(
        f"Pendientes: "
        f"{resultado['pendientes']}"
    )
    print(
        f"Errores: "
        f"{resultado['errores_totales']}"
    )
    print(
        f"Total disponible: "
        f"{resultado['descargados'] + resultado['generados_localmente']}"
        f"/{resultado['total']}"
    )
    print(
        f"Vista previa: "
        f"{resultado['vista_previa']}"
    )
    print(
        f"Manifiesto actualizado: "
        f"{resultado['manifiesto']}"
    )
    print("=" * 72)


def gestionar_cache_visual(argumentos: argparse.Namespace) -> None:
    """Guarda, restaura o libera recursos visuales con Google Drive."""
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parents[2]
    herramienta = project_root / "tools" / "google_drive_visual_cache.py"

    if not herramienta.is_file():
        raise FileNotFoundError(
            "No existe el gestor del cache visual: "
            f"{herramienta}"
        )

    comando = [
        sys.executable,
        str(herramienta),
        argumentos.accion,
        "--canal",
        getattr(argumentos, "canal", DEFAULT_CHANNEL),
    ]

    manifiesto = getattr(argumentos, "manifiesto", None)
    if manifiesto:
        comando.extend(["--manifiesto", str(manifiesto)])

    if (
        argumentos.accion != "status"
        and getattr(argumentos, "dry_run", False)
    ):
        comando.append("--dry-run")

    if (
        argumentos.accion == "cleanup"
        and getattr(argumentos, "confirmar", False)
    ):
        comando.append("--confirmar")

    subprocess.run(
        comando,
        cwd=project_root,
        check=True,
    )


def respaldar_codigo_drive(argumentos: argparse.Namespace) -> None:
    """Respalda en Drive un ZIP seguro del commit actual de Git."""
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parents[2]
    herramienta = project_root / "tools" / "google_drive_code_backup.py"

    if not herramienta.is_file():
        raise FileNotFoundError(
            "No existe la herramienta de respaldo del codigo: "
            f"{herramienta}"
        )

    comando = [
        sys.executable,
        str(herramienta),
        "--carpeta-raiz",
        str(argumentos.carpeta_raiz),
    ]
    if argumentos.version:
        comando.extend(["--version", str(argumentos.version)])
    if argumentos.dry_run:
        comando.append("--dry-run")

    subprocess.run(
        comando,
        cwd=project_root,
        check=True,
    )


def generar_timeline_semantica(
    argumentos: argparse.Namespace,
) -> None:
    """Genera la fuente temporal unica de narracion y visuales."""
    settings = load_settings()
    assets_path = (
        Path(argumentos.assets)
        if argumentos.assets
        else None
    )
    audio_path = (
        Path(argumentos.audio)
        if argumentos.audio
        else None
    )
    channel_slug = getattr(
        argumentos,
        "canal",
        DEFAULT_CHANNEL,
    )

    print("\nTIMELINE SEMANTICA")
    print("=" * 72)
    print(f"Canal: {channel_slug}")
    print("Validando cobertura temporal y recursos...")

    result = GeneradorTimelineSemantica(
        output_dir=settings.output_dir,
    ).generar(
        assets_path=assets_path,
        audio_path=audio_path,
        channel_slug=channel_slug,
    )

    print(f"Eventos sincronizados: {result['events']}")
    print(f"Palabras alineadas: {result['words']}")
    print(f"Fuente temporal: {result['timing_source']}")
    print(f"Version: {result['version']}")
    print(
        "Duracion cubierta: "
        f"{result['duration_ms'] / 1000:.3f} segundos"
    )
    print(f"Timeline: {result['path']}")
    print("Estado: APROBADA")
    print("=" * 72)


def auditar_visuales_finales(argumentos: argparse.Namespace) -> None:
    """Comprueba los pixeles y fotogramas de los recursos reales."""
    settings = load_settings()
    candidates = sorted(
        settings.output_dir.glob("assets/coleccion_*/assets_manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if argumentos.assets:
        assets_path = Path(argumentos.assets).expanduser().resolve()
    elif candidates:
        assets_path = candidates[0].resolve()
    else:
        raise FileNotFoundError("No existe un manifiesto visual para auditar.")

    result = AuditorVisualFinal(settings.output_dir).audit(
        assets_path=assets_path,
        channel_slug=getattr(argumentos, "canal", DEFAULT_CHANNEL),
        limit=max(0, int(argumentos.limite)),
    )

    print("\nAUDITORIA VISUAL FINAL")
    print("=" * 72)
    print(f"Recursos auditados: {result['audited_assets']}")
    print(f"Recursos aprobados: {result['approved_assets']}")
    print(f"Recursos rechazados: {result['rejected_assets']}")
    print(f"Informe: {result['path']}")
    print(f"Estado: {str(result['status']).upper()}")
    print("=" * 72)

    if result["status"] != "approved":
        raise RuntimeError(
            "La auditoria visual rechazo uno o mas recursos. "
            "El render permanece bloqueado."
        )


def renderizar_video(argumentos: argparse.Namespace) -> None:
    """Renderiza una vista previa o el video completo."""
    settings = load_settings()

    archivo_assets = (
        Path(argumentos.assets)
        if argumentos.assets
        else None
    )

    archivo_audio = (
        Path(argumentos.audio)
        if argumentos.audio
        else None
    )

    archivo_timeline = (
        Path(argumentos.timeline)
        if argumentos.timeline
        else None
    )

    archivo_auditoria = (
        Path(argumentos.visual_audit)
        if argumentos.visual_audit
        else None
    )

    import subprocess
    import sys

    project_root = Path(__file__).resolve().parents[2]
    restaurador = project_root / "tools" / "google_drive_visual_cache.py"

    if restaurador.is_file():
        comando_restaurar = [
            sys.executable,
            str(restaurador),
            "restore",
            "--canal",
            getattr(argumentos, "canal", DEFAULT_CHANNEL),
        ]

        if archivo_assets is not None:
            comando_restaurar.extend(
                ["--manifiesto", str(archivo_assets)]
            )

        subprocess.run(
            comando_restaurar,
            cwd=project_root,
            check=True,
        )

    (
        assets,
        audio,
        ruta_assets,
        ruta_audio_manifest,
        ruta_audio,
    ) = cargar_contexto_render(
        output_dir=settings.output_dir,
        archivo_assets=archivo_assets,
        archivo_audio=archivo_audio,
    )

    cantidad_requerida_auditoria = (
        int(argumentos.limite_clips)
        if argumentos.limite_clips is not None
        else (8 if argumentos.preview else len(assets.get("elementos", [])))
    )
    _, ruta_auditoria = find_compatible_audit(
        output_dir=settings.output_dir,
        assets_path=ruta_assets,
        required_assets=cantidad_requerida_auditoria,
        audit_path=archivo_auditoria,
    )

    timeline, ruta_timeline = cargar_timeline_render(
        output_dir=settings.output_dir,
        ruta_assets=ruta_assets,
        ruta_audio_manifest=ruta_audio_manifest,
        archivo=archivo_timeline,
    )

    cantidad_total = len(
        assets.get("elementos", [])
    )

    print("\nCOMPOSITOR DE VIDEO")
    print("=" * 72)
    print(f"Recursos: {ruta_assets}")
    print(f"Audio: {ruta_audio}")
    print(f"Timeline aprobada: {ruta_timeline}")
    print(f"Auditoria visual aprobada: {ruta_auditoria}")
    print(f"Recursos disponibles: {cantidad_total}/{cantidad_total}")
    print(
        f"Modo: "
        f"{'vista previa' if argumentos.preview else 'video completo'}"
    )
    print("=" * 72)

    compositor = CompositorVideo(
        output_dir=settings.output_dir,
    )

    resultado = compositor.renderizar(
        assets=assets,
        audio_manifest=audio,
        ruta_assets=ruta_assets,
        ruta_audio_manifest=ruta_audio_manifest,
        ruta_audio=ruta_audio,
        timeline=timeline,
        ruta_timeline=ruta_timeline,
        preview=argumentos.preview,
        limite_clips=argumentos.limite_clips,
        conservar_temporales=argumentos.conservar_temporales,
    )

    minutos = int(
        resultado["duracion"] // 60
    )

    segundos = round(
        resultado["duracion"] % 60,
        1,
    )

    print("\n" + "=" * 72)
    print(f"Modo: {resultado['modo']}")
    print(f"Clips procesados: {resultado['clips']}")
    print(f"Resolución: {resultado['resolucion']}")
    print(
        f"Duración: {minutos} minutos "
        f"y {segundos} segundos"
    )
    print(f"Video: {resultado['video']}")
    print(f"Manifiesto: {resultado['manifiesto']}")
    print("=" * 72)


def generar_subtitulos(argumentos: argparse.Namespace) -> None:
    """Genera subtítulos sincronizados desde la narración."""
    settings = load_settings()

    archivo_audio = (
        Path(argumentos.audio)
        if argumentos.audio
        else None
    )

    manifiesto_audio, ruta_audio = cargar_audio_para_subtitulos(
        output_dir=settings.output_dir,
        archivo=archivo_audio,
    )

    print("\nGENERADOR DE SUBTÍTULOS")
    print("=" * 72)
    print(f"Audio: {ruta_audio}")
    print(f"Máximo de palabras: {argumentos.max_palabras}")
    print(f"Máximo de caracteres: {argumentos.max_caracteres}")
    print("=" * 72)

    generador = GeneradorSubtitulos()

    resultado = generador.generar(
        manifiesto_audio=manifiesto_audio,
        ruta_audio_manifest=ruta_audio,
        output_dir=settings.output_dir,
        max_palabras=argumentos.max_palabras,
        max_caracteres=argumentos.max_caracteres,
    )

    minutos = int(
        resultado["duracion"] // 60
    )

    segundos = round(
        resultado["duracion"] % 60,
        1,
    )

    print("\n" + "=" * 72)
    print(f"Subtítulos creados: {resultado['cantidad']}")
    print(
        f"Duración cubierta: "
        f"{minutos} minutos y {segundos} segundos"
    )
    print(f"Archivo SRT: {resultado['srt']}")
    print(
        f"Transcripción: "
        f"{resultado['transcripcion']}"
    )
    print(
        f"Manifiesto: "
        f"{resultado['manifiesto']}"
    )
    print("=" * 72)






def generar_insights_analitica(
    argumentos: argparse.Namespace,
) -> None:
    """Genera el perfil estrategico desde Analytics."""
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parents[2]
    herramienta = (
        project_root
        / "tools"
        / "youtube_analytics_insights.py"
    )

    if not herramienta.is_file():
        raise FileNotFoundError(
            "No existe el motor de insights: "
            f"{herramienta}"
        )

    comando = [
        sys.executable,
        str(herramienta),
        "--canal",
        getattr(argumentos, "canal", "nexon_ia"),
    ]

    reporte = getattr(
        argumentos,
        "reporte",
        None,
    )

    if reporte:
        comando.extend(
            [
                "--reporte",
                str(reporte),
            ]
        )

    subprocess.run(
        comando,
        cwd=project_root,
        check=True,
    )


def generar_experimento(
    argumentos: argparse.Namespace,
) -> None:
    """Genera un experimento editorial controlado."""
    from autotube.content.experiment_manager import (
        GestorExperimentosYouTube,
    )

    project_root = Path(__file__).resolve().parents[2]

    gestor = GestorExperimentosYouTube(
        project_root=project_root,
        channel_slug=getattr(argumentos, "canal", DEFAULT_CHANNEL),
    )

    resultado = gestor.generar(
        variable=argumentos.variable,
        cantidad=argumentos.cantidad,
        renderizar_miniaturas=(
            not argumentos.sin_miniaturas
        ),
    )

    experimento = resultado["experimento"]

    print()
    print("EXPERIMENTO EDITORIAL DE YOUTUBE")
    print("=" * 72)
    print(
        "ID:",
        experimento["experimento_id"],
    )
    print(
        "Variable unica:",
        experimento["variable"],
    )
    print(
        "Metrica principal:",
        experimento["metrica"]["primaria"],
    )
    print(
        "Minimo:",
        experimento["reglas"]["vistas_minimas_por_variante"],
        "vistas por variante",
    )
    print("-" * 72)

    for variante in experimento["variantes"]:
        print()
        print(
            f"VARIANTE {variante['codigo']}"
            + (
                " - CONTROL"
                if variante["control"]
                else ""
            )
        )
        print(
            "Titulo:",
            variante["titulo"],
        )
        print(
            "Texto miniatura:",
            variante["texto_miniatura"],
        )
        print(
            "Gancho:",
            variante["gancho_inicial"],
        )
        print(
            "Duracion objetivo:",
            variante["duracion_objetivo_minutos"],
            "minutos",
        )
        print(
            "Hipotesis:",
            variante["hipotesis"],
        )

        if variante.get("miniatura"):
            print(
                "Miniatura:",
                variante["miniatura"],
            )

    print()
    print("=" * 72)
    print(
        "ESTADO: PLANIFICADO; NO SE MODIFICO YOUTUBE"
    )
    print(
        "Experimento:",
        resultado["archivo"],
    )
    print("=" * 72)


def registrar_resultado_experimento(
    argumentos: argparse.Namespace,
) -> None:
    """Registra metricas y evalua un experimento."""
    from autotube.content.experiment_manager import (
        GestorExperimentosYouTube,
    )

    project_root = Path(__file__).resolve().parents[2]

    gestor = GestorExperimentosYouTube(
        project_root=project_root,
        channel_slug=getattr(argumentos, "canal", DEFAULT_CHANNEL),
    )

    resultado = gestor.registrar_resultado(
        codigo=argumentos.codigo,
        vistas=argumentos.vistas,
        ctr=argumentos.ctr,
        retencion=argumentos.retencion,
        duracion_media=argumentos.duracion_media,
        minutos_vistos=argumentos.minutos_vistos,
        archivo=argumentos.experimento,
    )

    evaluacion = resultado["evaluacion"]

    print()
    print("RESULTADO DE EXPERIMENTO REGISTRADO")
    print("=" * 72)
    print(
        "Variante:",
        argumentos.codigo,
    )
    print(
        "Vistas:",
        argumentos.vistas,
    )
    print(
        "Estado:",
        evaluacion["estado"].upper(),
    )
    print(
        "Metrica:",
        evaluacion["metrica"],
    )

    ganador = evaluacion.get(
        "ganador_provisional",
        "",
    )

    if ganador:
        print(
            "Ganador provisional:",
            ganador,
        )
        print(
            "Diferencia:",
            evaluacion.get(
                "diferencia",
                0,
            ),
        )
    else:
        print(
            "Ganador provisional: ninguno"
        )

    faltantes = evaluacion.get(
        "faltantes",
        [],
    )

    for elemento in faltantes:
        print(
            f"- Variante {elemento['codigo']}: "
            + ", ".join(
                elemento["razones"]
            )
        )

    print(
        "Nota:",
        evaluacion.get(
            "nota",
            "",
        ),
    )
    print(
        "Experimento:",
        resultado["archivo"],
    )
    print("=" * 72)


def generar_analitica(argumentos: argparse.Namespace) -> None:
    """Ejecuta el informe local de YouTube Analytics."""
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parents[2]
    herramienta = (
        project_root
        / "tools"
        / "youtube_analytics_report.py"
    )

    if not herramienta.exists():
        raise FileNotFoundError(
            f"No existe la herramienta de Analytics: {herramienta}"
        )

    comando = [
        sys.executable,
        str(herramienta),
        "--dias",
        str(argumentos.dias),
        "--max-videos",
        str(argumentos.max_videos),
        "--canal",
        getattr(argumentos, "canal", "nexon_ia"),
    ]

    subprocess.run(
        comando,
        cwd=project_root,
        check=True,
    )

    print()
    print("Actualizando aprendizaje estrategico...")

    generar_insights_analitica(
        argparse.Namespace(
            reporte=None,
            canal=getattr(argumentos, "canal", "nexon_ia"),
        )
    )


def generar_dashboard(
    argumentos: argparse.Namespace,
) -> None:
    """Genera el centro de control operativo local."""
    from autotube.operations.dashboard import (
        CentroControlAutoTube,
    )

    project_root = Path(__file__).resolve().parents[2]

    dashboard = CentroControlAutoTube(
        project_root=project_root,
    )

    if argumentos.en_vivo:
        dashboard.seguir(
            intervalo=argumentos.intervalo,
            abrir=argumentos.abrir,
        )
        return

    dashboard.generar(
        abrir=argumentos.abrir,
    )




def limpiar_almacenamiento(
    argumentos: argparse.Namespace,
) -> None:
    """Audita o ejecuta la limpieza segura de output."""
    from autotube.operations.storage_cleaner import (
        LimpiadorAlmacenamiento,
    )

    project_root = Path(__file__).resolve().parents[2]

    limpiador = LimpiadorAlmacenamiento(
        project_root=project_root,
    )

    resultado = limpiador.ejecutar(
        confirmar=argumentos.confirmar,
        incluir_publicados=argumentos.publicados,
    )

    limpiador.imprimir(
        resultado
    )

    if not argumentos.confirmar:
        print(
            "SIMULACION: revisa la lista y agrega "
            "--confirmar solo si estas de acuerdo."
        )
        return

    if resultado["informe"]["errores"]:
        raise RuntimeError(
            "La limpieza termino con uno o mas errores."
        )


def ejecutar_guardian_automatico(
    argumentos: argparse.Namespace,
) -> None:
    """Ejecuta el pipeline mediante el guardian seguro."""
    from autotube.operations.guardian import (
        GuardianPipeline,
    )

    project_root = Path(__file__).resolve().parents[2]

    guardian = GuardianPipeline(
        project_root=project_root,
        channel_slug=argumentos.canal,
    )

    resultado = guardian.ejecutar(
        dry_run=argumentos.dry_run,
        publicar=not argumentos.sin_publicar,
        control_profundo=(
            not argumentos.sin_control_profundo
        ),
        limpiar_publicados=(
            not argumentos.sin_limpiar_publicados
        ),
    )

    guardian.imprimir(
        resultado
    )

    estado = resultado[
        "informe"
    ]["estado"]

    if (
        not argumentos.dry_run
        and estado != "completado"
    ):
        raise RuntimeError(
            "El guardian termino con estado: "
            f"{estado}"
        )


def gestionar_programador_windows(
    argumentos: argparse.Namespace,
) -> None:
    """Consulta, instala o elimina la tarea automatica."""
    from autotube.operations.windows_scheduler import (
        ProgramadorWindows,
    )

    project_root = Path(__file__).resolve().parents[2]

    programador = ProgramadorWindows(
        project_root=project_root,
        channel_slug=argumentos.canal,
    )

    if argumentos.accion == "instalar":
        resultado = programador.instalar(
            hora=argumentos.hora,
            dias=argumentos.dias,
            confirmar=argumentos.confirmar,
        )

        programador.imprimir_instalacion(
            resultado
        )

        if not argumentos.confirmar:
            print(
                "SIMULACION: agrega --confirmar "
                "para instalar la tarea."
            )
            return

        if not resultado["instalado"]:
            raise RuntimeError(
                "Windows no pudo instalar la tarea: "
                + str(
                    resultado.get(
                        "error",
                        "",
                    )
                )
            )

        return

    if argumentos.accion == "eliminar":
        resultado = programador.eliminar(
            confirmar=argumentos.confirmar,
        )

        print()
        print("PROGRAMADOR AUTOMATICO AUTOTUBE AI")
        print("=" * 72)
        print("Accion: ELIMINAR")
        print(
            "Modo:",
            (
                "ELIMINACION REAL"
                if argumentos.confirmar
                else "SIMULACION"
            ),
        )
        print(
            "Comando:",
            " ".join(
                resultado["comando"]
            ),
        )

        if argumentos.confirmar:
            print(
                "Resultado:",
                (
                    "ELIMINADA"
                    if resultado["eliminada"]
                    else "ERROR"
                ),
            )

        if resultado["salida"]:
            print(
                resultado["salida"]
            )

        if resultado["error"]:
            print(
                resultado["error"]
            )

        print("=" * 72)

        if not argumentos.confirmar:
            print(
                "SIMULACION: agrega --confirmar "
                "para eliminar la tarea."
            )
            return

        if not resultado["eliminada"]:
            raise RuntimeError(
                "Windows no pudo eliminar la tarea."
            )

        return

    resultado = programador.consultar()

    print()
    print("PROGRAMADOR AUTOMATICO AUTOTUBE AI")
    print("=" * 72)
    print(
        "Tarea:",
        resultado["tarea"],
    )
    print(
        "Estado:",
        (
            "INSTALADA"
            if resultado["instalada"]
            else "NO INSTALADA"
        ),
    )

    if resultado["salida"]:
        print("-" * 72)
        print(
            resultado["salida"]
        )

    if (
        resultado["error"]
        and resultado["instalada"]
    ):
        print(
            resultado["error"]
        )

    print("=" * 72)


def comprobar_codificador(
    argumentos: argparse.Namespace,
) -> None:
    """Comprueba y describe la seleccion de codificador."""
    from autotube.video.hardware_encoder import (
        describir_codificador,
        probar_qsv,
        seleccionar_codificador,
    )

    disponible, motivo = probar_qsv(
        forzar_prueba=argumentos.reprobar,
    )

    clips = seleccionar_codificador(
        crf_cpu=27,
        preset_cpu="veryfast",
        preferir_qsv=False,
    )

    final = seleccionar_codificador(
        crf_cpu=18,
        preset_cpu="fast",
    )

    shorts = seleccionar_codificador(
        crf_cpu=20,
        preset_cpu="fast",
    )

    print()
    print("DIAGNOSTICO DE CODIFICACION DE VIDEO")
    print("=" * 72)
    print(
        "Intel Quick Sync:",
        (
            "DISPONIBLE"
            if disponible
            else "NO DISPONIBLE"
        ),
    )
    print(
        "Prueba:",
        motivo,
    )
    print("-" * 72)
    print(
        "Clips:",
        describir_codificador(
            clips
        ),
    )
    print(
        "Render final:",
        describir_codificador(
            final
        ),
    )
    print(
        "Shorts:",
        describir_codificador(
            shorts
        ),
    )
    print("-" * 72)
    print(
        "Recuperacion por CPU: ACTIVADA"
    )
    print(
        "Modo configurable con "
        "AUTOTUBE_VIDEO_ENCODER=auto|qsv|cpu"
    )
    print("=" * 72)


def ejecutar_control_multimedia(
    argumentos: argparse.Namespace,
) -> None:
    """Ejecuta el control tecnico de la produccion reciente."""
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parents[2]
    herramienta = (
        project_root
        / "tools"
        / "media_quality_check.py"
    )

    if not herramienta.is_file():
        raise FileNotFoundError(
            "No existe el control multimedia: "
            f"{herramienta}"
        )

    comando = [
        sys.executable,
        str(herramienta),
    ]

    if getattr(
        argumentos,
        "validar_shorts",
        False,
    ):
        comando.append(
            "--validar-shorts"
        )

        manifiesto = getattr(
            argumentos,
            "manifiesto_shorts",
            None,
        )

        if manifiesto:
            comando.extend(
                [
                    "--manifiesto-shorts",
                    str(manifiesto),
                ]
            )

    if getattr(
        argumentos,
        "profundo",
        False,
    ):
        comando.append(
            "--profundo"
        )

    subprocess.run(
        comando,
        cwd=project_root,
        check=True,
    )


def gestionar_cola_publicacion(
    argumentos: argparse.Namespace,
) -> None:
    """Consulta, sincroniza o reanuda la cola de YouTube."""
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parents[2]
    herramienta = (
        project_root
        / "tools"
        / "youtube_publish_queue.py"
    )

    if not herramienta.is_file():
        raise FileNotFoundError(
            "No existe el gestor de la cola: "
            f"{herramienta}"
        )

    acciones = {
        "publish-status": "status",
        "publish-queue": "sync",
        "publish-resume": "resume",
    }

    accion = acciones[argumentos.comando]
    comando = [
        sys.executable,
        str(herramienta),
        accion,
        "--canal",
        getattr(argumentos, "canal", "nexon_ia"),
    ]

    if (
        accion == "resume"
        and getattr(argumentos, "dry_run", False)
    ):
        comando.append("--dry-run")

    subprocess.run(
        comando,
        cwd=project_root,
        check=True,
    )


def generar_shorts(argumentos: argparse.Namespace) -> None:
    """Genera Shorts verticales desde el documental mas reciente."""
    project_root = Path(__file__).resolve().parents[2]
    canal_slug = getattr(argumentos, "canal", DEFAULT_CHANNEL)
    generador = GeneradorShorts(
        project_root=project_root,
        channel_slug=canal_slug,
    )
    resultado = generador.generar(
        cantidad=argumentos.cantidad,
        duracion_objetivo=argumentos.duracion,
        solo_plan=argumentos.solo_plan,
    )

    print()
    print("GENERADOR DE SHORTS")
    print("=" * 72)
    print("Video:", resultado["video_origen"])
    print("Resolucion:", resultado["resolucion"])
    print("Cantidad:", resultado["cantidad"])

    for short in resultado["shorts"]:
        print()
        print(
            f"{short['orden']}. {short['gancho']} | "
            f"{short['duracion_segundos']:.1f}s | "
            f"score={short['puntuacion']:.1f}"
        )

        if short["archivo"]:
            print("   Archivo:", short["archivo"])

    print()
    print("Manifiesto:", resultado["manifiesto"])
    print("=" * 72)


def ejecutar_pipeline(argumentos: argparse.Namespace) -> None:
    """Ejecuta de principio a fin la producci?n autom?tica del video."""

    import shutil
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    canal_slug = getattr(
        argumentos,
        "canal",
        DEFAULT_CHANNEL,
    )
    profile = channel_profile(canal_slug)
    nombre_canal = profile["display_name"]
    argumentos.nicho = resolve_niche(
        canal_slug,
        argumentos.nicho,
    )

    import json
    import time
    from datetime import datetime

    migrate_legacy_pipeline_state(
        project_root
    )

    ruta_estado = pipeline_state_path(
        project_root,
        canal_slug,
    )

    otros_pendientes = incomplete_other_channel_states(
        project_root,
        canal_slug,
    )

    if otros_pendientes:
        canales = ", ".join(
            item["canal"]
            for item in otros_pendientes
        )
        raise RuntimeError(
            "No se puede iniciar este canal mientras existe "
            "otra produccion incompleta: "
            f"{canales}. Reanuda y finaliza primero ese canal; "
            "los recursos de produccion aun son compartidos."
        )

    estado: dict[str, object] = {
        "completado": False,
        "iniciado_en": (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        ),
        "actualizado_en": "",
        "finalizado_en": "",
        "paso_actual": "",
        "total_pasos": 0,
        "pasos_completados": [],
        "duraciones_pasos": {},
        "ejecuciones_pasos": [],
        "ultimo_error": "",
        "parametros": {
            "nicho": argumentos.nicho,
            "cantidad_ideas": argumentos.cantidad_ideas,
            "indice": argumentos.indice,
            "voz": argumentos.voz,
            "velocidad": argumentos.velocidad,
            "tono": argumentos.tono,
            "canal": canal_slug,
        },
    }

    print(
        f"Canal de YouTube seleccionado: "
        f"{nombre_canal} ({canal_slug})"
    )

    if argumentos.reanudar and ruta_estado.is_file():
        try:
            cargado = json.loads(
                ruta_estado.read_text(
                    encoding="utf-8-sig"
                )
            )

            parametros_cargados = (
                cargado.get(
                    "parametros",
                    {},
                )
                if isinstance(cargado, dict)
                else {}
            )
            canal_cargado = str(
                parametros_cargados.get(
                    "canal",
                    canal_slug,
                )
                if isinstance(
                    parametros_cargados,
                    dict,
                )
                else canal_slug
            )

            if (
                isinstance(cargado, dict)
                and canal_cargado == canal_slug
            ):
                estado = cargado
            else:
                raise ValueError(
                    "El estado pertenece a otro canal."
                )

            print(
                "Reanudaci?n activada. "
                "Se conservar?n los pasos completados."
            )

        except Exception:
            print(
                "El estado anterior no pudo leerse. "
                "Se iniciar? un pipeline nuevo."
            )

    estado.setdefault(
        "iniciado_en",
        (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        ),
    )
    estado.setdefault(
        "actualizado_en",
        "",
    )
    estado.setdefault(
        "finalizado_en",
        "",
    )
    estado.setdefault(
        "paso_actual",
        "",
    )
    estado.setdefault(
        "total_pasos",
        0,
    )
    estado.setdefault(
        "duraciones_pasos",
        {},
    )
    estado.setdefault(
        "ejecuciones_pasos",
        [],
    )

    if (
        argumentos.reanudar
        and getattr(
            argumentos,
            "regenerar_visuales",
            False,
        )
    ):
        pasos_visuales = {
            "Creaci?n del plan visual",
            "Descarga de recursos",
            "Generaci?n de recursos locales",
            "Generacion de timeline semantica",
            "Archivo visual en Google Drive",
            "Renderizado del video",
            "Generaci?n de subt?tulos",
        }

        completados = estado.get(
            "pasos_completados",
            [],
        )

        if isinstance(completados, list):
            estado["pasos_completados"] = [
                paso
                for paso in completados
                if paso not in pasos_visuales
            ]

        duraciones = estado.get(
            "duraciones_pasos",
            {},
        )

        if isinstance(duraciones, dict):
            for paso in pasos_visuales:
                duraciones.pop(paso, None)

        estado["completado"] = False
        estado["finalizado_en"] = ""
        estado["paso_actual"] = ""
        estado["ultimo_error"] = ""

        print(
            "Regeneracion visual activada. Se conservaran "
            "las ideas, el guion corregido y la narracion."
        )

    def guardar_estado() -> None:
        estado["actualizado_en"] = (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        )

        ruta_estado.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporal = ruta_estado.with_suffix(".tmp")

        temporal.write_text(
            json.dumps(
                estado,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporal.replace(ruta_estado)

    if not argumentos.reanudar:
        guardar_estado()

    autotube_exe = shutil.which("autotube")

    if autotube_exe:
        base_command = [autotube_exe]
    else:
        base_command = [
            sys.executable,
            "-c",
            "from autotube.main import main; main()",
        ]

    def registrar_ejecucion_paso(
        nombre: str,
        inicio_monotono: float,
        iniciado_en: str,
        resultado: str,
        error: str = "",
    ) -> None:
        duracion = round(
            time.perf_counter()
            - inicio_monotono,
            3,
        )

        duraciones = estado.setdefault(
            "duraciones_pasos",
            {},
        )

        if isinstance(
            duraciones,
            dict,
        ):
            duraciones[nombre] = duracion

        ejecuciones = estado.setdefault(
            "ejecuciones_pasos",
            [],
        )

        if isinstance(
            ejecuciones,
            list,
        ):
            ejecuciones.append(
                {
                    "paso": nombre,
                    "iniciado_en": iniciado_en,
                    "finalizado_en": (
                        datetime.now()
                        .astimezone()
                        .isoformat(
                            timespec="seconds"
                        )
                    ),
                    "duracion_segundos": duracion,
                    "resultado": resultado,
                    "error": error,
                }
            )

        estado["paso_actual"] = ""

    def ejecutar_paso(
        numero: int,
        total: int,
        nombre: str,
        parametros: list[str],
    ) -> None:
        print()
        print("=" * 72)
        print(f"PASO {numero}/{total}: {nombre}")
        print("=" * 72)

        comando = base_command + parametros

        print(
            "Comando:",
            " ".join(str(parte) for parte in comando),
        )

        inicio_paso = time.perf_counter()
        inicio_paso_fecha = (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        )

        estado["paso_actual"] = nombre
        guardar_estado()

        try:
            subprocess.run(
                comando,
                cwd=project_root,
                check=True,
            )

        except Exception as error:
            estado["ultimo_error"] = (
                f"{nombre}: {error}"
            )

            registrar_ejecucion_paso(
                nombre=nombre,
                inicio_monotono=inicio_paso,
                iniciado_en=inicio_paso_fecha,
                resultado="error",
                error=str(error),
            )

            if nombre == "Validaci?n del guion corregido":
                completados = estado.get(
                    "pasos_completados",
                    [],
                )

                if isinstance(completados, list):
                    while (
                        "Correcci?n y expansi?n del guion"
                        in completados
                    ):
                        completados.remove(
                            "Correcci?n y expansi?n del guion"
                        )

            guardar_estado()
            raise

        registrar_ejecucion_paso(
            nombre=nombre,
            inicio_monotono=inicio_paso,
            iniciado_en=inicio_paso_fecha,
            resultado="completado",
        )

        completados = estado.setdefault(
            "pasos_completados",
            [],
        )

        if (
            isinstance(completados, list)
            and nombre not in completados
        ):
            completados.append(nombre)

        estado["ultimo_error"] = ""
        guardar_estado()

    pasos: list[tuple[str, list[str]]] = []

    if not argumentos.omitir_doctor:
        pasos.append(
            (
                "Comprobaci?n del proyecto",
                ["doctor"],
            )
        )

    pasos.extend(
        [
            (
                "Generaci?n de ideas",
                [
                    "ideas",
                    "--nicho",
                    argumentos.nicho,
                    "--cantidad",
                    str(argumentos.cantidad_ideas),
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Generaci?n del guion",
                [
                    "script",
                    "--indice",
                    str(argumentos.indice),
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Correcci?n y expansi?n del guion",
                [
                    "script-fix",
                    "--ppm",
                    "145",
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Validaci?n del guion corregido",
                [
                    "script-check",
                    "--ppm",
                    "145",
                ],
            ),
            (
                "Generaci?n de narraci?n",
                [
                    "voice",
                    "--voz",
                    argumentos.voz,
                    f"--velocidad={argumentos.velocidad}",
                    f"--tono={argumentos.tono}",
                ],
            ),
            (
                "Creaci?n del plan visual",
                [
                    "visual-plan",
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Descarga de recursos",
                [
                    "assets",
                    "--limite",
                    "0",
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Generaci?n de recursos locales",
                [
                    "local-assets",
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Auditoria visual final",
                [
                    "visual-audit",
                    "--limite",
                    "0",
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Generacion de timeline semantica",
                [
                    "timeline",
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Archivo visual en Google Drive",
                [
                    "visual-cache",
                    "store",
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Renderizado del video",
                [
                    "render",
                    "--canal",
                    canal_slug,
                ],
            ),
            (
                "Generaci?n de subt?tulos",
                [
                    "subtitles",
                ],
            ),
        ]
    )

    total = len(pasos)
    estado["total_pasos"] = total
    guardar_estado()

    print()
    print("#" * 72)
    print(f"{nombre_canal.upper()} - PRODUCCION AUTOMATICA")
    print("#" * 72)
    print("Nicho:", argumentos.nicho)
    print("Idea seleccionada:", argumentos.indice)
    print("Pasos:", total)

    for numero, (nombre, parametros) in enumerate(
        pasos,
        start=1,
    ):
        completados = estado.get(
            "pasos_completados",
            [],
        )

        if (
            argumentos.reanudar
            and isinstance(completados, list)
            and nombre in completados
        ):
            print(
                f"PASO {numero}/{total} OMITIDO: "
                f"{nombre}"
            )
            continue

        ejecutar_paso(
            numero,
            total,
            nombre,
            parametros,
        )


    print()
    print("=" * 72)
    print("ETAPA FINAL AUTOMATICA")
    print("=" * 72)

    print("1/6 Finalizando video con subtitulos y musica...")
    finalizador = FinalizadorVideo(
        project_root=project_root,
    )
    video_final, video_generado = finalizador.finalizar()
    print(
        "Video final:",
        video_final,
        "|",
        "GENERADO" if video_generado else "REUTILIZADO",
    )

    print("2/6 Generando metadata y capitulos de YouTube...")
    generador_metadata = GeneradorMetadataYouTube(
        project_root=project_root,
        channel_slug=canal_slug,
    )
    metadata, metadata_path = generador_metadata.generar()
    print("Titulo:", metadata["title"])
    print("Metadata:", metadata_path)


    manifiesto_shorts_drive: Path | None = None

    if argumentos.sin_shorts:
        print("3/6 Shorts omitidos por --sin-shorts.")
    else:
        print("3/6 Generando Shorts verticales...")
        resultado_shorts = GeneradorShorts(
            project_root=project_root,
            channel_slug=canal_slug,
        ).generar(
            cantidad=argumentos.cantidad_shorts,
            duracion_objetivo=argumentos.duracion_short,
            solo_plan=False,
        )
        print(
            "Shorts generados:",
            resultado_shorts["cantidad"],
        )
        print(
            "Manifiesto de Shorts:",
            resultado_shorts["manifiesto"],
        )
        manifiesto_shorts_drive = Path(
            str(
                resultado_shorts[
                    "manifiesto"
                ]
            )
        ).resolve()

    print("4/6 Generando miniatura automatica...")
    generador_miniatura = GeneradorMiniaturaYouTube(
        project_root=project_root,
        channel_slug=canal_slug,
    )
    miniatura, miniatura_generada = generador_miniatura.generar()
    print(
        "Miniatura:",
        miniatura,
        "|",
        "GENERADA" if miniatura_generada else "REUTILIZADA",
    )

    control_multimedia = (
        project_root
        / "tools"
        / "media_quality_check.py"
    )

    if not control_multimedia.is_file():
        raise FileNotFoundError(
            "No existe el control multimedia: "
            f"{control_multimedia}"
        )

    comando_control = [
        sys.executable,
        str(control_multimedia),
    ]

    if not argumentos.sin_shorts:
        comando_control.append(
            "--validar-shorts"
        )

    if argumentos.control_profundo:
        comando_control.append(
            "--profundo"
        )

    print("Ejecutando control tecnico multimedia...")
    subprocess.run(
        comando_control,
        cwd=project_root,
        check=True,
    )

    respaldo_drive = (
        project_root
        / "tools"
        / "google_drive_backup.py"
    )

    if not respaldo_drive.is_file():
        raise FileNotFoundError(
            "No existe el respaldo de Google Drive: "
            f"{respaldo_drive}"
        )

    candidatos_subtitulos_drive = list(
        project_root.glob(
            "output/subtitles/subtitulos_*/subtitulos.srt"
        )
    )

    if not candidatos_subtitulos_drive:
        raise FileNotFoundError(
            "No se encontraron subtitulos para el respaldo."
        )

    subtitulos_drive = max(
        candidatos_subtitulos_drive,
        key=lambda ruta: ruta.stat().st_mtime,
    ).resolve()

    def respaldar_produccion_drive() -> None:
        comando_respaldo = [
            sys.executable,
            str(respaldo_drive),
            "--canal",
            canal_slug,
            "--video",
            str(Path(video_final).resolve()),
            "--miniatura",
            str(Path(miniatura).resolve()),
            "--subtitulos",
            str(subtitulos_drive),
            "--metadata",
            str(Path(metadata_path).resolve()),
        ]

        if manifiesto_shorts_drive is not None:
            comando_respaldo.extend(
                [
                    "--manifiesto-shorts",
                    str(manifiesto_shorts_drive),
                ]
            )

        subprocess.run(
            comando_respaldo,
            cwd=project_root,
            check=True,
        )

    print(
        "Respaldando produccion final "
        "en Google Drive..."
    )
    respaldar_produccion_drive()

    gestor_cola = (
        project_root
        / "tools"
        / "youtube_publish_queue.py"
    )

    if not gestor_cola.is_file():
        raise FileNotFoundError(
            "No existe el gestor de publicaciones: "
            f"{gestor_cola}"
        )

    def sincronizar_cola_pipeline() -> None:
        subprocess.run(
            [
                sys.executable,
                str(gestor_cola),
                "sync",
                "--canal",
                canal_slug,
            ],
            cwd=project_root,
            check=True,
        )

    print("Sincronizando cola segura de publicacion...")
    sincronizar_cola_pipeline()

    if argumentos.sin_publicar:
        print("5/6 YouTube omitido por --sin-publicar.")
    else:
        print(
            "5/6 Publicando documental en "
            f"{nombre_canal} como PRIVADO..."
        )
        publicador = project_root / "tools" / "youtube_publish_all.py"
        subprocess.run(
            [
                sys.executable,
                str(publicador),
                "--canal",
                canal_slug,
            ],
            cwd=project_root,
            check=True,
        )
        sincronizar_cola_pipeline()

    if argumentos.sin_publicar:
        print(
            "6/6 Publicacion de Shorts omitida "
            "por --sin-publicar."
        )
    elif argumentos.sin_shorts:
        print(
            "6/6 Publicacion de Shorts omitida "
            "por --sin-shorts."
        )
    else:
        print(
            f"6/6 Publicando Shorts en {nombre_canal} "
            "como PRIVADOS..."
        )

        publicador_shorts = (
            project_root
            / "tools"
            / "youtube_publish_shorts.py"
        )

        if not publicador_shorts.is_file():
            raise FileNotFoundError(
                "No existe el publicador de Shorts: "
                f"{publicador_shorts}"
            )

        subprocess.run(
            [
                sys.executable,
                str(publicador_shorts),
                "--canal",
                canal_slug,
            ],
            cwd=project_root,
            check=True,
        )
        sincronizar_cola_pipeline()

    if not argumentos.sin_publicar:
        print(
            "Sincronizando resultados de YouTube "
            "en Google Drive..."
        )
        respaldar_produccion_drive()

    if getattr(argumentos, "conservar_visuales_locales", False):
        print(
            "Recursos visuales locales conservados por "
            "--conservar-visuales-locales."
        )
        estado["cache_visual_local"] = "conservado"
    else:
        print(
            "Liberando recursos visuales locales despues "
            "de verificar Google Drive..."
        )
        herramienta_cache_visual = (
            project_root / "tools" / "google_drive_visual_cache.py"
        )

        try:
            subprocess.run(
                [
                    sys.executable,
                    str(herramienta_cache_visual),
                    "cleanup",
                    "--canal",
                    canal_slug,
                    "--confirmar",
                ],
                cwd=project_root,
                check=True,
            )
            estado["cache_visual_local"] = "liberado"

        except Exception as error_cache:
            estado["cache_visual_local"] = "conservado_por_error"
            estado["aviso_cache_visual"] = str(error_cache)
            print(
                "ADVERTENCIA: no se pudo liberar el cache visual local. "
                "Los archivos se conservaron para evitar cualquier perdida."
            )
            print(f"Detalle: {error_cache}")

    estado["completado"] = True
    estado["paso_actual"] = ""
    estado["ultimo_error"] = ""
    estado["finalizado_en"] = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )
    guardar_estado()

    print()
    print("#" * 72)
    print("PIPELINE DE PRODUCCI?N COMPLETADO")
    print("#" * 72)
    print(
        "Video, narraci?n, recursos y subt?tulos "
        "han sido generados."
    )
    print("Produccion final automatica completada.")
    if argumentos.sin_publicar:
        print("YouTube: OMITIDO por --sin-publicar")
    else:
        print(
            f"YouTube ({nombre_canal}): video subido "
            "en PRIVADO para revision."
        )



def capturar_tutorial(argumentos: argparse.Namespace) -> None:
    settings = load_settings()

    capturador = CapturadorTutorial(
        project_root=settings.project_root,
    )

    if argumentos.login:
        capturador.abrir_sesion(argumentos.login)
        return

    archivo = (
        Path(argumentos.manifiesto)
        if argumentos.manifiesto
        else None
    )

    manifiesto, ruta = cargar_manifiesto_tutorial(
        output_dir=settings.output_dir,
        archivo=archivo,
    )

    resultado = capturador.capturar(
        manifiesto=manifiesto,
        ruta_manifiesto=ruta,
        forzar=argumentos.forzar,
        limite=argumentos.limite,
        mostrar_navegador=argumentos.mostrar_navegador,
    )

    print("Capturas reales:", resultado["capturadas"])
    print("Errores:", resultado["errores"])
    print("Pendientes:", resultado["pendientes"])


def main() -> None:
    parser = crear_parser()
    argumentos = parser.parse_args()

    settings = load_settings()
    logger = configure_logging(settings)

    logger.info(
        "AutoTube AI iniciado | comando=%s | entorno=%s",
        argumentos.comando or "inicio",
        settings.environment,
    )

    try:

        if argumentos.comando == "run":
            ejecutar_pipeline(argumentos)
            return

        if argumentos.comando == "doctor":
            correcto = ejecutar_diagnostico()
            raise SystemExit(0 if correcto else 1)

        if argumentos.comando == "security":
            correcto = ejecutar_revision_seguridad()
            raise SystemExit(0 if correcto else 1)

        if argumentos.comando == "info":
            mostrar_informacion()
            return

        if argumentos.comando == "gemini-test":
            probar_gemini()
            return

        if argumentos.comando == "ideas":
            generar_ideas(argumentos)
            return

        if argumentos.comando == "script":
            generar_guion(argumentos)
            return

        if argumentos.comando == "script-check":
            revisar_guion(argumentos)
            return

        if argumentos.comando == "script-fix":
            corregir_guion(argumentos)
            return

        if argumentos.comando == "voice":
            generar_voz(argumentos)
            return

        if argumentos.comando == "visual-plan":
            generar_plan_visual(argumentos)
            return

        if argumentos.comando == "assets":
            descargar_recursos(argumentos)
            return

        if argumentos.comando == "local-assets":
            generar_recursos_locales(argumentos)
            return

        if argumentos.comando == "timeline":
            generar_timeline_semantica(argumentos)
            return

        if argumentos.comando == "visual-audit":
            auditar_visuales_finales(argumentos)
            return

        if argumentos.comando == "visual-cache":
            gestionar_cache_visual(argumentos)
            return

        if argumentos.comando == "code-backup":
            respaldar_codigo_drive(argumentos)
            return

        if argumentos.comando == "tutorial-capture":
            capturar_tutorial(argumentos)
            return

        if argumentos.comando == "render":
            renderizar_video(argumentos)
            return


        if argumentos.comando == "dashboard":
            generar_dashboard(argumentos)
            return



        if argumentos.comando == "storage-clean":
            limpiar_almacenamiento(argumentos)
            return

        if argumentos.comando == "guardian-run":
            ejecutar_guardian_automatico(argumentos)
            return

        if argumentos.comando == "scheduler":
            gestionar_programador_windows(argumentos)
            return

        if argumentos.comando == "encoder-check":
            comprobar_codificador(argumentos)
            return

        if argumentos.comando == "media-check":
            ejecutar_control_multimedia(argumentos)
            return

        if argumentos.comando in {
            "publish-status",
            "publish-queue",
            "publish-resume",
        }:
            gestionar_cola_publicacion(argumentos)
            return

        if argumentos.comando == "analytics":
            generar_analitica(argumentos)
            return

        if argumentos.comando == "analytics-insights":
            generar_insights_analitica(argumentos)
            return

        if argumentos.comando == "experiment":
            generar_experimento(argumentos)
            return

        if argumentos.comando == "experiment-result":
            registrar_resultado_experimento(argumentos)
            return

        if argumentos.comando == "shorts":
            generar_shorts(argumentos)
            return

        if argumentos.comando == "subtitles":
            generar_subtitulos(argumentos)
            return

    except Exception as error:
        logger.exception(
            "El comando %s falló.",
            argumentos.comando,
        )
        print(f"\nERROR: {error}")
        raise SystemExit(1) from error

    print("AutoTube AI está funcionando correctamente.")
    print("Usa 'autotube --help' para ver los comandos disponibles.")


if __name__ == "__main__":
    main()
