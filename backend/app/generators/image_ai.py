import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("STABILITY_API_KEY")


def prepare_image_folder():
    os.makedirs("images", exist_ok=True)


def generate_ai_image(prompt, number):

    prepare_image_folder()

    filename = f"images/escena_{number}.png"

    print(f"\n🖼️ Generando imagen {number}...")
    print(prompt)

    url = "https://api.stability.ai/v2beta/stable-image/generate/core"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "image/*"
    }

    files = {
        "prompt": (None, prompt),
        "output_format": (None, "png")
    }

    response = requests.post(
        url,
        headers=headers,
        files=files
    )

    if response.status_code == 200:

        with open(filename, "wb") as f:
            f.write(response.content)

        print("✅ Imagen creada:", filename)

        return filename

    print(response.text)
    return None


def generate_ai_images(scenes):

    images = []

    for scene in scenes:

        prompt = f"""
        {scene['titulo']}.
        {scene['descripcion']}.

        Cinematic.
        Ultra realistic.
        4K.
        Professional lighting.
        Highly detailed.
        No text.
        No watermark.
        """

        image = generate_ai_image(
            prompt,
            scene["escena"]
        )

        images.append(image)

    return images