import os


def prepare_image_folder():

    folder = "images"

    if not os.path.exists(folder):
        os.makedirs(folder)

    print("📁 Carpeta de imágenes preparada")


def create_scene_images(scenes):

    prepare_image_folder()

    images = []

    for scene in scenes:

        filename = f"images/escena_{scene['escena']}.txt"

        with open(filename, "w", encoding="utf-8") as file:
            file.write(
                "Imagen preparada para:\n"
                + scene["titulo"]
                + "\n\n"
                + scene["descripcion"]
            )

        images.append(filename)

        print(f"🖼️ Imagen preparada: {filename}")

    return images


if __name__ == "__main__":

    prueba = [
        {
            "escena": 1,
            "titulo": "Introducción",
            "descripcion": "Tecnología e inteligencia artificial"
        }
    ]

    create_scene_images(prueba)