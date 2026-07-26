import asyncio
from audio.voice_generator import generar_voz
from audio.audio_mixer import mix_audio


def create_voice(text):

    print("🎙️ Generando voz profesional...")

    # Generar voz
    voice_path = generar_voz(text)

    print("🎵 Mezclando música de fondo...")

    # Mezclar música
    final_audio = mix_audio(voice_path)

    print("✅ Voz profesional lista")

    return final_audio