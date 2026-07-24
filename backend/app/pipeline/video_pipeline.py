from generators.script_generator import generate_script
from generators.voice import create_voice
from generators.scene_generator import generate_scenes
from generators.image_manager import create_scene_images
from generators.subtitle_generator import generate_subtitles

from video.animation_engine import create_animation_sequence
from video.video_creator import create_video


class VideoPipeline:

    def run(self, topic):

        print("\n📝 Generando guion...\n")

        script = generate_script(topic)

        with open("storage/scripts/guion.txt", "w", encoding="utf-8") as file:
            file.write(script)

        print("✅ Guion creado")


        print("\n🎙️ Generando voz...")

        audio = create_voice(script)

        print(f"✅ Voz creada: {audio}")


        print("\n🎬 Generando escenas...")

        scenes = generate_scenes(topic)

        with open("storage/scenes/escenas.txt", "w", encoding="utf-8") as file:
            for scene in scenes:
                file.write(str(scene))
                file.write("\n\n")

        print("✅ Escenas creadas")


        print("\n🎞️ Creando animaciones...")

        animations = create_animation_sequence(scenes)

        with open("storage/scenes/animations.txt", "w", encoding="utf-8") as file:
            for animation in animations:
                file.write(str(animation))
                file.write("\n\n")

        print("✅ Animaciones creadas")


        print("\n🖼️ Preparando imágenes...")

        images = create_scene_images(scenes)

        print(f"✅ {len(images)} imágenes preparadas")


        print("\n📝 Generando subtítulos...")

        subtitles = generate_subtitles(script)

        print(f"✅ {len(subtitles)} subtítulos creados")


        print("\n🎬 Creando video...")

        video = create_video()

        print(f"✅ Video creado: {video}")


        return video