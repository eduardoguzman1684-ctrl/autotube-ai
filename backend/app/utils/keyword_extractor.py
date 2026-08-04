import re


def extraer_keywords(texto, limite=8):

    palabras = re.findall(r"[A-Za-zÀ-ÿ0-9]+", texto.lower())

    ignorar = {
        "de","la","el","los","las","un","una","unos","unas",
        "para","por","con","sobre","del","que","como",
        "es","son","en","y","o","a"
    }

    keywords = []

    for palabra in palabras:

        if len(palabra) < 4:
            continue

        if palabra in ignorar:
            continue

        if palabra not in keywords:
            keywords.append(palabra)

    return keywords[:limite]