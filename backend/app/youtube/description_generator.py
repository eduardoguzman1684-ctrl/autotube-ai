import os
from google import genai

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def generar_descripcion(topic, investigacion):

    prompt = f"""
Eres un experto en SEO para YouTube.

Tema:
{topic}

Información:
{investigacion[:4000]}

Escribe únicamente una descripción profesional para YouTube.

Reglas:

- Entre 400 y 800 caracteres.
- No uses Markdown.
- No uses títulos.
- No expliques lo que hiciste.
- Debe invitar a ver el video.
- Agrega una llamada a la acción.
- Termina con exactamente 5 hashtags relacionados.
"""

    respuesta = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    return respuesta.text.strip()