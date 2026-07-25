import subprocess
import os
import re


MODEL = "models/es_ES-davefx-medium.onnx"


def clean_text(text):

    # Eliminar formato Markdown y símbolos que Piper lee mal
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\*", "", text)
    text = re.sub(r"#", "", text)
    text = re.sub(r"_", "", text)
    text = re.sub(r"=", "", text)
    text = re.sub(r"`", "", text)

    # Eliminar líneas con separadores
    text = text.replace("---", "")

    # Quitar espacios repetidos
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def create_voice(text):

    os.makedirs("audio", exist_ok=True)

    audio_path = "audio/voz.mp3"

    wav_path = "audio/voz.wav"


    print("🧹 Limpiando guion para voz...")

    text = clean_text(text)


    print("🎙️ Generando voz con Piper...")


    subprocess.run(
        [
            "python",
            "-m",
            "piper",
            "--model",
            MODEL,
            "--output_file",
            wav_path
        ],
        input=text,
        text=True,
        check=True
    )


    # Convertir wav a mp3 usando ffmpeg

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            wav_path,
            audio_path
        ],
        check=True
    )


    print("✅ Voz creada:", audio_path)

    return audio_path