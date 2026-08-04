import logging


# =====================================
# AUTOTUBE AI v2.0
# GENERADOR DE ESCENAS
# =====================================


logger = logging.getLogger(
    "AutoTubeAI"
)



def generar_escenas(
    guion
):

    logger.info(
        "🎬 Generando escenas documentales"
    )


    escenas = []


    # ESCENA 1 - INTRODUCCIÓN

    escenas.append({

        "numero": 1,

        "titulo":
        "Introducción",

        "imagen_prompt":
        (
            f"Escena cinematográfica histórica "
            f"sobre {guion['titulo']}, "
            "paisaje antiguo, iluminación "
            "dramática, estilo documental."
        ),

        "narracion":
        guion["introduccion"]

    })


    # ESCENA 2 - DESARROLLO

    escenas.append({

        "numero": 2,

        "titulo":
        "Desarrollo histórico",

        "imagen_prompt":
        (
            "Civilización antigua, "
            "personajes históricos, "
            "arquitectura antigua, "
            "estilo documental cinematográfico."
        ),

        "narracion":
        guion["desarrollo"][0]

    })


    # ESCENA 3 - CONCLUSIÓN

    escenas.append({

        "numero": 3,

        "titulo":
        "Conclusión",

        "imagen_prompt":
        (
            "Ruinas arqueológicas antiguas "
            "al atardecer, misterio histórico, "
            "estilo película documental."
        ),

        "narracion":
        guion["conclusion"]

    })


    return escenas



def mostrar_escenas(
    escenas
):

    print()

    print("=" * 50)
    print("🎬 ESCENAS GENERADAS")
    print("=" * 50)


    for escena in escenas:

        print()

        print(
            f"🎞️ ESCENA {escena['numero']}"
        )

        print(
            "Título:",
            escena["titulo"]
        )

        print(
            "Imagen:",
            escena["imagen_prompt"]
        )

        print(
            "Narración:",
            escena["narracion"]
        )



if __name__ == "__main__":


    guion_prueba = {

        "titulo":
        "El Imperio Hitita",


        "introduccion":
        "Una antigua civilización llena de misterios.",


        "desarrollo":
        [
            "Origen y expansión del imperio."
        ],


        "conclusion":
        "Su legado continúa hasta nuestros días."

    }


    resultado = generar_escenas(
        guion_prueba
    )


    mostrar_escenas(
        resultado
    )