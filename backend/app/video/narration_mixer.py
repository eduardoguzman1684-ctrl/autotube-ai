import os

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips
)


BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../../"
    )
)

VIDEOS_DIR = os.path.join(
    BASE_DIR,
    "videos",
    "scenes"
)

AUDIO_DIR = os.path.join(
    BASE_DIR,
    "audio",
    "narrations"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "videos",
    "narrated"
)


os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)



def ajustar_video(video, duracion):

    clips = []

    tiempo = 0

    while tiempo < duracion:

        clips.append(
            video.copy()
        )

        tiempo += video.duration


    resultado = concatenate_videoclips(
        clips
    )


    return resultado.subclipped(
        0,
        duracion
    )



def mezclar(numero):

    video_file = os.path.join(
        VIDEOS_DIR,
        f"escena_{numero}.mp4"
    )


    audio_file = os.path.join(
        AUDIO_DIR,
        f"escena_{numero}.wav"
    )


    salida = os.path.join(
        OUTPUT_DIR,
        f"escena_{numero}_final.mp4"
    )


    print(
        f"\n🎬 Escena {numero}"
    )


    video = VideoFileClip(
        video_file
    )


    audio = AudioFileClip(
        audio_file
    )


    video = ajustar_video(
        video,
        audio.duration
    )


    video = video.with_audio(
        audio
    )


    video.write_videofile(
        salida,
        codec="libx264",
        audio_codec="aac",
        fps=24,
        preset="medium"
    )


    video.close()
    audio.close()


    print(
        f"✅ {salida}"
    )



def main():

    print("""
==================================================
🎙️ AUTOTUBE AI NARRATION MIXER V2
==================================================
""")


    total = 0


    for i in range(1,17):

        try:

            mezclar(i)
            total += 1

        except Exception as e:

            print(
                f"❌ Error escena {i}: {e}"
            )


    print("""
==================================================
🎉 ESCENAS NARRADAS:
""",
          total,
          """
==================================================
""")


if __name__ == "__main__":
    main()