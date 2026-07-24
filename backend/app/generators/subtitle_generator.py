import os


def generate_subtitles(script):

    folder = "storage/subtitles"

    if not os.path.exists(folder):
        os.makedirs(folder)


    lines = script.split(".")

    subtitles = []

    contador = 1

    for line in lines:

        texto = line.strip()

        if texto:

            subtitle = {
                "id": contador,
                "texto": texto
            }

            subtitles.append(subtitle)

            contador += 1


    with open(
        "storage/subtitles/subtitles.txt",
        "w",
        encoding="utf-8"
    ) as file:

        for subtitle in subtitles:
            file.write(str(subtitle))
            file.write("\n")


    print("✅ Subtítulos creados correctamente")

    return subtitles



if __name__ == "__main__":

    prueba = """
    La inteligencia artificial está transformando los negocios.
    Las empresas utilizan tecnología para mejorar sus procesos.
    """

    generate_subtitles(prueba)