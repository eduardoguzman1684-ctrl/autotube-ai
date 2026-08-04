import sys
from pathlib import Path

# Agregar raíz del proyecto al PATH
BASE_DIR = Path(__file__).resolve().parents[3]
sys.path.append(str(BASE_DIR))


from backend.app.trends.youtube_client import youtube
from backend.app.trends.search import buscar_documentales
from backend.app.trends.history import obtener_ids, guardar_video



def seleccionar_documental():

    historial = obtener_ids()

    candidatos = buscar_documentales(youtube)


    for candidato in candidatos:

        video = candidato["video"]

        if video["id"] in historial:
            continue


        guardar_video({

            "id": video["id"],

            "titulo": video["snippet"]["title"],

            "canal": video["snippet"]["channelTitle"],

            "categoria": "documental",

            "idioma": "en",

            "score": candidato["score"]

        })


        return video


    raise Exception(
        "No se encontró documental nuevo"
    )



if __name__ == "__main__":

    print()
    print("=" * 60)
    print("🎬 AUTOTUBE AI - SELECTOR DOCUMENTAL")
    print("=" * 60)
    print()


    documental = seleccionar_documental()


    print("Título:")
    print(documental["snippet"]["title"])

    print()

    print("Canal:")
    print(documental["snippet"]["channelTitle"])

    print()

    print("ID:")
    print(documental["id"])

    print()

    print("Vistas:")
    print(
        documental["statistics"].get("viewCount")
    )