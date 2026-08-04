import logging
from datetime import datetime


# =====================================
# AUTOTUBE AI v2.0
# GENERADOR DE TEMAS
# =====================================


logger = logging.getLogger(
    "AutoTubeAI"
)



def generar_tema(
    tema=None
):

    """
    Genera la información base
    para iniciar un documental.
    """


    if not tema:

        tema = (
            "Ancient civilizations "
            "and forgotten history"
        )


    documental = {

        "titulo": tema,

        "categoria": "documental",

        "idioma": "es",

        "fecha": datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "descripcion": (
            f"Documental cinematográfico "
            f"sobre {tema}. "
            "Historia, descubrimientos "
            "y misterios revelados."
        )

    }


    logger.info(
        f"🎬 Tema creado: {tema}"
    )


    return documental



if __name__ == "__main__":


    resultado = generar_tema(
        "El Imperio Hitita"
    )


    print(
        "=============================="
    )

    print(
        "🎬 TEMA GENERADO"
    )

    print(
        "=============================="
    )


    for clave, valor in resultado.items():

        print(
            f"{clave}: {valor}"
        )