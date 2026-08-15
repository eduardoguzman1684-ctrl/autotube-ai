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
from autotube.video.composer import (
    CompositorVideo,
    cargar_contexto_render,
)
from autotube.video.subtitle_generator import (
    GeneradorSubtitulos,
    cargar_audio_para_subtitulos,
)
from autotube.video.finalizer import FinalizadorVideo
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
        default="-4%",
        help="Velocidad de la narración.",
    )

    voice_parser.add_argument(
        "--tono",
        default="-2Hz",
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
        default="-4%",
        help="Velocidad de narraci?n.",
    )

    run_parser.add_argument(
        "--tono",
        default="-2Hz",
        help="Tono de narraci?n.",
    )

    run_parser.add_argument(
        "--omitir-doctor",
        action="store_true",
        help="No ejecuta la comprobaci?n inicial del proyecto.",
    )


    run_parser.add_argument(
        "--sin-publicar",
        action="store_true",
        help="Completa el video pero no lo sube a YouTube.",
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

    print("\nGENERADOR DE IDEAS")
    print("=" * 70)
    print(f"Nicho: {argumentos.nicho}")
    print(f"Cantidad solicitada: {argumentos.cantidad}")
    print("Generando ideas...")

    resultado = generador.generar(
        nicho=argumentos.nicho,
        cantidad=argumentos.cantidad,
        idioma=argumentos.idioma,
        data_dir=settings.data_dir,
    )

    ruta = generador.guardar(
        resultado=resultado,
        data_dir=settings.data_dir,
    )

    print("=" * 70)

    for numero, idea in enumerate(resultado["ideas"], start=1):
        print(f"\n{numero}. {idea['titulo']}")
        print(f"   Formato: {idea['formato']}")
        print(f"   Duración: {idea['duracion_minutos']} minutos")
        print(f"   Palabra clave: {idea['palabra_clave']}")
        print(f"   Potencial: {idea['potencial']}")
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

    archivo = (
        Path(argumentos.archivo)
        if argumentos.archivo
        else None
    )

    idea, archivo_ideas = cargar_idea(
        data_dir=settings.data_dir,
        indice=argumentos.indice,
        archivo=archivo,
    )

    print("\nGENERADOR DE GUIONES")
    print("=" * 70)
    print(f"Archivo de ideas: {archivo_ideas}")
    print(f"Idea seleccionada: {argumentos.indice}")
    print(f"Título: {idea.get('titulo', 'Sin título')}")
    print("Generando guion...")

    generador = GeneradorGuiones()

    resultado = generador.generar(
        idea=idea,
        idioma=argumentos.idioma,
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
    print("=" * 72)


def generar_plan_visual(argumentos: argparse.Namespace) -> None:
    """Crea un plan visual sincronizado con el audio."""
    settings = load_settings()

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
    )

    resumen = resultado["resumen"]

    print("\n" + "=" * 72)
    print(
        f"Recursos descargados: "
        f"{resumen['descargados']}"
    )
    print(
        f"Pendientes de generación local: "
        f"{resumen['pendientes_generacion']}"
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

    cantidad_total = len(
        assets.get("elementos", [])
    )

    print("\nCOMPOSITOR DE VIDEO")
    print("=" * 72)
    print(f"Recursos: {ruta_assets}")
    print(f"Audio: {ruta_audio}")
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




def ejecutar_pipeline(argumentos: argparse.Namespace) -> None:
    """Ejecuta de principio a fin la producci?n autom?tica del video."""

    import shutil
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]

    autotube_exe = shutil.which("autotube")

    if autotube_exe:
        base_command = [autotube_exe]
    else:
        base_command = [
            sys.executable,
            "-c",
            "from autotube.main import main; main()",
        ]

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

        subprocess.run(
            comando,
            cwd=project_root,
            check=True,
        )

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
                ],
            ),
            (
                "Generaci?n del guion",
                [
                    "script",
                    "--indice",
                    str(argumentos.indice),
                ],
            ),
            (
                "Correcci?n y expansi?n del guion",
                [
                    "script-fix",
                    "--ppm",
                    "145",
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
                ],
            ),
            (
                "Descarga de recursos",
                [
                    "assets",
                    "--limite",
                    "0",
                ],
            ),
            (
                "Generaci?n de recursos locales",
                [
                    "local-assets",
                ],
            ),
            (
                "Renderizado del video",
                [
                    "render",
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

    print()
    print("#" * 72)
    print("NEXON IA - PRODUCCI?N AUTOM?TICA")
    print("#" * 72)
    print("Nicho:", argumentos.nicho)
    print("Idea seleccionada:", argumentos.indice)
    print("Pasos:", total)

    for numero, (nombre, parametros) in enumerate(
        pasos,
        start=1,
    ):
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

    print("1/4 Finalizando video con subtitulos y musica...")
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

    print("2/4 Generando metadata y capitulos de YouTube...")
    generador_metadata = GeneradorMetadataYouTube(
        project_root=project_root,
    )
    metadata, metadata_path = generador_metadata.generar()
    print("Titulo:", metadata["title"])
    print("Metadata:", metadata_path)

    print("3/4 Generando miniatura automatica...")
    generador_miniatura = GeneradorMiniaturaYouTube(
        project_root=project_root,
    )
    miniatura, miniatura_generada = generador_miniatura.generar()
    print(
        "Miniatura:",
        miniatura,
        "|",
        "GENERADA" if miniatura_generada else "REUTILIZADA",
    )

    if argumentos.sin_publicar:
        print("4/4 YouTube omitido por --sin-publicar.")
    else:
        print("4/4 Publicando en YouTube como PRIVADO...")
        publicador = project_root / "tools" / "youtube_publish_all.py"
        subprocess.run(
            [
                sys.executable,
                str(publicador),
            ],
            cwd=project_root,
            check=True,
        )

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
        print("YouTube: video subido en PRIVADO para revision.")



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

        if argumentos.comando == "tutorial-capture":
            capturar_tutorial(argumentos)
            return

        if argumentos.comando == "render":
            renderizar_video(argumentos)
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
