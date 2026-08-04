import os
import re
import json
import time

from dotenv import load_dotenv
from googleapiclient.discovery import build


# ========================================
# AUTOTUBE AI V12.8 PRO
# DOCUMENTARY INTELLIGENCE ENGINE
# ========================================


# ========================================
# CARGAR .ENV
# ========================================


BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)


ENV_PATH = os.path.join(
    BASE_DIR,
    ".env"
)


load_dotenv(
    ENV_PATH
)



API_KEY = os.getenv(
    "YOUTUBE_API_KEY"
)



if not API_KEY:

    raise Exception(
        "❌ Falta YOUTUBE_API_KEY en backend/app/.env"
    )





# ========================================
# YOUTUBE API
# ========================================


youtube = build(

    "youtube",

    "v3",

    developerKey=API_KEY,

    cache_discovery=False

)





# ========================================
# CACHE V12.8
# ========================================


CACHE_DIR = os.path.join(

    os.path.dirname(__file__),

    "cache"

)


CACHE_FILE = os.path.join(

    CACHE_DIR,

    "youtube_cache_v12_8.json"

)



os.makedirs(

    CACHE_DIR,

    exist_ok=True

)







# ========================================
# REGIONES GLOBALES
# ========================================


REGIONES = [

    "US",
    "GB",
    "CA",
    "AU",
    "DE",
    "FR"

]








# ========================================
# CATEGORÍAS ACEPTADAS
# ========================================


CATEGORIAS_DOCUMENTAL = [

    "27",   # Education

    "28",   # Science Technology

    "15"    # Animals

]





# ========================================
# CATEGORÍAS BLOQUEADAS
# ========================================


CATEGORIAS_BLOQUEADAS = [

    "10",   # Music

    "20",   # Gaming

    "17",   # Sports

    "24"    # Entertainment

]







# ========================================
# PALABRAS DOCUMENTALES
# ========================================


PALABRAS_DOCUMENTAL = {


    "documentary":300,

    "documental":300,


    "history":250,

    "ancient":220,

    "civilization":280,

    "archaeology":260,


    "empire":150,

    "kingdom":120,


    "science":260,

    "technology":230,

    "innovation":200,


    "artificial intelligence":350,

    "ai technology":250,


    "nasa":450,

    "space":320,

    "universe":320,

    "galaxy":260,

    "black hole":350,


    "robotics":250,

    "robot":180,


    "nature":220,

    "wildlife":300,

    "ocean":220,


    "biology":220,

    "physics":220,


    "experiment":220,

    "research":220,


    "discovery":220,

    "explained":180,


    "earth":150

}








# ========================================
# ARTISTAS BLOQUEADOS
# ========================================


ARTISTAS_MUSICALES = [

    "fred again",

    "ariana grande",

    "selena gomez",

    "benny blanco",

    "shakira",

    "morgan wallen",

    "bad bunny",

    "drake",

    "rihanna",

    "katseye",

    "taylor swift",

    "justin bieber",

    "billie eilish",

    "the weeknd",

    "dua lipa",

    "ed sheeran",

    "bruno mars",

    "lady gaga",

]








# ========================================
# PALABRAS BLOQUEADAS
# ========================================


BLOQUEADOS = [

    "song",

    "music",

    "lyrics",

    "concert",

    "tour",

    "remix",

    "feat",

    "ft",

    "album",

    "playlist",

    "dj",

    "official audio",

    "official music",

    "live performance",


    "gaming",

    "gameplay",

    "minecraft",

    "roblox",

    "fortnite",

    "valorant",

    "twitch",

    "esports",


    "trailer",

    "teaser",

    "movie",

    "film",

    "cinema",

    "episode",

    "season",


    "reaction",

    "challenge",

    "prank",

    "vlog",

    "shorts"

]

# ========================================
# CANALES EDUCATIVOS PREMIUM
# ========================================


CANALES_PREMIADOS = [

    "nasa",

    "nasaspace",

    "national geographic",

    "nat geo",

    "bbc earth",

    "bbc",

    "discovery",

    "smithsonian",

    "science channel",

    "history channel",

    "dw documentary",

    "documentary"

]






# ========================================
# CANALES BLOQUEADOS
# ========================================


CANALES_BLOQUEADOS = [

    "vevo",

    "records",

    "music",

    "gaming",

    "sports",

    "radio",

    "official"

]







# ========================================
# LIMPIAR TEXTO
# ========================================


