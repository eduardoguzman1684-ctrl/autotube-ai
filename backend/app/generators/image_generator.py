from dotenv import load_dotenv
from openai import OpenAI
import os


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def generate_image(prompt, filename):

    print("🖼️ Generando imagen...")

    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024"
    )

    image_url = result.data[0].url

    print("✅ Imagen generada:")
    print(image_url)

    return image_url


if __name__ == "__main__":

    generate_image(
        "Una oficina moderna usando inteligencia artificial en los negocios, estilo cinematográfico, personas trabajando con tecnología avanzada",
        "imagen1.png"
    )