from PIL import Image
import os


imagenes = [
    "images/escena_1.png",
    "images/escena_2.png",
    "images/escena_3.png"
]


for archivo in imagenes:

    print("Procesando:", archivo)


    img = Image.open(archivo)

    img = img.convert("RGB")


    img.thumbnail(
        (1280,720)
    )


    salida = archivo.replace(
        ".png",
        "_small.jpg"
    )


    img.save(
        salida,
        "JPEG",
        quality=85
    )


    print(
        "Creada:",
        salida
    )


print("✅ Imágenes optimizadas")