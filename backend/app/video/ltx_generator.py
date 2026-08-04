import subprocess
import shutil
from pathlib import Path
import json
import os


# ============================================================
# AUTOTUBE AI - MOTOR LOCAL GRATUITO
# ============================================================
#
# IMPORTANTE:
# Este archivo conserva el nombre ltx_generator.py y la funciÃ³n
# generate_ltx_video() para no romper video_creator.py.
#
# YA NO UTILIZA LA API DE LTX.
#
# Utiliza:
#   - FFmpeg
#   - imÃ¡genes PNG
#   - narraciones WAV
#   - zoom/pan cinematogrÃ¡fico
#
# ============================================================


# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parents[3]

IMAGE_DIR = PROJECT_DIR / "images" / "generated"

NARRATION_DIR = PROJECT_DIR / "audio" / "narrations"

AUDIO_DIR = PROJECT_DIR / "audio"

VIDEO_DIR = PROJECT_DIR / "videos"

SCENES_DIR = VIDEO_DIR / "local_scenes"

OUTPUT_DEFAULT = VIDEO_DIR / "autotube_video.mp4"


# ============================================================
# CONFIGURACIÃ“N DE VIDEO
# ============================================================

WIDTH = 1920

HEIGHT = 1080

FPS = 24

VIDEO_CRF = "20"

VIDEO_PRESET = "medium"

AUDIO_BITRATE = "192k"


# ============================================================
# COMPROBAR FFMPEG
# ============================================================

def comprobar_ffmpeg():

    ffmpeg = shutil.which("ffmpeg")

    ffprobe = shutil.which("ffprobe")

    print()
    print("ðŸ”§ Comprobando FFmpeg...")

    print(
        "FFmpeg:",
        ffmpeg if ffmpeg else "NO ENCONTRADO"
    )

    print(
        "FFprobe:",
        ffprobe if ffprobe else "NO ENCONTRADO"
    )

    if not ffmpeg:

        raise RuntimeError(
            "âŒ FFmpeg no estÃ¡ instalado "
            "o no estÃ¡ disponible en PATH."
        )

    if not ffprobe:

        raise RuntimeError(
            "âŒ FFprobe no estÃ¡ instalado "
            "o no estÃ¡ disponible en PATH."
        )

    return ffmpeg, ffprobe


# ============================================================
# OBTENER DURACIÃ“N DEL AUDIO
# ============================================================

def obtener_duracion_audio(
    audio_file,
    ffprobe
):

    comando = [

        ffprobe,

        "-v",
        "error",

        "-show_entries",
        "format=duration",

        "-of",
        "default=noprint_wrappers=1:nokey=1",

        str(audio_file)
    ]

    resultado = subprocess.run(

        comando,

        capture_output=True,

        text=True
    )

    if resultado.returncode != 0:

        raise RuntimeError(
            "âŒ No se pudo obtener la duraciÃ³n de "
            f"{audio_file}\n"
            f"{resultado.stderr}"
        )

    try:

        duracion = float(
            resultado.stdout.strip()
        )

    except ValueError:

        raise RuntimeError(
            "âŒ DuraciÃ³n de audio invÃ¡lida: "
            f"{resultado.stdout}"
        )

    if duracion <= 0:

        raise RuntimeError(
            f"âŒ El audio tiene duraciÃ³n invÃ¡lida: "
            f"{duracion}"
        )

    return duracion


# ============================================================
# VERIFICAR IMAGEN
# ============================================================

def verificar_imagen(
    imagen
):

    imagen = Path(imagen)

    if not imagen.exists():

        raise FileNotFoundError(
            f"âŒ No existe imagen: {imagen}"
        )

    if imagen.stat().st_size == 0:

        raise RuntimeError(
            f"âŒ La imagen estÃ¡ vacÃ­a: {imagen}"
        )


# ============================================================
# VERIFICAR AUDIO
# ============================================================

def verificar_audio(
    audio
):

    audio = Path(audio)

    if not audio.exists():

        raise FileNotFoundError(
            f"âŒ No existe audio: {audio}"
        )

    if audio.stat().st_size == 0:

        raise RuntimeError(
            f"âŒ El audio estÃ¡ vacÃ­o: {audio}"
        )


