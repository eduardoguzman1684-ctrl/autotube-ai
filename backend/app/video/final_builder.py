import os

from moviepy import (
    VideoFileClip,
    concatenate_videoclips
)


BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../../"
    )
)


INPUT_DIR = os.path.join(
    BASE_DIR,
    "videos",
    "narrated"
)


OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "videos",
    "final"
)


OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "autotube_documental_final.mp4"
)


os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)



def cargar_escenas():

    escenas = []

    print("""
==================================================
🎬 AUTOTUBE AI FINAL BUILDER
==================================================
""")


    for i in range(1,17):

        archivo = os.path.join(
            INPUT_DIR,
            f"escena_{i}_final.mp4"
        )


        if os.path.exists(archivo):

            print(
                f"✅ Cargando escena {i}"
            )

            clip = VideoFileClip(
                archivo
            )

            escenas.append(
                clip
            )

        else:

            print(
                f"⚠️ Falta escena {i}"
            )


    return escenas



def crear_video():

    escenas = cargar_escenas()


    if not escenas:

        print(
            "❌ No hay escenas para unir"
        )

        return



    print()
    print(
        f"🎞️ Total escenas: {len(escenas)}"
    )


    print()
    print(
        "🔗 Uniendo documental..."
    )


    video_final = concatenate_videoclips(
        escenas,
        method="compose"
    )


    print()
    print(
        f"⏱️ Duración: {video_final.duration:.2f} segundos"
    )


    video_final.write_videofile(
        OUTPUT_FILE,
        codec="libx264",
        audio_codec="aac",
        fps=24,
        preset="medium",
        threads=4
    )


    video_final.close()


    for clip in escenas:
        clip.close()



    print("""
==================================================
🎉 DOCUMENTAL TERMINADO
==================================================
""")

    print(
        OUTPUT_FILE
    )



if __name__ == "__main__":
    crear_video()