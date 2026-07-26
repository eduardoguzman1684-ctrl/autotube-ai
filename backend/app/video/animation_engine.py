import time


def animate_scene(scene):

    print("\n🎞️ Animando escena...")

    print(f"Escena: {scene['titulo']}")
    print(f"Descripción: {scene['descripcion']}")


    movimientos = [
        "zoom cinematográfico lento",
        "paneo horizontal suave",
        "movimiento de cámara 3D falso",
        "acercamiento con profundidad"
    ]


    movimiento = movimientos[
        (scene["escena"] - 1) % len(movimientos)
    ]


    animation = {

        "escena": scene["escena"],

        "titulo": scene["titulo"],

        "descripcion": scene["descripcion"],

        "movimiento": movimiento,

        "duracion": 8,

        "efecto": "cinematic"

    }


    print("🎥 Efecto aplicado:", movimiento)


    return animation



def create_animation_sequence(scenes):

    animations = []


    for scene in scenes:

        animation = animate_scene(scene)

        animations.append(animation)


    return animations



if __name__ == "__main__":

    prueba = [

        {
            "escena":1,
            "titulo":"Introducción",
            "descripcion":"Presentación del tema"
        },

        {
            "escena":2,
            "titulo":"Desarrollo",
            "descripcion":"Explicación"
        }

    ]


    resultado = create_animation_sequence(prueba)


    for r in resultado:
        print(r)