from moviepy import (
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeAudioClip
)

import os
import glob



def crear_documental():

    print("\n🎬 CONSTRUYENDO DOCUMENTAL FINAL")
    print("="*50)


    escenas = sorted(
        glob.glob(
            "videos/scenes/*.mp4"
        )
    )


    if not escenas:
        raise Exception(
            "❌ No existen escenas animadas"
        )


    clips=[]


    for escena in escenas:

        print(
            "🎞️ Añadiendo:",
            escena
        )

        clips.append(
            VideoFileClip(escena)
        )


    video = concatenate_videoclips(
        clips,
        method="compose"
    )


    audio_path = (
        "audio/audio_final.mp3"
    )


    if os.path.exists(audio_path):

        print(
            "🎙️ Añadiendo narración..."
        )

        voz = AudioFileClip(
            audio_path
        )


        if video.duration < voz.duration:

            veces = int(
                voz.duration /
                video.duration
            ) + 1


            video = concatenate_videoclips(
                [video]*veces
            )


        video = video.subclipped(
            0,
            voz.duration
        )


        video = video.with_audio(
            voz
        )



    os.makedirs(
        "videos/final",
        exist_ok=True
    )


    salida = (
        "videos/final/"
        "documental_autotube.mp4"
    )


    print(
        "🎥 Exportando..."
    )


    video.write_videofile(
        salida,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )


    video.close()


    print(
        "\n✅ DOCUMENTAL CREADO:"
    )

    print(
        salida
    )



if __name__=="__main__":

    crear_documental()