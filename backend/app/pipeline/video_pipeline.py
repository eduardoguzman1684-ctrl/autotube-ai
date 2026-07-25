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
        print("DEBUG A")

        script = generate_script(topic)

        print("DEBUG B")

        with open("storage/scripts/guion.txt", "w", encoding="utf-8") as file:
            file.write(script)

        print("DEBUG C")
        print("✅ Guion creado")

        print("\n🎙️ Generando voz...")
        print("DEBUG D")

        audio = create_voice(script)

        print("DEBUG E")
        print(f"✅ Voz creada: {audio}")

        print("\n🎬 Generando escenas...")
        scenes = generate_scenes(topic)

        print("DEBUG F")

        print("\n🎞️ Creando animaciones...")
        animations = create_animation_sequence(scenes)

        print("DEBUG G")

        print("\n🖼️ Preparando imágenes...")
        images = create_scene_images(scenes)

        print("DEBUG H")

        print("\n📝 Generando subtítulos...")
        subtitles = generate_subtitles(script)

        print("DEBUG I")

        print("\n🎬 Creando video...")
        video = create_video()

        print("DEBUG J")

        return video