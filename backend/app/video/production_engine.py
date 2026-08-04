import os
import logging

from moviepy import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips
)


logger = logging.getLogger(
    "AutoTubeAI"
)


OUTPUT_DIR = "videos/production"



def crear_directorio():

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )



def crear_clip_imagen(
    imagen,
    duracion
):

    clip = ImageClip(
        imagen
    )

    clip = clip.with_duration(
        duracion
    )

    # Zoom cinematográfico suave

    clip = clip.resized(
        1.05
    )

    return clip



def crear_video_documental(
    imagenes,
    audio=None
):

    crear_directorio()


    clips = []


    duracion_total = 0


    duracion_audio = None


    if audio and os.path.exists(audio):

        sonido = AudioFileClip(
            audio
        )

        duracion_audio = sonido.duration

        print(
            f"🎙️ Duración narración: {duracion_audio:.2f} segundos"
        )



    # Si hay audio, repartir duración

    if duracion_audio:

        duracion_escena = (
            duracion_audio /
            len(imagenes)
        )

    else:

        duracion_escena = 8



    for imagen in imagenes:

        print(
            "🎞️ Procesando:",
            imagen
        )


        clip = crear_clip_imagen(
            imagen,
            duracion_escena
        )


        clips.append(
            clip
        )


        duracion_total += duracion_escena



    video = concatenate_videoclips(
        clips
    )



    if audio and os.path.exists(audio):

        print(
            "🎙️ Añadiendo narración completa..."
        )

        video = video.with_audio(
            sonido
        )



    salida = (
        f"{OUTPUT_DIR}/"
        "documental_final.mp4"
    )


    print(
        "🎥 Exportando video..."
    )


    video.write_videofile(
        salida,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )


    video.close()


    print()
    print(
        "✅ VIDEO CREADO:"
    )
    print(
        salida
    )


    return salida



if __name__ == "__main__":


    imagenes = [

        "images/escena_1.png",
        "images/escena_2.png",
        "images/escena_3.png"

    ]


    crear_video_documental(
        imagenes,
        "audio/audio_final.mp3"
    )