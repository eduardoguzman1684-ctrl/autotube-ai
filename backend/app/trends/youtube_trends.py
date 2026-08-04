import os
from dotenv import load_dotenv
from googleapiclient.discovery import build



# ========================================
# CARGAR VARIABLES .ENV
# ========================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


ENV_PATH = os.path.join(
    BASE_DIR,
    ".env"
)


load_dotenv(ENV_PATH)


API_KEY = os.getenv(
    "YOUTUBE_API_KEY"
)


if not API_KEY:

    raise Exception(
        "❌ No se encontró YOUTUBE_API_KEY en backend/app/.env"
    )



# ========================================
# YOUTUBE API
# ========================================

youtube = build(

    "youtube",

    "v3",

    developerKey=API_KEY

)



# ========================================
# TEMAS IMPORTANTES
# ========================================

PALABRAS_PRIORIDAD = {


    # Ciencia
    "NASA": 50,
    "space": 45,
    "universe": 45,
    "planet": 40,
    "science": 40,


    # Tecnología
    "AI": 45,
    "artificial intelligence": 50,
    "robot": 35,
    "technology": 35,
    "future": 30,


    # Historia real
    "ancient": 45,
    "archaeology": 50,
    "civilization": 45,
    "egypt": 40,
    "roman": 35,
    "history documentary": 50,


    # Documentales
    "documentary": 50,
    "explained": 35,
    "discovery": 35,
    "mystery": 30,
    "facts": 25

}



# ========================================
# PALABRAS BLOQUEADAS
# ========================================

PALABRAS_BLOQUEADAS = [

    # Películas
    "trailer",
    "official trailer",
    "movie",
    "film",
    "cinema",


    # Música
    "song",
    "music",
    "lyrics",
    "concert",


    # Juegos
    "roblox",
    "minecraft",
    "gaming",
    "gameplay",
    "fortnite",
    "streamer",
    "twitch",
    "playstation",
    "xbox",


    # Deportes
    "football",
    "soccer",
    "cricket",
    "nba",
    "match",


    # Farándula
    "celebrity",
    "gossip",
    "reality show",
    "award",
    "actor"


]



# ========================================
# OBTENER TENDENCIAS
# ========================================

def obtener_tendencias():


    regiones = [

        "US",
        "GB",
        "CA",
        "AU",
        "MX",
        "BR"

    ]


    tendencias = []



    for region in regiones:


        print(
            f"🌎 Buscando tendencias {region}"
        )


        try:


            respuesta = youtube.videos().list(

                part="snippet,statistics",

                chart="mostPopular",

                regionCode=region,

                maxResults=50

            ).execute()



            for video in respuesta.get(
                "items",
                []
            ):


                titulo = video["snippet"]["title"]


                vistas = int(

                    video["statistics"].get(

                        "viewCount",

                        0

                    )

                )


                tendencias.append({

                    "titulo": titulo,

                    "canal": video["snippet"]["channelTitle"],

                    "vistas": vistas,

                    "region": region

                })



        except Exception as error:


            print(
                "⚠️ Error:",
                error
            )



    return tendencias




# ========================================
# ELEGIR MEJOR TEMA
# ========================================

def mejor_tema():


    tendencias = obtener_tendencias()


    candidatos = []



    for video in tendencias:


        titulo = video["titulo"].lower()



        # Bloquear contenido basura

        bloqueado = False


        for palabra in PALABRAS_BLOQUEADAS:


            if palabra.lower() in titulo:


                bloqueado = True

                break



        if bloqueado:

            continue




        puntuacion = 0



        # Premiar temas buenos

        for palabra, puntos in PALABRAS_PRIORIDAD.items():


            if palabra.lower() in titulo:


                puntuacion += puntos



        # Añadir valor por vistas

        puntuacion += int(
            video["vistas"] / 1000000
        )



        video["puntuacion"] = puntuacion



        # Solo aceptar temas documentales

        if puntuacion >= 20:

            candidatos.append(video)




    if not candidatos:


        raise Exception(
            "❌ No se encontraron temas documentales"
        )



    candidatos.sort(

        key=lambda x:x["puntuacion"],

        reverse=True

    )



    return candidatos[0]





# ========================================
# PRUEBA
# ========================================

if __name__ == "__main__":


    print()

    print(
        "🔥 BUSCANDO TEMA PARA AUTOTUBE AI"
    )

    print()



    tema = mejor_tema()



    print(
        "=============================="
    )

    print(
        "🎬 TEMA SELECCIONADO"
    )

    print(
        "=============================="
    )

    print()


    print(
        "Título:"
    )

    print(
        tema["titulo"]
    )


    print()


    print(
        "Canal:"
    )

    print(
        tema["canal"]
    )


    print()


    print(
        "Vistas:"
    )

    print(
        tema["vistas"]
    )


    print()


    print(
        "Región:"
    )

    print(
        tema["region"]
    )


    print()


    print(
        "Puntuación:"
    )

    print(
        tema["puntuacion"]
    )