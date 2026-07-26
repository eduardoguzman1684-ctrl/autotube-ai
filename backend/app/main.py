from pipeline.video_pipeline import VideoPipeline
from ai.gemini_generator import generar_con_gemini


def main():

    print("🤖 AutoTube AI iniciado")
    print("------------------------")

    topic = input("Escribe el tema del video: ")

    print("\n🧠 Gemini creando contenido...")
    
    contenido = generar_con_gemini(topic)

    print("\n✅ Contenido generado por Gemini:")
    print("-------------------------------")
    print(contenido[:1000])

    pipeline = VideoPipeline()

    video = pipeline.run(topic)

    print("\n==============================")
    print("🎉 PROCESO COMPLETADO")
    print("==============================")
    print(f"📹 Video generado: {video}")


if __name__ == "__main__":
    main()