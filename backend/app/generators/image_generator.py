import os
import logging
from datetime import datetime


# =====================================
# AUTOTUBE AI v2.0
# GENERADOR DE IMÁGENES
# =====================================


logger = logging.getLogger(
    "AutoTubeAI"
)



OUTPUT_DIR = "images/generated"



def preparar_directorio():

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )



def generar_imagenes(
    escenas
):

    preparar_directorio()


    logger.info(
        "🎨 Preparando imágenes documentales"
    )


    imagenes = []


    for escena in escenas:


        numero = escena["numero"]


        nombre = (
            f"{OUTPUT_DIR}/"
            f"escena_{numero}.txt"
        )


        with open(
            nombre,
            "w",
            encoding="utf-8"
        ) as archivo:


            archivo.write(
                "PROMPT DE IMAGEN IA\n\n"
            )


            archivo.write(
                escena["imagen_prompt"]
            )


            archivo.write(
                "\n\nCreado:"
            )


            archivo.write(
                str(datetime.now())
            )



        imagenes.append(
            nombre
        )


        print(
            f"✅ Preparada escena {numero}: {nombre}"
        )



    return imagenes



if __name__ == "__main__":


    escenas_prueba = [


        {

            "numero":1,

            "imagen_prompt":
            (
                "Antigua ciudad hitita "
                "con estilo documental "
                "cinematográfico"
            )

        },


        {

            "numero":2,

            "imagen_prompt":
            (
                "Guerreros hititas "
                "en una batalla antigua"
            )

        },


        {

            "numero":3,

            "imagen_prompt":
            (
                "Ruinas arqueológicas "
                "al atardecer"
            )

        }

    ]



    generar_imagenes(
        escenas_prueba
    )