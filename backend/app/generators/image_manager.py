import os
import requests
from urllib.parse import quote
from PIL import Image
from io import BytesIO

print("######## IMAGE_MANAGER CARGADO ########")


def prepare_image_folder():
    os.makedirs("images", exist_ok=True)


def generar_imagen_pollinations(prompt, filename):

    print("\n🎨 Generando imagen con Pollinations AI...")
    print(prompt)

    url = (
        "https://image.pollinations.ai/prompt/"
        + quote(prompt)
        + "?width=1280&height=720&model=flux&enhance=true&nologo=true"
    )

    response = requests.get(url, timeout=180)

    if response.status_code != 200:
        raise Exception(f"Pollinations respondió {response.status_code}")

    img = Image.open(BytesIO(response.content))
    img.convert("RGB").save(filename, "JPEG", quality=95)

    print("✅ Imagen creada:", filename)


def create_scene_images(scenes):

    prepare_image_folder()

    images = []

    for scene in scenes:

        filename = f"images/escena_{scene['escena']}.jpg"

        prompt = scene.get("image_prompt")

        if not prompt:
            prompt = scene["descripcion"]

        generar_imagen_pollinations(
            prompt,
            filename
        )

        images.append(filename)

    return images