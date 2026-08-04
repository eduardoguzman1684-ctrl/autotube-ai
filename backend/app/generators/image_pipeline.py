import json
import logging
from pathlib import Path

from image_ai import generate_ai_image
from image_manager import generar_imagen_pollinations


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)



BASE_DIR = Path(__file__).resolve().parent.parent

CACHE_DIR = BASE_DIR / "cache"

IMAGE_DIR = BASE_DIR / "images"

IMAGE_DIR.mkdir(
    exist_ok=True
)


SCENES_FILE = CACHE_DIR / "images.json"



def cargar_escenas():

    with open(
        SCENES_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)




def generar_imagenes_reales():


    logging.info(
        "🎨 Iniciando motor de imágenes IA"
    )


    escenas = cargar_escenas()


    resultados = []


    for escena in escenas:


        numero = escena["escena"]


        prompt = escena["prompt"]


        filename = IMAGE_DIR / (
            f"escena_{numero:03}.jpg"
        )


        imagen = None



        # ==================================
        # PRUEBA STABILITY AI
        # ==================================

        try:

            logging.info(
                f"Probando Stability escena {numero}"
            )


            imagen = generate_ai_image(

                prompt,

                numero

            )


        except Exception as error:

            logging.warning(
                f"Stability falló: {error}"
            )



        # ==================================
        # RESPALDO POLLINATIONS
        # ==================================

        if not imagen:


            logging.info(
                f"Usando Pollinations escena {numero}"
            )


            generar_imagen_pollinations(

                prompt,

                str(filename)

            )


            imagen = str(filename)



        resultados.append({

            "escena": numero,

            "archivo": imagen,

            "estado": "generada"

        })



    salida = CACHE_DIR / "generated_images.json"


    with open(
        salida,
        "w",
        encoding="utf-8"
    ) as f:


        json.dump(

            resultados,

            f,

            indent=4,

            ensure_ascii=False

        )



    logging.info(
        "✅ Imágenes generadas correctamente"
    )


    return resultados





if __name__ == "__main__":


    imagenes = generar_imagenes_reales()


    print("\n==============================")
    print("🎨 IMÁGENES TERMINADAS")
    print("==============================\n")


    for img in imagenes:

        print(
            "Escena:",
            img["escena"]
        )

        print(
            "Archivo:",
            img["archivo"]
        )

        print(
            "Estado:",
            img["estado"]
        )

        print("--------------------")