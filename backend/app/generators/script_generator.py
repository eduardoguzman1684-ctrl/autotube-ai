from ai.ollama_client import OllamaClient


def generate_script(topic):

    ai = OllamaClient()

    prompt = f"""
Eres un guionista profesional de YouTube.

Escribe un guion sobre:

{topic}

Debe incluir:

1. Título atractivo.
2. Introducción.
3. Tres secciones de desarrollo.
4. Una conclusión.
5. Una llamada a la acción.

Escribe todo en español.

Máximo 300 palabras.
"""

    return ai.generate(prompt)