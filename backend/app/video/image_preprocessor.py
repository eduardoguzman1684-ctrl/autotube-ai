from PIL import Image
import os

INPUT_FOLDER = "images"
OUTPUT_FOLDER = "images/ready"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def preparar(nombre):

    origen = os.path.join(INPUT_FOLDER, nombre)

    destino = os.path.join(
        OUTPUT_FOLDER,
        nombre.replace(".png", ".jpg")
    )

    print("Procesando:", origen)

    img = Image.open(origen).convert("RGB")

    img.thumbnail((1280,720))

    fondo = Image.new(
        "RGB",
        (1280,720),
        (0,0,0)
    )

    x = (1280-img.width)//2
    y = (720-img.height)//2

    fondo.paste(img,(x,y))

    fondo.save(
        destino,
        quality=95
    )

    print("✅", destino)


if __name__ == "__main__":

    for i in range(1,4):

        preparar(f"escena_{i}.png")

    print("\n🎉 Todas las imágenes fueron optimizadas.")