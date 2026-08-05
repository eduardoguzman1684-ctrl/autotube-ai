from __future__ import annotations

import argparse
from pathlib import Path

from autotube.ai.gemini_client import GeminiClient
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