import json
from pathlib import Path
from datetime import datetime

# Carpeta donde se guardará el historial
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

HISTORY_FILE = CACHE_DIR / "used_videos.json"


def cargar_historial():
    """
    Devuelve todo el historial.
    """

    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def obtener_ids():
    """
    Devuelve solamente los IDs.
    """

    historial = cargar_historial()

    return {
        item["id"]
        for item in historial
        if isinstance(item, dict) and "id" in item
    }


def guardar_video(video):

    historial = cargar_historial()

    video_id = video.get("id")

    if not video_id:
        return

    for item in historial:
        if item.get("id") == video_id:
            return

    historial.append({

        "id": video_id,

        "titulo": video.get("titulo"),

        "canal": video.get("canal"),

        "categoria": video.get("categoria"),

        "idioma": video.get("idioma"),

        "score": video.get("score"),

        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    })

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(
            historial,
            f,
            indent=4,
            ensure_ascii=False
        )


if __name__ == "__main__":

    print("Historial actual:")

    print(cargar_historial())