# ============================================================
# CREAR ESCENA CINEMATOGRÃFICA
# ============================================================

def crear_escena(
    imagen,
    audio,
    salida,
    numero,
    ffmpeg,
    ffprobe
):

    imagen = Path(imagen)

    audio = Path(audio)

    salida = Path(salida)

    verificar_imagen(imagen)

    verificar_audio(audio)

    duracion = obtener_duracion_audio(
        audio,
        ffprobe
    )

    frames = max(
        int(duracion * FPS),
        1
    )

    print()
    print(
        f"ðŸŽ¬ ESCENA {numero}"
    )

    print(
        f"ðŸ–¼ï¸ Imagen: {imagen.name}"
    )

    print(
        f"ðŸŽ™ï¸ Audio: {audio.name}"
    )

    print(
        f"â±ï¸ DuraciÃ³n: {duracion:.2f} segundos"
    )

    print(
        f"ðŸŽžï¸ Frames: {frames}"
    )

    # --------------------------------------------------------
    # ALTERNAR MOVIMIENTOS
    # --------------------------------------------------------
    #
    # Escenas impares:
    #   zoom lento hacia el centro
    #
    # Escenas pares:
    #   zoom lento hacia afuera
    #
    # TambiÃ©n se introduce un pequeÃ±o desplazamiento.
    #
    # --------------------------------------------------------

    if numero % 4 == 1:

        zoom_expression = (
            "min(zoom+0.0008,1.10)"
        )

        x_expression = (
            "iw/2-(iw/zoom/2)"
        )

        y_expression = (
            "ih/2-(ih/zoom/2)"
        )

    elif numero % 4 == 2:

        zoom_expression = (
            "min(zoom+0.0007,1.08)"
        )

        x_expression = (
            "iw/2-(iw/zoom/2)+on*0.12"
        )

        y_expression = (
            "ih/2-(ih/zoom/2)"
        )

    elif numero % 4 == 3:

        zoom_expression = (
            "min(zoom+0.0007,1.08)"
        )

        x_expression = (
            "iw/2-(iw/zoom/2)-on*0.10"
        )

        y_expression = (
            "ih/2-(ih/zoom/2)+on*0.05"
        )

    else:

        zoom_expression = (
            "min(zoom+0.0008,1.10)"
        )

        x_expression = (
            "iw/2-(iw/zoom/2)"
        )

        y_expression = (
            "ih/2-(ih/zoom/2)-on*0.05"
        )

    # --------------------------------------------------------
    # FILTRO ZOOMPAN
    # --------------------------------------------------------

    filtro = (

        "scale=3840:2160:force_original_aspect_ratio=decrease,"
        "pad=3840:2160:(ow-iw)/2:(oh-ih)/2,"
        
        "crop=3840:2160,"
        
        f"zoompan="
        f"z='{zoom_expression}':"
        f"x='{x_expression}':"
        f"y='{y_expression}':"
        f"d={frames}:"
        f"s={WIDTH}x{HEIGHT}:"
        f"fps={FPS},"

        "format=yuv420p"
    )

    # --------------------------------------------------------
    # COMANDO FFMPEG
    # --------------------------------------------------------

    comando = [

        ffmpeg,

        "-y",

        "-hide_banner",

        "-loglevel",
        "warning",

        # ----------------------------------------------------
        # IMAGEN
        # ----------------------------------------------------

        "-loop",
        "1",

        "-i",
        str(imagen),

        # ----------------------------------------------------
        # AUDIO
        # ----------------------------------------------------

        "-i",
        str(audio),

        # ----------------------------------------------------
        # FILTRO
        # ----------------------------------------------------

        "-vf",
        filtro,

        # ----------------------------------------------------
        # DURACIÃ“N
        # ----------------------------------------------------

        "-t",
        f"{duracion:.3f}",

        # ----------------------------------------------------
        # VIDEO
        # ----------------------------------------------------

        "-c:v",
        "libx264",

        "-preset",
        VIDEO_PRESET,

        "-crf",
        VIDEO_CRF,

        "-pix_fmt",
        "yuv420p",

        "-r",
        str(FPS),

        # ----------------------------------------------------
        # AUDIO
        # ----------------------------------------------------

        "-c:a",
        "aac",

        "-b:a",
        AUDIO_BITRATE,

        # ----------------------------------------------------
        # TERMINAR CON EL AUDIO
        # ----------------------------------------------------

        "-shortest",

        # ----------------------------------------------------
        # SALIDA
        # ----------------------------------------------------

        str(salida)
    ]

    print(
        "âš™ï¸ Renderizando escena..."
    )

    resultado = subprocess.run(
        comando,
        capture_output=True,
        text=True
    )

    if resultado.returncode != 0:

        print()
        print(
            "âŒ FFmpeg devolviÃ³ un error:"
        )

        print(
            resultado.stderr
        )

        raise RuntimeError(
            f"âŒ Error renderizando escena {numero}"
        )

    if not salida.exists():

        raise RuntimeError(
            f"âŒ FFmpeg terminÃ³ pero no creÃ³: "
            f"{salida}"
        )

    if salida.stat().st_size < 10000:

        raise RuntimeError(
            f"âŒ El video generado parece invÃ¡lido: "
            f"{salida}"
        )

    size_mb = (
        salida.stat().st_size
        / 1024
        / 1024
    )

    print(
        f"âœ… Escena {numero} creada"
    )

    print(
        f"ðŸ“¦ TamaÃ±o: {size_mb:.2f} MB"
    )

    return salida


