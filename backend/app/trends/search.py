from backend.app.trends.scorer import calcular_score

BUSQUEDAS = [
    "history documentary",
    "science documentary",
    "space documentary",
    "technology documentary",
    "artificial intelligence documentary",
    "ancient civilization documentary",
    "Roman Empire documentary",
    "World War documentary",
    "NASA documentary",
    "BBC documentary",
    "DW documentary"
]


def buscar_documentales(youtube):

    candidatos = []

    for termino in BUSQUEDAS:

        print(f"🔎 Buscando: {termino}")

        try:

            respuesta = youtube.search().list(
                part="id",
                q=termino,
                type="video",
                maxResults=5,
                relevanceLanguage="en"
            ).execute()

        except Exception as e:

            print("Error:", e)
            continue

        ids = [
            item["id"]["videoId"]
            for item in respuesta.get("items", [])
        ]

        if not ids:
            continue

        try:

            detalles = youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(ids)
            ).execute()

        except Exception as e:

            print("Error:", e)
            continue

        for video in detalles.get("items", []):

            score = calcular_score(video)

            candidatos.append({

                "video": video,

                "score": score

            })

    candidatos.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return candidatos