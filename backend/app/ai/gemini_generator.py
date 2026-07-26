def generar_con_gemini(tema):

    print("\n🧠 Gemini creando contenido...")

    contenido = f"""
Eres un experto creador de contenido para YouTube.

Crea un guion profesional sobre:

TEMA: {tema}

Debe tener:

Título:
Un título llamativo para YouTube.

Introducción:
Presenta el tema de forma interesante para captar la atención.

Desarrollo:
Explica tres puntos importantes relacionados con el tema.

Aplicaciones o ejemplos:
Incluye ejemplos reales.

Conclusión:
Resume las ideas principales.

Llamada a la acción:
Invita al espectador a suscribirse y comentar.

Escribe en español.
Máximo 500 palabras.
"""

    from ai.ollama_client import OllamaClient

    ai = OllamaClient()

    return ai.generate(contenido)