def limpiar_texto(texto):

    return texto.lower().strip()







# ========================================
# DETECTOR DE MÚSICA
# ========================================


def es_musica(texto):


    patrones = [

        r"\blive\b",

        r"\bofficial\b",

        r"\blyrics\b",

        r"\bremix\b",

        r"\bfeat\b",

        r"\bft\b",

        r"\bconcert\b",

        r"\btour\b",

        r"\bplaylist\b",

        r"\bdj\b",

        r"\bmix\b",

        r"\bsoundtrack\b",

        r"\bmv\b",

        r"\baudio\b"

    ]



    for patron in patrones:


        if re.search(

            patron,

            texto

        ):

            return True



    return False








# ========================================
# DETECTOR GAMING
# ========================================


def es_gaming(texto):


    patrones = [

        r"\bgaming\b",

        r"\bgameplay\b",

        r"\bminecraft\b",

        r"\broblox\b",

        r"\bfortnite\b",

        r"\bvalorant\b",

        r"\btwitch\b",

        r"\besports\b",

        r"\bfps\b",

        r"\bgta\b",

        r"\bcall of duty\b"

    ]



    for patron in patrones:


        if re.search(

            patron,

            texto

        ):

            return True



    return False








# ========================================
# DETECTOR CINE
# ========================================


def es_cine(texto):


    patrones = [

        r"\btrailer\b",

        r"\bteaser\b",

        r"\bmovie\b",

        r"\bfilm\b",

        r"\bcinema\b",

        r"\bepisode\b",

        r"\bseason\b",

        r"\bcast\b",

        r"\bactor\b",

        r"\bactress\b"

    ]



    for patron in patrones:


        if re.search(

            patron,

            texto

        ):

            return True



    return False








# ========================================
# DETECTOR ARTISTAS
# ========================================


def es_artista(texto):


    for artista in ARTISTAS_MUSICALES:


        if artista in texto:


            return True



    return False







# ========================================
# GUARDAR CACHE
# ========================================


def guardar_cache(videos):


    try:


        with open(

            CACHE_FILE,

            "w",

            encoding="utf-8"

        ) as archivo:


            json.dump(

                videos,

                archivo,

                indent=4,

                ensure_ascii=False

            )


    except Exception as error:


        print(

            "⚠️ Error guardando cache:",

            error

        )








# ========================================
# CARGAR CACHE
# ========================================


def cargar_cache():


    if not os.path.exists(

        CACHE_FILE

    ):


        return []




    try:


        fecha = os.path.getmtime(

            CACHE_FILE

        )


        antiguedad = time.time() - fecha



        # 6 horas

        if antiguedad < 21600:


            with open(

                CACHE_FILE,

                "r",

                encoding="utf-8"

            ) as archivo:


                datos = json.load(

                    archivo

                )


            print()

            print(

                "📦 Cache V12.8 cargada"

            )

            print()


            return datos




    except Exception as error:


        print(

            "⚠️ Error leyendo cache:",

            error

        )




    return []









# ========================================
# BUSCAR TENDENCIAS YOUTUBE
# ========================================


def buscar_documentales():


    cache = cargar_cache()



    if cache:


        return cache




    videos = []



    print()

    print(

        "🌎 Analizando tendencias globales V12.8..."

    )

    print()



    for region in REGIONES:


        print(

            f"🌎 Región: {region}"

        )



        try:


            respuesta = youtube.videos().list(


                part="snippet,statistics",


                chart="mostPopular",


                regionCode=region,


                maxResults=50


            ).execute()





            for item in respuesta.get(

                "items",

                []

            ):


                snippet = item.get(

                    "snippet",

                    {}

                )



                stats = item.get(

                    "statistics",

                    {}

                )



                videos.append({

                    "titulo":
                        snippet.get(
                            "title",
                            ""
                        ),


                    "canal":
                        snippet.get(
                            "channelTitle",
                            ""
                        ),


                    "categoria":
                        snippet.get(
                            "categoryId",
                            ""
                        ),


                    "vistas":
                        int(
                            stats.get(
                                "viewCount",
                                0
                            )
                        ),


                    "region":

                        region

                })



        except Exception as error:


            print(

                "⚠️ Error región:",

                error

            )



    if videos:


        guardar_cache(

            videos

        )



    return videos

# ========================================
# ANALIZADOR DOCUMENTAL V12.8 PRO
# ========================================


