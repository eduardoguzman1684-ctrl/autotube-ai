import os
from dotenv import load_dotenv
from googleapiclient.discovery import build


# ========================================
# CONFIGURACIÓN
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

API_KEY = os.getenv("YOUTUBE_API_KEY")

if not API_KEY:
    raise Exception(
        "❌ No se encontró YOUTUBE_API_KEY en backend/app/.env"
    )


youtube = build(
    "youtube",
    "v3",
    developerKey=API_KEY
)


# ========================================
# REGIONES A CONSULTAR
# ========================================

REGIONES = [
    "US",
    "CA",
    "GB",
    "AU",
    "MX",
    "BR"
]


# ========================================
# TEMAS DOCUMENTALES
# ========================================

BUSQUEDAS = [
    "science",
    "technology",
    "artificial intelligence",
    "space",
    "NASA",
    "universe",
    "history",
    "ancient civilizations",
    "archaeology",
    "ancient Egypt",
    "Roman Empire",
    "dinosaurs",
    "black holes",
    "future technology",
    "documentary"
]

# ========================================
# BUSCAR VIDEOS POR TEMA
# ========================================

def buscar_videos():

    videos = []

    for region in REGIONES:

        print(f"🌎 Región: {region}")

        for tema in BUSQUEDAS:

            print(f"   🔍 {tema}")

            try:

                respuesta = youtube.search().list(

                    part="snippet",

                    q=tema,

                    type="video",

                    maxResults=10,

                    regionCode=region,

                    relevanceLanguage="en",

                    order="viewCount"

                ).execute()


                for item in respuesta.get("items", []):

                    video_id = item["id"]["videoId"]

                    detalle = youtube.videos().list(

                        part="snippet,statistics",

                        id=video_id

                    ).execute()

                    if not detalle.get("items"):
                        continue

                    data = detalle["items"][0]

                    videos.append({

                        "titulo": data["snippet"]["title"],

                        "canal": data["snippet"]["channelTitle"],

                        "vistas": int(
                            data["statistics"].get(
                                "viewCount",
                                0
                            )
                        ),

                        "region": region

                    })

            except Exception as e:

                print("⚠️", e)

    return videos