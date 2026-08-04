import re


DURACION_MINIMA = 600


CANALES_PRIORIDAD = [
    "BBC",
    "National Geographic",
    "DW",
    "History",
    "Smithsonian",
    "Discovery",
    "Arte"
]


PALABRAS_BUENAS = {

    "documentary": 40,
    "history": 35,
    "ancient": 30,
    "civilization": 30,
    "science": 30,
    "space": 30,
    "universe": 25,
    "technology": 25,
    "artificial intelligence": 40,
    "ai": 25,
    "nasa": 35,
    "empire": 25,
    "war": 20

}


PALABRAS_BLOQUEADAS = [

    "music",
    "song",
    "lyrics",
    "official video",
    "remix",
    "concert",
    "trailer",
    "movie",
    "film",
    "minecraft",
    "gaming",
    "gameplay",
    "shorts",
    "tiktok",
    "live performance"

]


def parse_duration(duration):

    resultado = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        duration
    )

    if not resultado:
        return 0


    horas = int(resultado.group(1) or 0)
    minutos = int(resultado.group(2) or 0)
    segundos = int(resultado.group(3) or 0)


    return (
        horas * 3600 +
        minutos * 60 +
        segundos
    )



def calcular_score(video):

    titulo = video["snippet"]["title"].lower()

    canal = video["snippet"]["channelTitle"]

    vistas = int(
        video["statistics"].get(
            "viewCount",
            0
        )
    )


    duracion = parse_duration(
        video["contentDetails"]["duration"]
    )


    score = 0


    # Duración

    if duracion >= DURACION_MINIMA:

        score += 50

    else:

        score -= 100



    # Palabras positivas

    for palabra, puntos in PALABRAS_BUENAS.items():

        if palabra in titulo:

            score += puntos



    # Bloqueos

    for palabra in PALABRAS_BLOQUEADAS:

        if palabra in titulo:

            score -= 200



    # Canal importante

    for canal_ok in CANALES_PRIORIDAD:

        if canal_ok.lower() in canal.lower():

            score += 60



    # Popularidad

    if vistas > 100000:

        score += 20


    if vistas > 1000000:

        score += 40



    return score