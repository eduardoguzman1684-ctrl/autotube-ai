import os
import logging
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# =====================================================
# CARGAR VARIABLES
# =====================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


ENV_PATH = os.path.join(
    BASE_DIR,
    ".env"
)


load_dotenv(ENV_PATH)


GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)



# =====================================================
# GENERADOR DE GUION
# =====================================================


def generar_guion(
    titulo,
    canal,
    categoria="historia"
):


    logging.info(
        "Generando guion documental..."
    )


    prompt = f"""
Eres un guionista profesional de documentales para YouTube.

Crea un documental original basado en el siguiente tema:

Título de referencia:
{titulo}

Canal fuente:
{canal}

Categoría:
{categoria}


REQUISITOS:

- Crear una narración de 10 minutos.
- No copiar el documental original.
- Crear contenido educativo original.
- Estilo National Geographic / BBC.
- Usar tono cinematográfico.
- Dividir en escenas.
- Cada escena debe incluir:
  - Narración
  - Descripción visual
  - Ambiente sonoro


Estructura:

INTRODUCCIÓN

ESCENA 1

ESCENA 2

ESCENA 3

ESCENA 4

ESCENA 5

CONCLUSIÓN


Genera únicamente el guion.
"""


    # Mientras conectamos Gemini dejamos plantilla
    # de prueba funcional


    guion = f"""

INTRODUCCIÓN

Durante siglos, la humanidad ha intentado comprender
los grandes acontecimientos que marcaron nuestra historia.

Hoy exploraremos:
{titulo}


ESCENA 1

Narración:
Los primeros registros muestran una civilización
llena de secretos y descubrimientos.


Visual:
Imágenes cinematográficas de ruinas antiguas,
mapas históricos y reconstrucciones digitales.


ESCENA 2

Narración:
Cada hallazgo revela nuevas preguntas sobre
el pasado de la humanidad.


Visual:
Arqueólogos investigando antiguos territorios.


ESCENA 3

Narración:
La tecnología moderna permite estudiar estos
acontecimientos con una precisión nunca antes vista.


Visual:
Animaciones 3D y modelos digitales.


ESCENA 4

Narración:
El legado de estas civilizaciones continúa
influyendo en nuestro mundo actual.


Visual:
Transición entre pasado y presente.


ESCENA 5

Narración:
Comprender la historia es comprender nuestro propio origen.


CONCLUSIÓN

La historia permanece viva a través de los descubrimientos
que seguimos realizando.


"""


    return guion



# =====================================================
# PRUEBA
# =====================================================

if __name__ == "__main__":


    resultado = generar_guion(

        titulo="The Entire History Of The Hittites",

        canal="History Time",

        categoria="historia"

    )


    print("\n==============================")
    print("📜 GUION GENERADO")
    print("==============================\n")


    print(resultado)