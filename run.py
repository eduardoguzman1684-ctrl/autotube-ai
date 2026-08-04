import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import APP_NAME, VERSION
from logger import info

from backend.app.pipeline.documentary_pipeline import ejecutar_pipeline
from backend.app.audio.xtts_generator import generar_documental


def ejecutar(script):

    ruta = os.path.join(BASE_DIR, script)

    print()
    print("=" * 60)
    print(f"🚀 Ejecutando {script}")
    print("=" * 60)

    if not os.path.exists(ruta):
        print("❌ Archivo no encontrado:")
        print(ruta)
        sys.exit(1)

    resultado = subprocess.run(
        [sys.executable, ruta],
        cwd=BASE_DIR
    )

    if resultado.returncode != 0:
        print(f"\n❌ Error ejecutando {script}")
        sys.exit(1)


def main():

    print("=" * 60)
    print(f"🎬 {APP_NAME} v{VERSION}")
    print("=" * 60)

    info("Sistema iniciado correctamente")

    print("\n🧠 Creando documental...")

    datos = ejecutar_pipeline(
        "El Imperio Hitita"
    )

    print("\n🎙️ Generando narraciones XTTS...")

    generar_documental(
        datos["escenas"]
    )

    ejecutar(r"backend\app\video\fake_motion.py")
    ejecutar(r"backend\app\video\narration_mixer.py")
    ejecutar(r"backend\app\video\final_builder.py")

    print()
    print("=" * 60)
    print("🎉 DOCUMENTAL TERMINADO")
    print("=" * 60)


if __name__ == "__main__":
    main()