import os
from dotenv import load_dotenv
from google import genai

load_dotenv("backend/app/.env")

API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)


def investigar_tema(topic):

    print("🔍 Investigando con Gemini Flash Latest...")

    prompt = f"""
Eres un investigador profesional experto en documentales para YouTube.

Investiga profundamente este tema:

{topic}

Responde en español.

Incluye:

1. Qué es.
2. Historia.
3. Datos importantes.
4. Curiosidades.
5. Personajes importantes.
6. Lugares importantes.
7. Palabras clave.
8. Un resumen de aproximadamente 500 palabras.

No inventes información.
"""

    respuesta = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt
    )

    return respuesta.text