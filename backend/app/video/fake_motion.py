import os
import random

from moviepy import ImageClip, CompositeVideoClip


# =====================================
# AUTOTUBE AI
# FAKE MOTION ENGINE v2.1
# COMPATIBLE MOVIEPY 2.x
# =====================================


BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../../"
    )
)


IMAGE_DIR = os.path.join(
    BASE_DIR,
    "images",
    "generated"
)


VIDEO_DIR = os.path.join(
    BASE_DIR,
    "videos",
    "scenes"
)


DURATION = 8



def crear_movimiento(
    imagen,
    salida
):


    print(
        f"🎥 Procesando: {imagen}"
    )


    clip = ImageClip(
        imagen
    )


    clip = clip.with_duration(
        DURATION
    )


    clip = clip.resized(
        height=1080
    )


    zoom = random.choice(
        [
            1.05,
            1.08,
            1.10
        ]
    )


    clip = clip.resized(

        lambda t:

        1 + ((zoom - 1) * t / DURATION)

    )



    video = CompositeVideoClip(

        [
            clip
        ]

    )



    video.write_videofile(

        salida,

        fps=30,

        codec="libx264",

        audio=False,

        logger=None

    )


    video.close()

    clip.close()



    print(
        "✅ Creado:",
        salida
    )





def producir_movimiento():


    os.makedirs(

        VIDEO_DIR,

        exist_ok=True

    )


    creados = 0



    print()

    print(
        "=" * 50
    )

    print(
        "🎬 AUTOTUBE FAKE MOTION ENGINE"
    )

    print(
        "=" * 50
    )



    for i in range(1,17):


        imagen = os.path.join(

            IMAGE_DIR,

            f"escena_{i}.png"

        )



        salida = os.path.join(

            VIDEO_DIR,

            f"escena_{i}.mp4"

        )



        if not os.path.exists(imagen):

            print(
                "❌ No existe:",
                imagen
            )

            continue



        crear_movimiento(

            imagen,

            salida

        )


        creados += 1



    print()

    print(
        "=" * 50
    )

    print(
        f"🎉 VIDEOS CREADOS: {creados}"
    )

    print(
        "=" * 50
    )





if __name__ == "__main__":

    producir_movimiento()