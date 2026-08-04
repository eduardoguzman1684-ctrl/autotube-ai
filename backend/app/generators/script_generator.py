import logging


# =====================================
# AUTOTUBE AI v2.0
# GENERADOR DE GUION DOCUMENTAL
# =====================================


logger = logging.getLogger(
    "AutoTubeAI"
)



def generar_guion(
    documental
):

    titulo = documental["titulo"]


    logger.info(
        f"📝 Generando guion: {titulo}"
    )


    guion = {

        "titulo": titulo,


        "introduccion": (
            f"Durante siglos, {titulo} "
            "ha despertado curiosidad "
            "por sus secretos, historia "
            "y acontecimientos."
        ),


        "desarrollo": [

            (
                "Origen y contexto histórico "
                "del tema."
            ),

            (
                "Personajes importantes "
                "y acontecimientos principales."
            ),

            (
                "Misterios, descubrimientos "
                "y datos sorprendentes."
            )

        ],


        "conclusion": (
            f"La historia de {titulo} "
            "nos demuestra que el pasado "
            "todavía tiene muchos secretos "
            "por descubrir."
        )

    }


    return guion



def imprimir_guion(
    guion
):

    print()
    print("=" * 50)
    print("📝 GUION DOCUMENTAL")
    print("=" * 50)


    print()
    print("🎬 TÍTULO:")
    print(
        guion["titulo"]
    )


    print()
    print("🎙️ INTRODUCCIÓN:")
    print(
        guion["introduccion"]
    )


    print()
    print("📚 DESARROLLO:")

    for punto in guion["desarrollo"]:

        print(
            "•",
            punto
        )


    print()
    print("🏁 CONCLUSIÓN:")
    print(
        guion["conclusion"]
    )



if __name__ == "__main__":


    prueba = {

        "titulo":
        "El Imperio Hitita"

    }


    resultado = generar_guion(
        prueba
    )


    imprimir_guion(
        resultado
    )