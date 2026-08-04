import os

from moviepy import VideoFileClip, concatenate_videoclips


BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../../"
    )
)


SCENES_DIR = os.path.join(
    BASE_DIR,
    "videos",
    "scenes"
)


FINAL_DIR = os.path.join(
    BASE_DIR,
    "videos",
    "final"
)


OUTPUT = os.path.join(
    FINAL_DIR,
    "documental_autotube_16escenas.mp4"
)



def crear_documental():


    os.makedirs(
        FINAL_DIR,
        exist_ok=True
    )


    clips = []


    print()
    print("="*50)
    print("🎬 AUTOTUBE DOCUMENTAL BUILDER")
    print("="*50)



    for i in range(1,17):


        archivo = os.path.join(
            SCENES_DIR,
            f"escena_{i}.mp4"
        )


        if os.path.exists(archivo):

            print(
                f"✅ Añadiendo escena {i}"
            )


            clip = VideoFileClip(
                archivo
            )


            clips.append(
                clip
            )


        else:

            print(
                f"❌ No encontrada escena {i}"
            )



    print()

    print(
        f"🎞️ Total escenas cargadas: {len(clips)}"
    )



    if len(clips) != 16:

        raise Exception(
            "No se cargaron las 16 escenas"
        )



    print()

    print(
        "🔗 Uniendo las 16 escenas..."
    )


    final = concatenate_videoclips(
        clips,
        method="compose"
    )


    print()

    print(
        "⏱️ Duración:",
        final.duration,
        "segundos"
    )



    final.write_videofile(

        OUTPUT,

        fps=24,

        codec="libx264",

        audio=False,

        pixel_format="yuv420p"

    )



    final.close()


    for c in clips:

        c.close()



    print()

    print("="*50)

    print(
        "🎉 DOCUMENTAL CREADO:"
    )

    print(
        OUTPUT
    )

    print("="*50)




if __name__ == "__main__":

    crear_documental()