# ============================================================
# UNIR ESCENAS
# ============================================================

def unir_escenas(
    videos,
    salida_final,
    ffmpeg
):

    print()
    print("=" * 60)
    print("ðŸ”— UNIENDO ESCENAS")
    print("=" * 60)

    lista = (
        VIDEO_DIR /
        "concat_local.txt"
    )

    with open(
        lista,
        "w",
        encoding="utf-8"
    ) as f:

        for video in videos:

            ruta = (
                Path(video)
                .resolve()
                .as_posix()
            )

            # Escapar comillas simples
            ruta = ruta.replace(
                "'",
                "'\\''"
            )

            f.write(
                f"file '{ruta}'\n"
            )

    comando = [

        ffmpeg,

        "-y",

        "-hide_banner",

        "-loglevel",
        "warning",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        str(lista),

        "-c",
        "copy",

        str(salida_final)
    ]

    print(
        "ðŸ”— Concatenando..."
    )

    resultado = subprocess.run(

        comando,

        capture_output=True,

        text=True
    )

    if resultado.returncode != 0:

        print()
        print(
            "âš ï¸ La uniÃ³n directa fallÃ³."
        )

        print(
            "ðŸ”„ Intentando una uniÃ³n con recodificaciÃ³n..."
        )

        comando_fallback = [

            ffmpeg,

            "-y",

            "-hide_banner",

            "-loglevel",
            "warning",

            "-f",
            "concat",

            "-safe",
            "0",

            "-i",
            str(lista),

            "-c:v",
            "libx264",

            "-preset",
            VIDEO_PRESET,

            "-crf",
            VIDEO_CRF,

            "-c:a",
            "aac",

            "-b:a",
            AUDIO_BITRATE,

            "-pix_fmt",
            "yuv420p",

            "-r",
            str(FPS),

            str(salida_final)
        ]

        resultado = subprocess.run(

            comando_fallback,

            capture_output=True,

            text=True
        )

    if resultado.returncode != 0:

        print(
            resultado.stderr
        )

        raise RuntimeError(
            "âŒ No se pudieron unir las escenas."
        )

    if not salida_final.exists():

        raise RuntimeError(
            "âŒ No se creÃ³ el video final."
        )

    size_mb = (
        salida_final.stat().st_size
        / 1024
        / 1024
    )

    print()
    print(
        "âœ… VIDEO FINAL CREADO"
    )

    print(
        f"ðŸ“¹ Archivo: {salida_final}"
    )

    print(
        f"ðŸ“¦ TamaÃ±o: {size_mb:.2f} MB"
    )

    return salida_final


# ============================================================
# MOTOR PRINCIPAL
# ============================================================

