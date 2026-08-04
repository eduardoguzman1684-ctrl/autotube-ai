import os


# =====================================
# AUTOTUBE AI v2.0
# CONFIGURACIÓN PRINCIPAL
# =====================================


APP_NAME = "AutoTube AI"

VERSION = "2.0.0"


# Carpeta principal del proyecto

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# Carpetas del sistema

LOGS_DIR = os.path.join(
    BASE_DIR,
    "logs"
)

CACHE_DIR = os.path.join(
    BASE_DIR,
    "cache"
)

VIDEOS_DIR = os.path.join(
    BASE_DIR,
    "videos"
)

IMAGES_DIR = os.path.join(
    BASE_DIR,
    "images"
)

AUDIO_DIR = os.path.join(
    BASE_DIR,
    "audio"
)


# Crear carpetas automáticamente

for folder in [
    LOGS_DIR,
    CACHE_DIR,
    VIDEOS_DIR,
    IMAGES_DIR,
    AUDIO_DIR
]:

    os.makedirs(
        folder,
        exist_ok=True
    )


print(
    f"🚀 {APP_NAME} v{VERSION} cargado"
)