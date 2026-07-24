import time


def animate_scene(scene):

    print("\n🎞️ Animando escena...")
    
    print(f"Escena: {scene['titulo']}")
    print(f"Descripción: {scene['descripcion']}")

    time.sleep(2)

    animation = {
        "escena": scene["escena"],
        "estado": "animación creada",
        "movimiento": "zoom suave + transición"
    }

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
            "escena": 1,
            "titulo": "Introducción",
            "descripcion": "Presentación del tema"
        }
    ]

    resultado = create_animation_sequence(prueba)

    print(resultado)