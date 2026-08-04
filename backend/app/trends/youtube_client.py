import os
from pathlib import Path
from dotenv import load_dotenv
from googleapiclient.discovery import build


# =====================================================
# CARGAR .ENV
# =====================================================

BASE_DIR = Path(__file__).resolve().parents[3]

ENV_PATH = BASE_DIR / ".env"


print("📁 Buscando .env en:")
print(ENV_PATH)


load_dotenv(ENV_PATH)


API_KEY = os.getenv("YOUTUBE_API_KEY")


print("🔑 API KEY encontrada:", bool(API_KEY))


if not API_KEY:
    raise Exception(
        "❌ No existe YOUTUBE_API_KEY"
    )


# =====================================================
# CLIENTE YOUTUBE
# =====================================================

youtube = build(
    "youtube",
    "v3",
    developerKey=API_KEY
)


print("✅ Cliente YouTube creado")