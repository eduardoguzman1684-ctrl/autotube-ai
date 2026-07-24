from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
import os


def create_video():

    print("🎬 Construyendo video por escenas...")

    audio = AudioFileClip("audio/voz.mp3")

    escenas = []

    imagenes = [
        "images/escena_1.txt",
        "images/escena_2.txt",
        "images/escena_3.txt",
        "images/escena_4.txt"
    ]


    duracion = audio.duration / len(imagenes)


    for imagen in imagenes:

        # Por ahora usamos fondo.jpg como imagen visual
        # hasta activar generación de imágenes IA

        clip = ImageClip(
            "config/fondo.jpg"
        )

        clip = clip.with_duration(duracion)

        # efecto zoom
        clip = clip.resized(
            lambda t: 1 + (0.03 * t)
        )

        escenas.append(clip)


    video = concatenate_videoclips(
        escenas,
        method="compose"
    )


    video = video.with_audio(audio)


    video.write_videofile(
        "videos/autotube_video.mp4",
        fps=24
    )


    return "videos/autotube_video.mp4"