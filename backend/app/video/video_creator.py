import os
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips


def create_video():

    print("🎬 Construyendo video cinematográfico...")

    image_folder = "images"

    # ← ESTA ES LA LÍNEA CORRECTA
    audio_file = "audio/audio_final.mp3"

    output = "videos/autotube_video.mp4"

    os.makedirs("videos", exist_ok=True)

    images = [
        "images/escena_1.jpg",
        "images/escena_2.jpg",
        "images/escena_3.jpg",
        "images/escena_4.jpg"
    ]

    clips = []

    for img in images:

        print(f"🎥 Procesando: {img}")

        clip = (
            ImageClip(img)
            .resized(width=1080)
            .with_duration(5)
        )

        clip = clip.resized(new_size=(1080, 720))

        clips.append(clip)

    video = concatenate_videoclips(
        clips,
        method="compose"
    )

    print("🎙️ Agregando voz...")

    if os.path.exists(audio_file):

        audio = AudioFileClip(audio_file)

        video = video.with_audio(audio)

    print("🎬 Exportando video compatible...")

    video.write_videofile(
        output,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )

    print("✅ Video creado:", output)

    return output