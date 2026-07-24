from gtts import gTTS


def create_voice(text):

    audio_path = "audio/voz.mp3"

    voz = gTTS(
        text=text,
        lang="es"
    )

    voz.save(audio_path)

    return audio_path