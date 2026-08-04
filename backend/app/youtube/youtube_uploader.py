import os
import pickle
import time

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload"
]

BASE_DIR = os.path.dirname(__file__)

CLIENT_SECRET = os.path.join(
    BASE_DIR,
    "client_secret.json"
)

TOKEN_FILE = os.path.join(
    BASE_DIR,
    "token.pickle"
)


def login():

    creds = None

    if os.path.exists(TOKEN_FILE):

        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if creds and creds.valid:

        print("✅ Token encontrado")

    else:

        if creds and creds.expired and creds.refresh_token:

            print("🔄 Renovando token...")
            creds.refresh(Request())

        else:

            print("🌐 Abriendo navegador...")

            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET,
                SCOPES
            )

            creds = flow.run_local_server(
                port=8080,
                open_browser=True
            )

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    youtube = build(
        "youtube",
        "v3",
        credentials=creds
    )

    print("✅ Login correcto")

    return youtube


def upload_video(

    video_path,
    title,
    description,
    tags,
    privacy="private",
    category="27"

):

    print("🚀 Preparando subida a YouTube...")

    youtube = login()

    title = str(title)
    description = str(description)

    title = title.replace("\x00", "").strip()
    description = description.replace("\x00", "").strip()

    title = title[:100]
    description = description[:5000]

    if not tags:

        tags = [
            "AI",
            "Documentary",
            "History",
            "AutoTube AI"
        ]

    body = {

        "snippet": {

            "title": title,

            "description": description,

            "tags": tags,

            "categoryId": category,

            "defaultLanguage": "es",

            "defaultAudioLanguage": "es"

        },

        "status": {

            "privacyStatus": privacy,

            "selfDeclaredMadeForKids": False

        }

    }

    media = MediaFileUpload(

        video_path,

        resumable=True,

        chunksize=1024 * 1024

    )

    request = youtube.videos().insert(

        part="snippet,status",

        body=body,

        media_body=media

    )

    response = None

    intentos = 0

    while response is None:

        try:

            status, response = request.next_chunk()

            if status:

                progreso = int(status.progress() * 100)

                print(f"📤 Subiendo... {progreso}%")

        except Exception as error:

            intentos += 1

            print()
            print("⚠️ Fallo de conexión:")
            print(error)

            if intentos >= 10:

                raise Exception(
                    "❌ Falló la subida después de 10 intentos"
                )

            print("🔄 Reintentando en 20 segundos...")

            time.sleep(20)

    print()

    print("🎉 Video subido correctamente")

    video_id = response["id"]

    url = "https://youtu.be/" + video_id

    print(url)

    return video_id


def upload_autotube_video(

    title,

    description,

    tags=None,

    privacy="private",

    category="27"

):

    video = "videos/autotube_video.mp4"

    if not os.path.exists(video):

        raise Exception(
            "No existe videos/autotube_video.mp4"
        )

    if tags is None:

        tags = [

            "AI",

            "Documentary",

            "History",

            "Technology",

            "AutoTube AI"

        ]

    return upload_video(

        video,

        title,

        description,

        tags,

        privacy,

        category

    )