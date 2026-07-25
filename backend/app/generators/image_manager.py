import os
from PIL import Image, ImageDraw, ImageFont


def prepare_image_folder():

    folder = "images"

    if not os.path.exists(folder):
        os.makedirs(folder)

    print("📁 Carpeta de imágenes preparada")


def create_scene_images(scenes):

    prepare_image_folder()

    images = []

    for scene in scenes:

        filename = f"images/escena_{scene['escena']}.png"

        img = Image.new(
            "RGB",
            (1280, 720),
            color=(20, 20, 30)
        )

        draw = ImageDraw.Draw(img)

        texto = (
            scene["titulo"]
            + "\n\n"
            + scene["descripcion"]
        )

        draw.multiline_text(
            (80, 200),
            texto,
            fill=(255,255,255),
            spacing=10
        )

        img.save(filename)

        images.append(filename)

        print(f"🖼️ Imagen creada: {filename}")

    return images