import os
import sys
from pathlib import Path

from moviepy import AudioFileClip, concatenate_audioclips

# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parents[3]

IMAGE_DIR = PROJECT_DIR / "images" / "generated"
NARRATION_DIR = PROJECT_DIR / "audio" / "narrations"
AUDIO_DIR = PROJECT_DIR / "audio"
VIDEO_DIR = PROJECT_DIR / "videos"

AUDIO_FINAL = AUDIO_DIR / "audio_final.mp3"
OUTPUT_FILE = VIDEO_DIR / "autotube_video.mp4"


# ============================================================
# IMPORTAR MOTOR LTX
# ============================================================

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ltx_generator import generate_ltx_video


# ============================================================
# BUSCAR IMÁGENES
# ============================================================

def buscar_imagenes():
    imagenes = []

    for archivo in IMAGE_DIR.glob("escena_*.png"):
        imagenes.append(archivo)

    imagenes.sort(
        key=lambda x: int(
            x.stem.replace("escena_", "")
        )
    )

    return imagenes


# ============================================================
# BUSCAR NARRACIONES
# ============================================================

def buscar_narraciones():
    audios = []

    for archivo in NARRATION_DIR.glob("escena_*.wav"):
        audios.append(archivo)

    audios.sort(
        key=lambda x: int(
            x.stem.replace("escena_", "")
        )
    )

    return audios


# ============================================================
# CREAR AUDIO FINAL
# ============================================================

def crear_audio_final(narraciones):
    print()
    print("=" * 60)
    print("🎙️ UNIENDO NARRACIONES")
    print("=" * 60)

    if not narraciones:
        raise RuntimeError(
            "❌ No se encontraron narraciones WAV."
        )

    clips = []

    try:
        for i, archivo in enumerate(narraciones, start=1):
            print(
                f"🎙️ Cargando narración {i}/{len(narraciones)}: "
                f"{archivo.name}"
            )

            clip = AudioFileClip(str(archivo))
            clips.append(clip)

        print()
        print("🔗 Uniendo las 16 narraciones...")

        audio_final = concatenate_audioclips(clips)

        print(
            f"⏱️ Duración total: "
            f"{audio_final.duration:.2f} segundos"
        )

        print()
        print("💾 Exportando audio final...")

        audio_final.write_audiofile(
            str(AUDIO_FINAL),
            codec="mp3",
            bitrate="192k",
            logger="bar",
        )

        audio_final.close()

        print()
        print("✅ Audio final creado:")
        print(AUDIO_FINAL)

        return AUDIO_FINAL

    finally:
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass


# ============================================================
# VERIFICAR ARCHIVOS
# ============================================================

def verificar_archivos(imagenes, narraciones):
    print()
    print("=" * 60)
    print("🔎 VERIFICANDO ARCHIVOS")
    print("=" * 60)

    print(f"🖼️ Imágenes: {len(imagenes)}")
    print(f"🎙️ Narraciones: {len(narraciones)}")

    if len(imagenes) != 16:
        raise RuntimeError(
            f"❌ Se esperaban 16 imágenes, pero hay {len(imagenes)}."
        )

    if len(narraciones) != 16:
        raise RuntimeError(
            f"❌ Se esperaban 16 narraciones, pero hay {len(narraciones)}."
        )

    for i in range(1, 17):
        imagen = IMAGE_DIR / f"escena_{i}.png"
        audio = NARRATION_DIR / f"escena_{i}.wav"

        if not imagen.exists():
            raise FileNotFoundError(
                f"❌ Falta imagen: {imagen}"
            )

        if not audio.exists():
            raise FileNotFoundError(
                f"❌ Falta narración: {audio}"
            )

    print("✅ Las 16 imágenes existen.")
    print("✅ Las 16 narraciones existen.")
    print("✅ Archivos verificados correctamente.")


# ============================================================
# CREAR VIDEO
# ============================================================

def create_video():

    print()
    print("=" * 60)
    print("🎬 AUTOTUBE AI VIDEO ENGINE")
    print("=" * 60)

    print()
    print("📁 Proyecto:")
    print(PROJECT_DIR)

    # --------------------------------------------------------
    # IMÁGENES
    # --------------------------------------------------------

    imagenes = buscar_imagenes()

    # --------------------------------------------------------
    # NARRACIONES
    # --------------------------------------------------------

    narraciones = buscar_narraciones()

    # --------------------------------------------------------
    # VERIFICACIÓN
    # --------------------------------------------------------

    verificar_archivos(
        imagenes,
        narraciones
    )

    # --------------------------------------------------------
    # MOSTRAR IMÁGENES
    # --------------------------------------------------------

    print()
    print("🖼️ IMÁGENES SELECCIONADAS:")

    for i, imagen in enumerate(imagenes, start=1):
        print(
            f"  {i:02d}. {imagen.name}"
        )

    # --------------------------------------------------------
    # MOSTRAR NARRACIONES
    # --------------------------------------------------------

    print()
    print("🎙️ NARRACIONES SELECCIONADAS:")

    for i, audio in enumerate(narraciones, start=1):
        print(
            f"  {i:02d}. {audio.name}"
        )

    # --------------------------------------------------------
    # CREAR AUDIO FINAL
    # --------------------------------------------------------

    audio_final = crear_audio_final(
        narraciones
    )

    # --------------------------------------------------------
    # LANZAR LTX
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("🤖 INICIANDO LTX VIDEO ENGINE")
    print("=" * 60)

    print()
    print("🖼️ Escenas:", len(imagenes))
    print("🎙️ Audio:", audio_final)
    print("🎬 Salida:", OUTPUT_FILE)

    video = generate_ltx_video(
        [str(x) for x in imagenes],
        str(audio_final),
        str(OUTPUT_FILE)
    )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("🎉 VIDEO DOCUMENTAL CREADO")
    print("=" * 60)

    print()
    print("📹 Archivo:")
    print(video)

    print()
    print("📁 Ubicación:")
    print(OUTPUT_FILE)

    return video


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    try:
        create_video()

    except KeyboardInterrupt:

        print()
        print("⚠️ Proceso cancelado por el usuario.")

    except Exception as e:

        print()
        print("=" * 60)
        print("❌ ERROR")
        print("=" * 60)

        print()
        print(type(e).__name__)
        print(str(e))

        raise