import os
import sys
import json
import logging


# =====================================
# AUTOTUBE AI v2.0
# DOCUMENTARY PIPELINE XTTS READY
# =====================================


ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../.."
    )
)


sys.path.insert(
    0,
    ROOT_DIR
)


from backend.app.generators.topic_generator import generar_tema
from backend.app.generators.script_generator import generar_guion
from backend.app.generators.scene_expander import expandir_escenas
from backend.app.generators.image_generator import generar_imagenes


logger = logging.getLogger(
    "AutoTubeAI"
)



# =====================================
# GUARDAR ESCENAS PARA XTTS
# =====================================

def guardar_escenas_json(escenas):

    data_dir = os.path.join(
        ROOT_DIR,
        "backend",
        "app",
        "data"
    )


    os.makedirs(
        data_dir,
        exist_ok=True
    )


    archivo = os.path.join(
        data_dir,
        "escenas.json"
    )


    exportar = []


    for escena in escenas:


        exportar.append({

            "numero": escena["numero"],

            "titulo": escena["titulo"],


            # TEXTO QUE USARA XTTS

            "texto": escena.get(
                "narracion",
                escena.get(
                    "texto",
                    escena["titulo"]
                )
            ),


            "imagen_prompt": escena.get(
                "imagen_prompt",
                ""
            )

        })


    with open(
        archivo,
        "w",
        encoding="utf-8"
    ) as f:


        json.dump(
            exportar,
            f,
            indent=4,
            ensure_ascii=False
        )


    print()
    print("💾 Escenas guardadas:")
    print(archivo)




# =====================================
# PIPELINE PRINCIPAL
# =====================================

def ejecutar_pipeline(
    tema=None
):


    print()

    print("=" * 60)

    print(
        "🎬 AUTOTUBE AI DOCUMENTARY PIPELINE"
    )

    print("=" * 60)



    # -------------------------------
    # CREAR TEMA
    # -------------------------------


    documental = generar_tema(
        tema
    )


    print()

    print("📜 DOCUMENTAL")

    print("-------------------------")

    print(
        documental["titulo"]
    )



    # -------------------------------
    # CREAR GUION
    # -------------------------------


    guion = generar_guion(
        documental
    )


    print()

    print("=" * 60)

    print("📝 GUION")

    print("=" * 60)


    print(
        guion["introduccion"]
    )



    # -------------------------------
    # CREAR ESCENAS
    # -------------------------------


    escenas = expandir_escenas(
        documental
    )


    print()

    print("=" * 60)

    print("🎬 ESCENAS")

    print("=" * 60)



    for escena in escenas:


        print(

            f"🎞 Escena {escena['numero']}: "
            f"{escena['titulo']}"

        )



    # -------------------------------
    # CREAR IMAGENES
    # -------------------------------


    imagenes = generar_imagenes(
        escenas
    )


    print()

    print("=" * 60)

    print("🖼 IMÁGENES")

    print("=" * 60)


    print(
        f"Total: {len(imagenes)}"
    )



    # -------------------------------
    # EXPORTAR DATOS XTTS
    # -------------------------------


    guardar_escenas_json(
        escenas
    )



    logger.info(
        "Pipeline documental completado XTTS READY"
    )



    return {


        "documental":

        documental,


        "guion":

        guion,


        "escenas":

        escenas,


        "imagenes":

        imagenes

    }




if __name__ == "__main__":


    ejecutar_pipeline(
        "El Imperio Hitita"
    )