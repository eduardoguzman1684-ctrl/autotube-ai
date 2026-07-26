from ai.ollama_client import OllamaClient
import json


def generate_scenes(topic):

    print("🧠 Generando escenas inteligentes...")


    prompt = f"""
Eres un director cinematográfico profesional de YouTube.

Crea 4 escenas visuales para un video sobre:

{topic}


Reglas importantes:

- La descripción debe ser TEXTO PLANO.
- NO uses JSON dentro de descripcion.
- NO uses campos como video, imagen o textura.
- NO menciones inteligencia artificial, oficinas o tecnología si el tema no trata de eso.
- Las escenas deben estar relacionadas directamente con el tema.


Cada escena debe tener:

- escena
- titulo
- descripcion


Ejemplos:

Historia:
Lugares antiguos, personajes históricos, ciudades antiguas, vestimenta de época.

Religión:
Templos, lugares históricos, personajes relacionados, ambientes de la época.

Ciencia:
Laboratorios, naturaleza, experimentos, descubrimientos.

Biografía:
Persona, momentos importantes de su vida, lugares relacionados.


Devuelve solamente JSON.


Formato obligatorio:

[
 {{
 "escena":1,
 "titulo":"Introducción",
 "descripcion":"Descripción cinematográfica detallada relacionada con el tema."
 }},
 {{
 "escena":2,
 "titulo":"Desarrollo",
 "descripcion":"Descripción cinematográfica detallada relacionada con el tema."
 }},
 {{
 "escena":3,
 "titulo":"Momentos importantes",
 "descripcion":"Descripción cinematográfica detallada relacionada con el tema."
 }},
 {{
 "escena":4,
 "titulo":"Conclusión",
 "descripcion":"Descripción cinematográfica detallada relacionada con el tema."
 }}
]


No agregues explicaciones fuera del JSON.
"""


    ai = OllamaClient()

    respuesta = ai.generate(prompt)


    try:

        respuesta = respuesta.replace("```json", "")
        respuesta = respuesta.replace("```", "")

        scenes = json.loads(respuesta)


    except Exception:

        print("⚠️ Error leyendo escenas IA, usando modo seguro")


        scenes = [

            {
                "escena":1,
                "titulo":"Introducción",
                "descripcion":f"""
                Escena cinematográfica sobre {topic}.
                Ambiente relacionado con la época y cultura del tema.
                Fotografía profesional estilo documental 4K.
                """
            },


            {
                "escena":2,
                "titulo":"Desarrollo",
                "descripcion":f"""
                Representación visual de los acontecimientos principales de {topic}.
                Escenario realista con detalles históricos y cinematográficos.
                """
            },


            {
                "escena":3,
                "titulo":"Momentos importantes",
                "descripcion":f"""
                Escena mostrando los momentos más relevantes relacionados con {topic}.
                Imagen realista con iluminación de película.
                """
            },


            {
                "escena":4,
                "titulo":"Conclusión",
                "descripcion":f"""
                Imagen final inspiradora relacionada con {topic}.
                Estilo documental cinematográfico profesional.
                """
            }

        ]


    # Protección contra respuestas incorrectas de la IA
    for scene in scenes:

        descripcion = scene.get("descripcion")


        # Si Ollama devuelve un objeto en vez de texto
        if isinstance(descripcion, dict):

            texto = ""

            for valor in descripcion.values():
                texto += str(valor) + ". "

            scene["descripcion"] = texto.strip()



        # Si viene vacío
        if not scene.get("descripcion"):

            scene["descripcion"] = (
                f"Escena cinematográfica relacionada con {topic}"
            )


    return scenes