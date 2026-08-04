import logging
import os

from config import LOGS_DIR


# =====================================
# AUTOTUBE AI v2.0
# SISTEMA DE LOGS
# =====================================


LOG_FILE = os.path.join(
    LOGS_DIR,
    "autotube.log"
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)


logger = logging.getLogger(
    "AutoTubeAI"
)



def info(message):

    logger.info(message)



def warning(message):

    logger.warning(message)



def error(message):

    logger.error(message)



print(
    "📝 Logger AutoTube AI v2.0 cargado"
)