def puntuar_video(video):


    titulo = limpiar_texto(
        video["titulo"]
    )


    canal = limpiar_texto(
        video["canal"]
    )


    texto = titulo + " " + canal



    puntos = 0

    señales = 0






    # =====================================
    # FILTROS PRINCIPALES
    # =====================================


    if es_artista(texto):


        print(
            "❌ Artista musical:",
            video["titulo"]
        )

        return 0





    if es_musica(texto):


        print(
            "❌ Música:",
            video["titulo"]
        )

        return 0





    if es_gaming(texto):


        print(
            "❌ Gaming:",
            video["titulo"]
        )

        return 0





    if es_cine(texto):


        print(
            "❌ Cine:",
            video["titulo"]
        )

        return 0






    for palabra in BLOQUEADOS:


        if palabra in texto:


            print(

                "❌ Bloqueado:",
                palabra,
                "|",
                video["titulo"]

            )

            return 0






    for canal_malo in CANALES_BLOQUEADOS:


        if canal_malo in canal:


            print(

                "❌ Canal bloqueado:",
                canal

            )

            return 0







    # =====================================
    # CATEGORÍA YOUTUBE
    # =====================================


    categoria = video.get(

        "categoria",

        ""

    )



    if categoria in CATEGORIAS_BLOQUEADAS:


        print(

            "❌ Categoría bloqueada:",
            video["titulo"]

        )

        return 0







    # =====================================
    # BUSCAR SEÑALES DOCUMENTALES
    # =====================================


    for palabra, valor in PALABRAS_DOCUMENTAL.items():


        if palabra in texto:


            puntos += valor

            señales += 1







    # Mínimo dos señales

    if señales < 2:


        print(

            "❌ Sin tema documental:",
            video["titulo"]

        )

        return 0







    # =====================================
    # PREMIAR CANALES SERIOS
    # =====================================


    for canal_ok in CANALES_PREMIADOS:


        if canal_ok in canal:


            puntos += 400

            señales += 1








    # =====================================
    # BONUS VISTAS
    # =====================================


    vistas = video["vistas"]



    if vistas >= 10000000:


        puntos += 200



    elif vistas >= 1000000:


        puntos += 120



    elif vistas >= 500000:


        puntos += 70



    elif vistas >= 100000:


        puntos += 30








    # =====================================
    # BONUS TEMAS PREMIUM
    # =====================================


    premium = [


        "nasa",

        "space",

        "universe",

        "black hole",

        "history",

        "science",

        "technology",

        "wildlife",

        "nature",

        "documentary"

    ]




    for palabra in premium:


        if palabra in texto:


            puntos += 60






    return puntos







# ========================================
# SELECCIÓN DEL MEJOR DOCUMENTAL
# ========================================


def seleccionar_tema():


    videos = buscar_documentales()



    candidatos = []



    print()

    print(

        "🧠 Analizando candidatos V12.8..."

    )

    print()



    vistos = set()



    for video in videos:



        clave = (

            video["titulo"]

            +

            video["canal"]

        )



        if clave in vistos:


            continue



        vistos.add(

            clave

        )



        puntuacion = puntuar_video(

            video

        )



        if puntuacion > 0:


            video["puntuacion"] = puntuacion


            candidatos.append(

                video

            )








    if not candidatos:


        raise Exception(

            "❌ No se encontró documental válido"

        )







    candidatos.sort(

        key=lambda x:x["puntuacion"],

        reverse=True

    )



    return candidatos[0]








# ========================================
# MOSTRAR RESULTADO
# ========================================


def mostrar_resultado(tema):


    print()

    print(

        "=============================="

    )

    print(

        "🎬 DOCUMENTAL SELECCIONADO"

    )

    print(

        "=============================="

    )

    print()



    print(

        "Título:",

        tema["titulo"]

    )



    print(

        "Canal:",

        tema["canal"]

    )



    print(

        "Vistas:",

        tema["vistas"]

    )



    print(

        "Región:",

        tema["region"]

    )



    print(

        "Puntuación:",

        tema["puntuacion"]

    )



    print()

    print(

        "✅ Tema listo para generar documental IA"

    )








# ========================================
# EJECUCIÓN PRINCIPAL
# ========================================


if __name__ == "__main__":


    print()



    print(

        "🔥 AUTOTUBE AI V12.8 PRO - DOCUMENTARY INTELLIGENCE ENGINE"

    )


    print()



    tema = seleccionar_tema()



    mostrar_resultado(

        tema

    )