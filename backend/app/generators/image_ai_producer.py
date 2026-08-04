import os
import requests

from dotenv import load_dotenv


# =====================================
# AUTOTUBE AI
# SAFE IMAGE PRODUCER
# =====================================


BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../../"
    )
)


load_dotenv(
    os.path.join(BASE_DIR, ".env")
)



OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "images",
    "generated"
)



def get_key():

    key = os.getenv(
        "STABILITY_API_KEY"
    )


    if not key:

        raise Exception(
            "STABILITY_API_KEY faltante"
        )


    print(
        "🔑 Stability AI KEY encontrada: True"
    )


    return key





ESCENAS = [

"Ancient Hittite civilization landscape, stone city, archaeological ruins, historical documentary style",

"Ancient Anatolia map landscape, mountains and old settlements, cinematic history documentary",

"Ancient civilization origins, old stone buildings, archaeological discovery, realistic documentary",

"Ancient village in Anatolia, historical architecture, peaceful landscape, cinematic documentary",

"Ancient kingdom palace, stone walls, historical environment, museum documentary style",

"Ancient ruler palace, historical clothing, civilization documentary scene",

"Ancient warriors and historical city, no combat, cultural documentary scene",

"Ancient stone architecture, temples and city structures, archaeological documentary",

"Ancient writing tablets, symbols, archaeology museum, historical documentary",

"Ancient temples and cultural traditions, peaceful historical scene",

"Ancient civilizations meeting, diplomacy, historical documentary",

"Ancient city panorama, historical events documentary style",

"Ancient markets, trade routes, old civilization economy documentary",

"Ancient abandoned city ruins, mysterious archaeological landscape",

"Archaeologists discovering ancient ruins, museum documentary scene",

"Ancient civilization legacy, ruins at sunset, cinematic documentary ending"

]





def crear_imagen(prompt, numero):


    url = (

        "https://api.stability.ai/"
        "v2beta/stable-image/"
        "generate/core"

    )



    headers = {

        "Authorization":
        f"Bearer {get_key()}",

        "Accept":
        "image/*"

    }



    files = {

        "prompt":
        (
            None,
            prompt
        ),

        "aspect_ratio":
        (
            None,
            "16:9"
        )

    }



    print()

    print(
        f"🎨 Creando escena {numero}"
    )



    r = requests.post(

        url,

        headers=headers,

        files=files

    )



    if r.status_code != 200:

        print(
            r.text
        )

        return None



    salida = os.path.join(

        OUTPUT_DIR,

        f"escena_{numero}.png"

    )


    with open(

        salida,

        "wb"

    ) as f:

        f.write(
            r.content
        )


    print(
        "✅",
        salida
    )


    return salida





def main():


    os.makedirs(

        OUTPUT_DIR,

        exist_ok=True

    )


    creadas = 0



    print()

    print(
        "="*50
    )

    print(
        "🎨 AUTOTUBE SAFE IMAGE PRODUCER"
    )

    print(
        "="*50
    )



    for i, escena in enumerate(

        ESCENAS,

        start=1

    ):


        imagen = crear_imagen(

            escena,

            i

        )


        if imagen:

            creadas += 1



    print()

    print(
        "🎉 IMÁGENES CREADAS:",
        creadas
    )




if __name__ == "__main__":

    main()