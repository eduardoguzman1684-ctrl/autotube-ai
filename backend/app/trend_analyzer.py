import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from dotenv import load_dotenv
from googleapiclient.discovery import build

# ============================================================
# CONFIGURACIÓN
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

REGIONES = ["US", "ES"]

SCORE_MINIMO = 50
DURACION_MINIMA_SEGUNDOS = 600

HISTORIAL_FILE = "used_videos.json"

CANALES_PRIORIDAD = [
    "BBC",
    "National Geographic",
    "DW",
    "History",
    "Smithsonian",
    "Discovery",
    "Arte"
]

CANALES_EXCLUIDOS = [
    "TikTok",
    "Shorts",
    "Compilation",
    "Top Facts",
    "Top 10"
]

FILTRO_MUSICA = [
    "official music",
    "official lyric",
    "official audio",
    "official video",
    "lyrics",
    "karaoke",
    "instrumental",
    "visualizer",
    "remix",
    "feat.",
    "ft.",
    "nightcore",
    "sped up",
    "slowed"
]

BUSQUEDAS_HISTORICAS = [
    "history documentary",
    "ancient civilization documentary",
    "world war documentary",
    "science documentary",
    "space documentary",
    "technology documentary"
]

BUSQUEDAS_HISTORICAS_ES = [
    "documental historia",
    "documental segunda guerra mundial",
    "civilizaciones antiguas documental",
    "documental espacio",
    "documental ciencia"
]

BUSQUEDAS_IA = [
    "artificial intelligence documentary",
    "future technology documentary",
    "openai documentary",
    "robots documentary"
]