def generate_ltx_video(
    images,
    audio_file,
    output
):

    print()
    print("=" * 60)
    print("ðŸŽ¬ AUTOTUBE AI - MOTOR LOCAL GRATUITO")
    print("=" * 60)

    print()
    print(
        "ðŸš« LTX API: DESACTIVADA"
    )

    print(
        "ðŸ’° Costo de API: $0"
    )

    print(
        "ðŸŽžï¸ Motor: FFmpeg"
    )

    print(
        "ðŸŽ¥ Efecto: Zoom/Pan cinematogrÃ¡fico"
    )

    print()

    # --------------------------------------------------------
    # FFMPEG
    # --------------------------------------------------------

    ffmpeg, ffprobe = comprobar_ffmpeg()

    # --------------------------------------------------------
    # RUTAS
    # --------------------------------------------------------

    SCENES_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    VIDEO_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # IMÃGENES
    # --------------------------------------------------------

    images = [
        Path(x)
        for x in images
    ]

    images.sort(
        key=lambda x: int(
            x.stem.replace(
                "escena_",
                ""
            )
        )
    )

    if not images:

        raise RuntimeError(
            "âŒ No hay imÃ¡genes."
        )

    # --------------------------------------------------------
    # AUDIO
    # --------------------------------------------------------

    print(
        "ðŸ“‚ Directorio imÃ¡genes:"
    )

    print(
        IMAGE_DIR
    )

    print()

    print(
        "ðŸ“‚ Directorio narraciones:"
    )

    print(
        NARRATION_DIR
    )

    # --------------------------------------------------------
    # COMPROBAR 16 ESCENAS
    # --------------------------------------------------------

    print()

    print(
        f"ðŸ–¼ï¸ ImÃ¡genes recibidas: "
        f"{len(images)}"
    )

    narraciones = []

    for i in range(
        1,
        len(images) + 1
    ):

        audio = (
            NARRATION_DIR /
            f"escena_{i}.wav"
        )

        if not audio.exists():

            raise FileNotFoundError(
                f"âŒ Falta narraciÃ³n: "
                f"{audio}"
            )

        narraciones.append(
            audio
        )

    print(
        f"ðŸŽ™ï¸ Narraciones encontradas: "
        f"{len(narraciones)}"
    )

    # --------------------------------------------------------
    # GENERAR ESCENAS
    # --------------------------------------------------------

    videos = []

    for index, (
        image,
        audio
    ) in enumerate(
        zip(
            images,
            narraciones
        ),
        start=1
    ):

        salida_escena = (

            SCENES_DIR /
            f"escena_{index:02d}.mp4"
        )

        video = crear_escena(

            image,

            audio,

            salida_escena,

            index,

            ffmpeg,

            ffprobe
        )

        videos.append(
            video
        )

    # --------------------------------------------------------
    # UNIR
    # --------------------------------------------------------

    output = Path(
        output
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    video_final = unir_escenas(

        videos,

        output,

        ffmpeg
    )

    # --------------------------------------------------------
    # LIMPIEZA DEL ARCHIVO CONCAT
    # --------------------------------------------------------

    concat_file = (
        VIDEO_DIR /
        "concat_local.txt"
    )

    try:

        if concat_file.exists():

            concat_file.unlink()

    except Exception:

        pass

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("ðŸŽ‰ AUTOTUBE AI TERMINADO")
    print("=" * 60)

    print()
    print(
        "ðŸ“¹ VIDEO:"
    )

    print(
        video_final
    )

    print()
    print(
        "ðŸŽ™ï¸ VOZ:"
    )

    print(
        "XTTS v2 - voz femenina natural"
    )

    print()
    print(
        "ðŸŽžï¸ ESCENAS:"
    )

    print(
        len(videos)
    )

    print()
    print(
        "ðŸ¤– LTX:"
    )

    print(
        "No utilizado"
    )

    return str(
        video_final
    )


# ============================================================
# EJECUCIÃ“N DIRECTA
# ============================================================

if __name__ == "__main__":

    print()
    print(
        "â„¹ï¸ Este archivo es un mÃ³dulo."
    )

    print(
        "â„¹ï¸ Ejecuta:"
    )

    print(
        "python backend\\app\\video\\video_creator.py"
    )
